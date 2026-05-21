"""
Recipe content generator.

Uses GPT-4o-mini to produce a structured recipe with a 10-slide breakdown.
Each slide has: a short overlay caption, an image prompt, and (for slide 6)
optional sauce-component callouts.

Usage:
    from recipes import generate_recipe
    recipe = generate_recipe("a high-protein chicken caesar wrap")
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

# Fixed CTA copy — same on every single slideshow, never AI-generated
CTA_CAPTION: list[str] = [
    "Here's the trick for saving recipes:",
    "Like > Share > RecipeVault.",
    "That's all it takes to keep the full recipe.",
]

from openai import OpenAI

# ---------------------------------------------------------------------------
# Slide schema
# ---------------------------------------------------------------------------
# The 10-slide structure that drives engagement:
#   1.  hook              hero shot of finished dish
#   2.  ingredients       flat-lay of all ingredients
#   3.  protein_prep      single-ingredient close-up (e.g. grilled chicken)
#   4.  veg_one           single-ingredient close-up (e.g. lettuce)
#   5.  veg_two           single-ingredient close-up (e.g. tomato)
#   6.  sauce             bowl of sauce with callout labels for each component
#   7.  combine           everything mixed in a single bowl
#   8.  assemble          wrap/fold/plate action shot
#   9.  finish            cooking/crisping/garnish action shot
#   10. final             beauty hero close + CTA
# ---------------------------------------------------------------------------

SLIDE_TYPES = [
    "hook",
    "ingredients",
    "protein_prep",
    "veg_one",
    "veg_two",
    "sauce",
    "combine",
    "assemble",
    "finish",
    "final",
]


@dataclass
class Slide:
    index: int
    slide_type: str
    caption: str           # text overlay shown on the slide
    image_prompt: str      # prompt sent to image model
    callouts: list[str] = field(default_factory=list)  # used for sauce slide


@dataclass
class Recipe:
    slug: str              # filesystem-safe id, e.g. "chicken_caesar_wrap"
    title: str             # display title
    short_pitch: str       # 1-line description used in hook
    ingredients: list[str]
    slides: list[Slide]
    cta_caption: list[str] = field(default_factory=lambda: CTA_CAPTION.copy())

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Prompt for the LLM that designs each recipe
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You design recipe-slideshow content for a TikTok food creator.
The visual style is the popular "tight bowl shot" cooking-tutorial style: every
slide is a clean, focused, overhead phone-photo of food in a single vessel
(stainless steel mixing bowl, ceramic bowl, sheet pan, non-stick skillet,
measuring cup) with a plain uncluttered background. NO kitchen environment,
NO plants, NO towels, NO props. Just the vessel, the food, plain surface.

You output ONLY a single valid JSON object, no prose.

Each output is a complete recipe broken into exactly 10 slides that follow this fixed structure:
1. hook          - the finished dish in the bowl/dish it was made in (recipe title goes here)
2. ingredients   - all main ingredients laid in one bowl OR on a sheet pan, labeled later
3. protein_prep  - the prepared protein/starch IN A BOWL (e.g. "Grilled chicken", "Cooked pasta")
4. veg_one       - the first vegetable IN A BOWL (e.g. "Cherry tomatoes", "Cucumbers diced")
5. veg_two       - the second vegetable IN A BOWL (e.g. "Red onion", "Avocado")
6. sauce         - the sauce in a small bowl, with 3-5 component callouts
7. combine       - everything mixed together IN ONE LARGE BOWL
8. assemble      - the wrap/sandwich/plating happening, focused tight
9. finish        - cooking IN A PAN or oven dish (sizzle/steam visible)
10. final        - the finished dish plated, ready to eat

For each slide produce:
- caption: a SHORT overlay label, descriptive of WHAT'S IN THE BOWL or WHAT IS HAPPENING.
  Use the popular TikTok cooking-account style:
    * Ingredient slides (3,4,5): the ingredient name (sometimes with quantity).
      Examples: "Grilled chicken", "Cherry tomatoes", "Red onion", "Greek yogurt",
      "Pomegranate seeds", "Sweet corn 1 cup", "Olive oil 2 tbsp"
    * Action slides (7,8,9): a brief instruction.
      Examples: "Mix it all", "Wrap it tight", "Pan fry 5 min", "Bake 175 / 8 min"
    * Slide 1 caption is the recipe title (compositor auto-overrides anyway).
    * Slide 10 caption: "Dig in", "Done", or similar 1-2 word punchline.

- image_prompt: a detailed visual prompt. ALWAYS lead with:
    "Tight overhead phone-photo, [VESSEL] centered in frame, [WHAT'S INSIDE THE VESSEL],
    plain [SURFACE] visible at edges, nothing else in frame, clean and minimal."
  Examples of good prompts:
    * "Tight overhead phone-photo, stainless steel mixing bowl centered, filled with cooked
      grilled chicken pieces, plain off-white kitchen counter visible at edges, nothing
      else in frame, clean and minimal."
    * "Tight overhead phone-photo, small ceramic ramekin bowl centered, filled with bright
      red pomegranate seeds, plain butcher block wood surface, nothing else in frame."
    * "Tight overhead phone-photo, non-stick black skillet centered on a clean stovetop,
      golden seared salmon fillets sizzling inside, gentle steam, dark stovetop visible
      at edges, nothing else in frame."
  Avoid: kitchen props (plants, towels, paper towels, soap bottles, water glasses,
  decorations). Keep image_prompt under 60 words.

- callouts: only for slide 6 (sauce); a list of 3-5 ingredient names that make up the sauce
  (e.g. ["greek yogurt", "mayo", "mustard", "honey", "black pepper"]). Empty list for all
  other slides.

Also produce:
- slug: lowercase snake_case id, max 30 chars
- title: human-readable title
- short_pitch: 1 sentence, max 12 words
- ingredients: full ingredient list with quantities, as an array of strings
"""


USER_TEMPLATE = """Design a recipe slideshow for: {brief}

Return JSON with this exact shape:
{{
  "slug": "...",
  "title": "...",
  "short_pitch": "...",
  "ingredients": ["...", "..."],
  "slides": [
    {{"index": 1, "slide_type": "hook",          "caption": "...", "image_prompt": "...", "callouts": []}},
    {{"index": 2, "slide_type": "ingredients",   "caption": "...", "image_prompt": "...", "callouts": []}},
    {{"index": 3, "slide_type": "protein_prep",  "caption": "...", "image_prompt": "...", "callouts": []}},
    {{"index": 4, "slide_type": "veg_one",       "caption": "...", "image_prompt": "...", "callouts": []}},
    {{"index": 5, "slide_type": "veg_two",       "caption": "...", "image_prompt": "...", "callouts": []}},
    {{"index": 6, "slide_type": "sauce",         "caption": "...", "image_prompt": "...", "callouts": ["...", "..."]}},
    {{"index": 7, "slide_type": "combine",       "caption": "...", "image_prompt": "...", "callouts": []}},
    {{"index": 8, "slide_type": "assemble",      "caption": "...", "image_prompt": "...", "callouts": []}},
    {{"index": 9, "slide_type": "finish",        "caption": "...", "image_prompt": "...", "callouts": []}},
    {{"index": 10,"slide_type": "final",         "caption": "...", "image_prompt": "...", "callouts": []}}
  ]
}}
"""


# ---------------------------------------------------------------------------


def generate_recipe(brief: str, model: str = "gpt-4o-mini") -> Recipe:
    """Call the LLM to design a recipe for the given brief."""
    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": USER_TEMPLATE.format(brief=brief)},
        ],
        temperature=0.8,
    )
    raw = resp.choices[0].message.content
    data = json.loads(raw)

    slides = [
        Slide(
            index=s["index"],
            slide_type=s["slide_type"],
            caption=s["caption"],
            image_prompt=s["image_prompt"],
            callouts=s.get("callouts", []) or [],
        )
        for s in data["slides"]
    ]
    # Defensive: ensure we got exactly 10 slides in expected order
    assert len(slides) == 10, f"expected 10 slides, got {len(slides)}"
    for i, s in enumerate(slides, 1):
        assert s.index == i, f"slide {i} has index {s.index}"
        assert s.slide_type == SLIDE_TYPES[i - 1], f"slide {i} wrong type: {s.slide_type}"

    return Recipe(
        slug=data["slug"],
        title=data["title"],
        short_pitch=data["short_pitch"],
        ingredients=data["ingredients"],
        slides=slides,
    )


def save_recipe_json(recipe: Recipe, out_dir: str) -> str:
    """Persist the recipe as JSON next to its image folder."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{recipe.slug}.json")
    with open(path, "w") as f:
        json.dump(recipe.to_dict(), f, indent=2)
    return path


if __name__ == "__main__":
    # quick manual test
    r = generate_recipe("a healthy chicken caesar wrap, 5 minutes")
    print(json.dumps(r.to_dict(), indent=2))
