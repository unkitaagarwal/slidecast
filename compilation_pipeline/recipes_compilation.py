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
from typing import Optional

# Fixed CTA copy — same on every compilation, never AI-generated.
# Domain-agnostic save prompt (works for food, fitness, finance, productivity,
# lifestyle, etc.). To rebrand or reword, edit this list directly.
CTA_CAPTION: list[str] = [
    "Save this carousel before you scroll on.",
    "Like → Share → Bookmark.",
    "Comes back when you need it.",
]


@dataclass
class CompilationRecipe:
    """One item in a compilation. Field names are recipe-flavoured for backwards
    compatibility with older JSON specs and the compositor, but the *content*
    works across any domain — ingredient_sections becomes "key facts" /
    "exercises" / "metrics" etc. depending on the brief, and instructions
    becomes "steps" / "form cues" / "talking points" etc. The compositor just
    renders whatever section names Gemini wrote."""
    title: str                       # "STICKY GINGER SOY CHICKEN THIGHS" or "MORNING ROUTINE — 15 MIN"
    short_pitch: str                 # one-line summary
    ingredient_sections: list[dict]  # [{name: "<SECTION>", items: [...]}, ...] — see prompt
    instructions: list[str]          # numbered steps OR key points, 9-12 per item
    hero_image_prompt: str           # for Nano Banana — adapted to the topic


@dataclass
class Compilation:
    slug: str
    theme: str                       # the user's brief, echoed back
    hook_caption: str                # punchy 1-line cover headline
    hook_image_prompt: str           # cinematic spread visual
    cta_caption: list[str]           # 2-3 lines of mid-carousel CTA copy
    recipes: list[CompilationRecipe] # exactly 5 items

    def to_dict(self) -> dict:
        return asdict(self)


SYSTEM_PROMPT = """You design viral 5-item COMPILATION carousels for social
creators. The topic can be anything — recipes, workouts, money tips, productivity
hacks, life advice, finance concepts, tech tools, anything. Infer the domain
from the user's brief and adapt every part of the output accordingly.

Output ONE valid JSON object, no prose.

VOICE/TONE
- Hook captions are punchy, slightly edgy, casual social-media English.
  Domain-flexible examples:
    Food:         "5 dinners that hit harder than your ex's apology"
    Fitness:      "5 mistakes wrecking your bench press"
    Finance:      "5 index fund myths your dad still believes"
    Productivity: "5 habits that quietly steal your focus"
    Lifestyle:    "5 morning rituals nobody actually does"
- Item titles read like magazine headlines, ALL CAPS preferred.
  Domain-flexible examples:
    Food:         "STICKY GINGER SOY CHICKEN THIGHS"
    Fitness:      "ELEVATED-FOOT BULGARIAN SPLIT SQUAT"
    Finance:      "DOLLAR-COST AVERAGING (DCA), DEMYSTIFIED"
    Productivity: "TIME-BLOCK YOUR DEEP-WORK MORNINGS"
- The "instructions" array contains 9-12 numbered, descriptive entries per item.
  For a recipe these are cooking steps. For a workout they're sets/reps + form
  cues. For finance they're talking points with examples. For productivity they
  are concrete actions. Whatever the domain, the rendered page should LOOK
  full of text, like a real magazine spread.
  Examples by domain:
    Food:         "Sear chicken skin-side down for 6-7 minutes until deeply golden."
    Fitness:      "3 sets × 10 reps per leg, rear foot on a 12-inch bench, 90s rest."
    Finance:      "DCA = invest the same dollar amount every month, regardless of price."
    Productivity: "Block 9-11am as Deep Work. Phone in another room, Slack closed."

PAGE LAYOUT — the compositor renders each item as a 2-column page. The LEFT
column is rendered with the header "INGREDIENTS:" for food briefs OR "OVERVIEW:"
for any other domain. The RIGHT column is rendered with the header
"INSTRUCTIONS:" for food OR "KEY POINTS:" for everything else. Detect the
domain from the brief and write content that fits the appropriate header.

"INGREDIENT_SECTIONS" FIELD (left column — fixed JSON key, do NOT rename):
- FOOD: a printed-cookbook ingredient list. 3-4 grouped sections, 3-6 items
  each, with precise quantities. Section names like "FOR THE BASE", "FOR THE
  SAUCE", "FOR TOPPINGS". Example item: "2 lbs boneless skinless chicken
  thighs, trimmed".
- NON-FOOD: 2-3 sections that give a brief ANALYSIS of the item — overview
  facts, context, why it matters, common pitfalls. 3-5 entries per section
  written as short declarative sentences (not just nouns). Section names
  domain-appropriate:
    Fitness:      "WHY IT MATTERS", "FORM CHECK", "PROGRESSION", "WATCH OUT FOR"
    Finance:      "WHAT IT IS", "WHY IT MATTERS", "COMMON MYTH", "REALITY"
    Productivity: "THE PROBLEM", "THE FIX", "WHEN TO USE IT"
    Lifestyle:    "OVERVIEW", "WHY PEOPLE STRUGGLE", "WHAT ACTUALLY WORKS"
  Example NON-FOOD items (each is a sentence, not a noun):
    Fitness:      "Bench is the king of pressing — but elbow flare wrecks shoulders fast."
    Finance:      "DCA = invest the same amount monthly regardless of price."
    Productivity: "Focus dies the moment you let notifications back in."

"INSTRUCTIONS" FIELD (right column — fixed JSON key, do NOT rename):
- FOOD: 9-12 numbered, descriptive cooking steps with timing/technique cues.
  Example: "Sear chicken skin-side down 6-7 minutes until deeply golden."
- NON-FOOD: 9-12 numbered KEY INSIGHTS, data points, or talking points — not
  step-by-step instructions. Each is a complete thought that stands on its
  own and that the reader could screenshot for later.
  Examples:
    Fitness:      "Most lifters fail because they bench 4× a week. 2× is the sweet spot."
    Finance:      "VTI returned ~10% annualised over the last 30 years."
    Productivity: "Cal Newport's rule: phone in a different room, not just on silent."
    Lifestyle:    "85% of habit failure happens in week 2. Plan a midweek check-in."

TOTAL across both columns: ~20-24 entries per item — dense enough that the
page feels authoritative on its own without the photo slide for context.

HERO IMAGE PROMPTS (for the Nano Banana image generator):
- 30-50 words each. Choose a visual style that matches the domain:
    Food:         warm cinematic food-photography, cast-iron skillet, garnish, steam
    Fitness:      moody gym shot, dramatic side-light, athlete mid-rep, clean lines
    Finance:      minimalist desk flat-lay, notebook + coffee + laptop, soft daylight
    Productivity: tidy workspace, mechanical keyboard, plant, golden-hour window light
    Lifestyle:    editorial lifestyle shot, soft natural light, considered composition
    Tech:         clean product shot on a neutral surface, single key light
- Always restaurant/magazine/editorial quality. Specify lighting, camera angle,
  primary subject, and one or two atmosphere details.

HOOK IMAGE PROMPT:
- Cinematic spread/cover shot that fits the 5-item theme. Adapt the subject to
  the domain (5 dishes for food, training space for fitness, desk-with-chart-
  printouts for finance, etc.). Magazine-cover composition.

CTA CAPTION:
- 2-3 short lines used on a mid-carousel slide. Domain-neutral save prompts —
  e.g. ["Save this carousel before you scroll on.", "Like → Share → Bookmark.",
  "Comes back when you need it."]. The runtime overrides this with a fixed
  brand-safe CTA, so this field is largely informational.
"""

USER_TEMPLATE = """Design a 5-item compilation carousel for the theme: {theme}

Detect the domain (food/fitness/finance/productivity/lifestyle/tech/etc.) from
the theme and adapt every field accordingly — section names, instruction style,
hero image style, hook tone.

Return JSON with EXACTLY this shape:
{{
  "slug": "lowercase_snake_case_max_40_chars",
  "theme": "the theme string back",
  "hook_caption": "the punchy hook line",
  "hook_image_prompt": "...",
  "cta_caption": ["line 1", "line 2", "line 3"],
  "recipes": [
    {{
      "title": "ITEM TITLE IN CAPS",
      "short_pitch": "...",
      "ingredient_sections": [
        {{"name": "<SECTION 1>", "items": ["...", "..."]}},
        {{"name": "<SECTION 2>", "items": ["...", "..."]}}
      ],
      "instructions": ["1. Step or point one...", "2. Step or point two..."],
      "hero_image_prompt": "..."
    }},
    {{ ... 4 more, exactly 5 total ... }}
  ]
}}

The field NAMES (recipes, ingredient_sections, instructions) are fixed for
backwards compatibility — do NOT rename them. Adapt only the CONTENT to fit
the detected domain.
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


_DEFAULT_COMPILATION_MODEL = os.environ.get(
    "GEMINI_COMPILATION_MODEL", "gemini-2.5-flash"
)


def generate_compilation(theme: str, model: Optional[str] = None) -> Compilation:
    """Generate a 5-recipe compilation. Uses Gemini text model (same key as
    Nano Banana) so we don't depend on OpenAI quota.

    The default model is gemini-2.5-flash (a thinking model — high quality
    but 90-150 s on Render). Override with the GEMINI_COMPILATION_MODEL env
    var to use a faster non-thinking model, e.g.:
        export GEMINI_COMPILATION_MODEL=gemini-2.0-flash
    Typical wall-clock savings: 2-3× on the recipe-drafting phase. The
    existing fallback chain (1.5-flash, 2.0-flash) still kicks in on 503/timeout.
    """
    if model is None:
        model = _DEFAULT_COMPILATION_MODEL
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
    # Gemini occasionally returns 4 or 6+ despite the prompt asking for exactly 5.
    # The downstream compositor hardcodes recipes[0..4], so we need exactly 5.
    # If too few → real failure (can't fake recipes). If too many → trim the tail.
    if len(recipes) < 5:
        raise ValueError(
            f"Gemini returned only {len(recipes)} recipes for theme "
            f"{theme!r}; need at least 5. Retry the generation."
        )
    if len(recipes) > 5:
        print(f"  [recipes] Gemini returned {len(recipes)}; trimming to 5")
        recipes = recipes[:5]

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
