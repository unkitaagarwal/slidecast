"""Quick Tips / Hacks template.

Use case: short actionable tips. Same shape as Top List but tip-styled framing.
"""
from .registry import Template


SYSTEM_PROMPT = """You design viral TikTok/Instagram "Quick Tips" carousels.

Each tip is an actionable do-this. Output ONE valid JSON object, no prose.

  - hook_caption: punchy 1-line headline.
    Examples:
      "5 productivity hacks they don't teach in school"
      "7 finance tips that save me $1000/month"
      "5 sleep hacks that actually work"
  - hero_image_prompt: cinematic establishing photo for the hook
  - tips: list of N objects, each:
      title:        2-4 word action label, like a command. e.g. "Batch your emails"
      body:         2-3 sentences explaining how + why
      image_prompt: cinematic prompt for the slide background
  - cta_caption: 1-line closer pushing toward {cta_target}
  - hashtags: 8-12 relevant tags as one string
"""

USER_TEMPLATE = """Generate {item_count} quick tips for: {topic}

Audience: {audience}
Tone: {tone}

JSON shape:
{{
  "hook_caption": "...",
  "hero_image_prompt": "...",
  "tips": [{{"title": "...", "body": "...", "image_prompt": "..."}}, ...],
  "cta_caption": "...",
  "hashtags": "..."
}}
"""

TEMPLATE = Template(
    id="quick_tips",
    name="Quick Tips & Hacks",
    description="Actionable tips your audience can apply today. Highest save-rate format on TikTok.",
    slide_count_default=7,
    slide_count_min=5,
    slide_count_max=12,
    schema_fields=[
        {"key": "topic", "label": "Topic", "type": "text",
         "placeholder": "e.g. productivity tips for remote workers"},
        {"key": "audience", "label": "Audience", "type": "text",
         "placeholder": "e.g. solopreneurs, ADHD adults, parents"},
        {"key": "tone", "label": "Tone", "type": "select",
         "options": ["edgy", "professional", "friendly", "educational"],
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
    for i, t in enumerate(content["tips"], 1):
        out.append({
            "type": "tip_card",
            "number": i,
            "title": t["title"],
            "body": t["body"],
            "image_prompt": t.get("image_prompt", ""),
        })
    out.append({
        "type": "cta",
        "caption": content.get("cta_caption", ""),
    })
    return out
