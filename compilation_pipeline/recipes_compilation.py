"""Compilation recipe generator.

Takes a *theme* (e.g. "5 lazy weeknight dinners", "5 high-protein lunches")
and asks GPT-4o-mini to produce 5 distinct recipes that fit the theme.

Each recipe has:
  - title (display, all caps for the recipe-page header looks great)
  - short_pitch (one phrase used optionally on the photo slide)
  - ingredients: grouped sections like FOR DISH BASE / FOR PROTEIN / FOR
    TOPPINGS, each section is a list of ingredient strings with quantities
  - instructions: numbered steps, list of strings
  - hero_image_prompt: a styled food-photography prompt for the dish photo

We also output:
  - hook_caption: edgy 1-line title for the FIRST slide ("5 weekend dinners
    for your lazy ass" style)
  - hook_image_prompt: cinematic moody-kitchen Nano Banana prompt for the hook
  - cta_caption: 3-line copy for the mid-carousel CTA slide
"""
from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass, field, asdict

# Fixed CTA copy — same on every single slideshow, never AI-generated
CTA_CAPTION: list[str] = [
    "Here's the trick for saving recipes:",
    "Like > Share > RecipeVault.",
    "That's all it takes to keep the full recipe.",
]


@dataclass
class CompilationRecipe:
    title: str                       # "STICKY GINGER SOY CHICKEN THIGHS"
    short_pitch: str                 # "Sweet, sticky, weeknight winner"
    ingredient_sections: list[dict]  # [{name: "FOR DISH BASE", items: [...]}, ...]
    instructions: list[str]          # ["1. Season chicken...", "2. Whisk sauce...", ...]
    hero_image_prompt: str           # for Nano Banana (the food photo slide)


@dataclass
class Compilation:
    slug: str
    theme: str                       # "5 lazy weeknight dinners"
    hook_caption: str                # edgy line, e.g. "5 weekend dinners for your LAZY ASS"
    hook_image_prompt: str           # cinematic
    cta_caption: list[str]           # 2-3 lines of mid-carousel CTA copy
    recipes: list[CompilationRecipe] # exactly 5

    def to_dict(self) -> dict:
        return asdict(self)


SYSTEM_PROMPT = """You design viral TikTok recipe COMPILATION carousels for a
food creator promoting RecipeVault (a recipe-saving mobile app).

Each compilation = 5 distinct recipes around a theme, plus an attention-grabbing
hook and a mid-carousel CTA. Output ONE valid JSON object, no prose.

VOICE/TONE:
- Hook captions are punchy, slightly edgy, casual TikTok English. Examples:
    "5 weekend dinners for your LAZY ASS"
    "5 dinners that hit harder than your ex's apology"
    "5 girl-dinner upgrades that won't make your therapist worried"
    "5 high-protein meals if cooking is your villain origin story"
- Recipe titles are written like cookbook headlines, ALL CAPS preferred.
    "STICKY GINGER SOY CHICKEN THIGHS"
    "CREAMY CAJUN SAUSAGE & RICE SKILLET"
- Instructions are numbered, descriptive, action-led with timing/technique cues.
  Use 9-12 steps per recipe. Examples:
    "Season chicken thighs generously with salt and pepper on both sides."
    "Heat 2 tbsp olive oil in a 10-inch cast iron skillet over medium-high."
    "Sear chicken skin-side down for 6-7 minutes until deeply golden."
  The idea is the page LOOKS FULL of text, like a real cookbook page.

INGREDIENT SECTIONS (grouped, like in a printed cookbook):
- Use 3-4 sections per recipe. Common section names:
    "FOR DISH BASE", "FOR THE PROTEIN", "FOR THE SAUCE", "FOR CREAMINESS",
    "FOR TOPPINGS / SERVING", "FOR THE MARINADE", "FOR GARNISH"
- 3-6 items per section. Each item must include a precise quantity and a brief
  modifier when useful, e.g. "2 lbs boneless skinless chicken thighs, trimmed",
  "1 tbsp gochujang (Korean chili paste)", "1/4 cup low-sodium soy sauce".
  The total ingredient list should feel detailed, like a printed cookbook —
  aim for 12-18 ingredient lines total across all sections.

HERO IMAGE PROMPTS (for gemini-2.0-flash-preview-image-generation / Imagen 3):
- Style: warm, cinematic food-photography, shallow depth of field, beautifully
  styled, restaurant-quality. Specific lighting (golden-hour kitchen light,
  warm tungsten), cast-iron skillet or rustic plate, garnish, slight steam.
- 30-50 words each. Focus on the FINISHED PLATED DISH.
- Example: "Cinematic close-up overhead photo of a cast iron skillet on a dark
  wooden table, glossy sticky ginger soy chicken thighs glistening with sauce,
  fresh chopped scallions and sesame seeds on top, warm tungsten lighting, soft
  blurred background, restaurant food magazine quality, shot on Sony A7."

HOOK IMAGE PROMPT:
- Cinematic spread of multiple finished dishes on a wooden table, warm moody
  lighting, shallow depth, food-magazine cover vibe. Ambiguous enough to fit
  any 5-recipe set.

CTA CAPTION:
- 2-3 short lines that sit on a colored background slide. Sells the app angle.
  Examples:
    ["Here's the trick for saving recipes:",
     "Like > Share > RecipeVault.",
     "That's all it takes to keep the full recipe."]
"""

USER_TEMPLATE = """Design a 5-recipe compilation carousel for the theme: {theme}

Return JSON with EXACTLY this shape:
{{
  "slug": "lowercase_snake_case_max_40_chars",
  "theme": "the theme string back",
  "hook_caption": "the edgy hook line",
  "hook_image_prompt": "...",
  "cta_caption": ["line 1", "line 2", "line 3"],
  "recipes": [
    {{
      "title": "RECIPE TITLE IN CAPS",
      "short_pitch": "...",
      "ingredient_sections": [
        {{"name": "FOR DISH BASE", "items": ["...", "..."]}},
        {{"name": "FOR THE SAUCE", "items": ["...", "..."]}}
      ],
      "instructions": ["1. Step one...", "2. Step two..."],
      "hero_image_prompt": "..."
    }},
    {{ ... 4 more, exactly 5 total ... }}
  ]
}}
"""


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return s[:40]


def _call_gemini_json(model: str, system_prompt: str, user_prompt: str,
                      temperature: float = 0.9) -> dict:
    """Call Gemini text model and return parsed JSON.
    Uses the same GEMINI_API_KEY as the image gen (Nano Banana).
    Retries on 503 with exponential backoff, then falls back to gemini-1.5-flash."""
    import time as _time
    from google import genai
    from google.genai import types as gtypes

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY missing from environment")
    # gemini-2.5-flash is a thinking model — it can take 90-150s on Render.
    # GEMINI_TEXT_TIMEOUT is in seconds; google-genai http_options timeout is ms.
    _timeout_s = max(int(os.environ.get("GEMINI_TEXT_TIMEOUT", "180")), 10)
    client = genai.Client(api_key=api_key,
                          http_options={"timeout": _timeout_s * 1000})

    # Model priority: try requested model first, then stable fallbacks
    models_to_try = [model]
    if model != "gemini-1.5-flash":
        models_to_try.append("gemini-1.5-flash")
    if "gemini-2.0-flash" not in models_to_try:
        models_to_try.append("gemini-2.0-flash")

    last_exc = None
    for attempt_model in models_to_try:
        for attempt in range(3):  # up to 3 retries per model
            try:
                resp = client.models.generate_content(
                    model=attempt_model,
                    contents=[system_prompt + "\n\n" + user_prompt],
                    config=gtypes.GenerateContentConfig(
                        temperature=temperature,
                        response_mime_type="application/json",
                    ),
                )
                raw = resp.candidates[0].content.parts[0].text
                if attempt_model != model:
                    print(f"  [gemini] used fallback model {attempt_model}")
                return json.loads(raw)
            except Exception as e:
                last_exc = e
                err_str = str(e)
                is_503    = "503" in err_str or "UNAVAILABLE" in err_str or "high demand" in err_str
                is_429    = "429" in err_str or "quota" in err_str.lower() or "RESOURCE_EXHAUSTED" in err_str
                is_timeout = ("timed out" in err_str.lower() or "timeout" in err_str.lower()
                              or "deadline" in err_str.lower() or "read operation" in err_str.lower())
                if is_503 or is_429 or is_timeout:
                    wait = (2 ** attempt) * 5  # 5s, 10s, 20s
                    reason = "timed out" if is_timeout else "overloaded"
                    print(f"  [gemini] {attempt_model} {reason} (attempt {attempt+1}/3) — retrying in {wait}s")
                    _time.sleep(wait)
                else:
                    break  # non-retryable error, try next model immediately

    raise RuntimeError(f"All Gemini models failed. Last error: {last_exc}")


def generate_compilation(theme: str, model: str = "gemini-2.5-flash") -> Compilation:
    """Generate a 5-recipe compilation. Uses Gemini text model (same key as
    Nano Banana) so we don't depend on OpenAI quota."""
    data = _call_gemini_json(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=USER_TEMPLATE.format(theme=theme),
        temperature=0.9,
    )

    recipes = [
        CompilationRecipe(
            title=r["title"],
            short_pitch=r.get("short_pitch", ""),
            ingredient_sections=r["ingredient_sections"],
            instructions=r["instructions"],
            hero_image_prompt=r["hero_image_prompt"],
        )
        for r in data["recipes"]
    ]
    assert len(recipes) == 5, f"expected 5 recipes, got {len(recipes)}"

    return Compilation(
        slug=_slugify(data.get("slug") or theme),
        theme=data.get("theme", theme),
        hook_caption=data["hook_caption"],
        hook_image_prompt=data["hook_image_prompt"],
        cta_caption=CTA_CAPTION,   # always the fixed brand copy, never AI-generated
        recipes=recipes,
    )


def save_compilation_json(comp: Compilation, out_dir: str) -> str:
    import os
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, f"{comp.slug}.json")
    with open(p, "w") as f:
        json.dump(comp.to_dict(), f, indent=2)
    return p
