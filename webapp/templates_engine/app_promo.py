"""App / Product Promo template — direct marketing for an app or product.

Slide structure (fixed at ~8 slides):
  1. Hook
  2. Problem (the pain your audience feels)
  3. Solution intro (your app/product)
  4-6. 3 key features
  7. Social proof (testimonial or stat)
  8. CTA
"""
from .registry import Template


SYSTEM_PROMPT = """You design "I built an app" promo carousels — direct response copy
optimized for app downloads or product clicks.

Output ONE valid JSON object.

Fields:
  - hook_caption: scroll-stopping hook tying problem + product in 1 line.
    Examples:
      "I built an app that saves 10 recipes per day"
      "Stop losing your TikTok recipes — this app fixes it"
  - hero_image_prompt: cinematic establishing shot (no UI screenshot — that's later)
  - problem: { title, body, image_prompt }
      title:  blunt pain statement (e.g. "Lost recipe screenshots = wasted dinners")
      body:   2-3 sentences naming the specific pain
      image_prompt: visual representing the pain
  - solution: { title, body, image_prompt }
      title:  "Meet {app_name}" or similar
      body:   1-sentence what-it-does
      image_prompt: app-on-phone cinematic shot
  - features: exactly 3 objects, each:
      title:  feature name (3-5 words)
      body:   2 sentences on what it does + the benefit
      image_prompt: visual for the feature
  - social_proof: { title, body, image_prompt }
      title: "Reviews are insane" / "Users say…" / "12K downloads in week 1"
      body: a quoted-style testimonial or stat (you can invent a plausible one — user will edit)
      image_prompt: happy user / 5-star reviews / press logos visual
  - cta_caption: closer pushing download or click
  - hashtags: 8-12 relevant tags
"""

USER_TEMPLATE = """Generate an app/product promo carousel for:

App / product name: {app_name}
What it does: {app_description}
Main pain it solves: {pain_point}
Audience: {audience}
Tone: {tone}

JSON:
{{
  "hook_caption": "...",
  "hero_image_prompt": "...",
  "problem": {{"title": "...", "body": "...", "image_prompt": "..."}},
  "solution": {{"title": "...", "body": "...", "image_prompt": "..."}},
  "features": [
    {{"title": "...", "body": "...", "image_prompt": "..."}},
    {{"title": "...", "body": "...", "image_prompt": "..."}},
    {{"title": "...", "body": "...", "image_prompt": "..."}}
  ],
  "social_proof": {{"title": "...", "body": "...", "image_prompt": "..."}},
  "cta_caption": "...",
  "hashtags": "..."
}}
"""

TEMPLATE = Template(
    id="app_promo",
    name="App / Product Promo",
    description="Direct-response carousel for any app or product. Hook → problem → solution → features → social proof → download.",
    slide_count_default=8,
    slide_count_min=8,
    slide_count_max=8,
    schema_fields=[
        {"key": "app_name", "label": "App / product name", "type": "text",
         "placeholder": "RecipeVault"},
        {"key": "app_description", "label": "What it does (1 sentence)", "type": "text",
         "placeholder": "Save TikTok recipes with one tap"},
        {"key": "pain_point", "label": "Main pain it solves", "type": "text",
         "placeholder": "Recipes lost in screenshot folders"},
        {"key": "audience", "label": "Audience", "type": "text",
         "placeholder": "Home cooks scrolling TikTok"},
        {"key": "tone", "label": "Tone", "type": "select",
         "options": ["edgy", "professional", "friendly"],
         "default": "friendly"},
    ],
    system_prompt=SYSTEM_PROMPT,
    user_template=USER_TEMPLATE,
)


def slide_specs(content: dict, brand: dict) -> list[dict]:
    out = [{
        "type": "hook",
        "caption": content["hook_caption"],
        "image_prompt": content["hero_image_prompt"],
    }]
    out.append({"type": "block_card",
                "label": "THE PROBLEM",
                "title": content["problem"]["title"],
                "body": content["problem"]["body"],
                "image_prompt": content["problem"].get("image_prompt", "")})
    out.append({"type": "block_card",
                "label": "THE SOLUTION",
                "title": content["solution"]["title"],
                "body": content["solution"]["body"],
                "image_prompt": content["solution"].get("image_prompt", "")})
    for i, f in enumerate(content["features"], 1):
        out.append({"type": "feature_card",
                    "number": i,
                    "title": f["title"],
                    "body": f["body"],
                    "image_prompt": f.get("image_prompt", "")})
    out.append({"type": "block_card",
                "label": "SOCIAL PROOF",
                "title": content["social_proof"]["title"],
                "body": content["social_proof"]["body"],
                "image_prompt": content["social_proof"].get("image_prompt", "")})
    out.append({"type": "cta",
                "caption": content.get("cta_caption", "")})
    return out
