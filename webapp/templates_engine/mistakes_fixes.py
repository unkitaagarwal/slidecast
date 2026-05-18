"""Mistakes & Fixes template — high save-rate viral format."""
from .registry import Template


SYSTEM_PROMPT = """You design "5 mistakes & fixes" carousels — viral on TikTok.

Each pair has a Mistake and a Fix (Do this instead). Output ONE valid JSON object.

  - hook_caption: scroll-stopping 1-liner.
    Examples:
      "5 skincare mistakes ruining your face"
      "5 mistakes killing your savings (do this instead)"
  - hero_image_prompt: cinematic establishing photo
  - pairs: list of N objects, each:
      mistake_title: 3-6 words, blunt — "Sleeping 5 hours"
      mistake_body: 1-2 sentences explaining the mistake
      fix_title:    3-6 words — "Sleep 7-9 hours"
      fix_body:     1-2 sentences explaining the better approach
      image_prompt: photo prompt for the slide background
  - cta_caption: 1-line closer
  - hashtags: 8-12 relevant tags
"""

USER_TEMPLATE = """Generate {item_count} mistake/fix pairs for: {topic}

Audience: {audience}
Tone: {tone}

JSON:
{{
  "hook_caption": "...",
  "hero_image_prompt": "...",
  "pairs": [
    {{"mistake_title": "...", "mistake_body": "...",
      "fix_title": "...", "fix_body": "...",
      "image_prompt": "..."}}
  ],
  "cta_caption": "...",
  "hashtags": "..."
}}
"""

TEMPLATE = Template(
    id="mistakes_fixes",
    name="Mistakes & Fixes",
    description="One slide per (mistake → do this instead) pair. Viewers save these to avoid the mistakes.",
    slide_count_default=7,
    slide_count_min=5,
    slide_count_max=10,
    schema_fields=[
        {"key": "topic", "label": "Topic", "type": "text",
         "placeholder": "e.g. skincare mistakes, marketing mistakes"},
        {"key": "audience", "label": "Audience", "type": "text",
         "placeholder": "e.g. people new to investing"},
        {"key": "tone", "label": "Tone", "type": "select",
         "options": ["edgy", "professional", "friendly", "educational"],
         "default": "edgy"},
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
    for i, p in enumerate(content["pairs"], 1):
        out.append({
            "type": "mistake_fix",
            "number": i,
            "mistake_title": p["mistake_title"],
            "mistake_body": p["mistake_body"],
            "fix_title": p["fix_title"],
            "fix_body": p["fix_body"],
            "image_prompt": p.get("image_prompt", ""),
        })
    out.append({
        "type": "cta",
        "caption": content.get("cta_caption", ""),
    })
    return out
