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

# Fixed CTA copy — same on every single-format slideshow, never AI-generated.
# Domain-agnostic save prompt (food / fitness / finance / productivity / etc.).
CTA_CAPTION: list[str] = [
    "Save this carousel before you scroll on.",
    "Like → Share → Bookmark.",
    "Comes back when you need it.",
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

SYSTEM_PROMPT = """You design 10-slide DEEP-DIVE carousels for social creators.
The topic can be anything — recipes, workouts, money concepts, productivity
playbooks, life skills, tech how-tos, anything. Infer the domain from the
user's brief and adapt every part of the output accordingly.

The visual style is the popular "tight subject shot" tutorial style: every
slide is a clean, focused, overhead phone-photo of ONE element on a plain
uncluttered background. No clutter, no environment, no props beyond what is
the subject of that slide.

You output ONLY a single valid JSON object, no prose.

Each output is broken into exactly 10 slides in this fixed structure (the
slide_type values are NEVER changed — they're contract names. Map your topic
to each conceptual slot.):

  1. hook          → cover shot of the finished result. Title goes here.
  2. ingredients   → "what you need" — overview of the components (ingredients
                     for food; tools/exercises/concepts for any other domain).
  3. protein_prep  → main component / heaviest hitter (the protein for food;
                     the keystone exercise / core concept / primary tool for
                     other domains).
  4. veg_one       → first supporting component / sub-topic.
  5. veg_two       → second supporting component / sub-topic.
  6. sauce         → the secret formula or key framework, with 3-5 callouts
                     listing its ingredients/components/principles.
  7. combine       → everything assembled / integrated together.
  8. assemble      → active execution shot (the doing).
  9. finish        → the polish / final touches.
  10. final        → the outcome / payoff shot.

For each slide produce:

- caption: a SHORT overlay label, descriptive of what's in the frame or what's
  happening. Use punchy social-media voice. Domain-flexible examples:
    Food (ingredients):     "Grilled chicken", "Cherry tomatoes", "Greek yogurt"
    Fitness (ingredients):  "Bulgarian split squat", "Romanian deadlift"
    Productivity (sauce):   "Deep work block 9-11am"
    Finance (sauce):        "DCA + index fund + 10yr horizon"
    Action slides (7,8,9):  "Mix it all" / "Pan fry 5 min"  (food)
                            "3 sets × 10 reps"            (fitness)
                            "Block 90 minutes"            (productivity)
    Slide 10 caption:       1-2 word punchline. "Dig in", "Done", "Ship it".

- image_prompt: a detailed visual prompt. ALWAYS lead with:
    "Tight overhead phone-photo, [SUBJECT] centered in frame, [WHAT IT IS],
    plain [SURFACE] visible at edges, nothing else in frame, clean and minimal."
  Adapt the SUBJECT and SURFACE to the domain:
    Food:         stainless mixing bowl / ceramic ramekin / cast-iron skillet
                  on butcher block, white counter, marble
    Fitness:      single dumbbell, kettlebell, resistance band, yoga mat
                  on a gym floor or neutral mat
    Finance:      notebook + pen / single index card / coffee mug
                  on a clean desk or felt mat
    Productivity: mechanical keyboard / single book / planner page
                  on a tidy desk
  Avoid: clutter, decorative props, plants, towels, anything beyond the subject
  and its surface. Keep image_prompt under 60 words.

- callouts: only for slide 6 (sauce); a list of 3-5 names of the components
  that make up the "sauce" (the secret formula). Examples:
    Food sauce:        ["greek yogurt", "mayo", "mustard", "honey", "black pepper"]
    Productivity sauce:["focus block", "single tab", "phone in drawer", "timer"]
    Finance sauce:     ["DCA", "index funds", "10yr horizon", "auto-invest"]
  Empty list for all other slides.

Also produce:
- slug: lowercase snake_case id, max 30 chars
- title: human-readable title
- short_pitch: 1 sentence, max 12 words
- ingredients: the "what you need" list (ingredients for food; tools or
  concepts for other domains) as an array of strings with quantities/specifics
  where applicable.
"""


USER_TEMPLATE = """Design a 10-slide deep-dive slideshow for: {brief}

Detect the domain (food/fitness/finance/productivity/lifestyle/tech/etc.) from
the brief and map every slide_type to the appropriate concept for that domain
while keeping the slide_type values exactly as listed below.

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
