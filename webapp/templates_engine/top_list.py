"""Top 5 / Top 10 list template.

Use case: "5 things I wish I knew", "10 must-have apps", "Top 7 mistakes"
Layout: hook + N numbered list cards + cta
"""
from .registry import Template


SYSTEM_PROMPT = """You design viral TikTok/Instagram carousel "Top N list" content.

Your output:
  - hook_caption: a punchy, slightly edgy 1-line headline.
    Examples:
      "5 apps every founder NEEDS in 2026"
      "Top 10 hacks for sleeping 8 hours a night"
      "5 mistakes I made in my first year — don't repeat them"
  - items: list of N objects. Each item has:
      title:      a 3-7 word headline for the item
      body:       2-3 short sentences that explain it — concrete, no fluff
      image_prompt: a cinematic photo prompt for the slide background
                    (real photo, dramatic lighting, depth of field, subject in focus)
  - hero_image_prompt: a cinematic establishing-shot prompt for the hook slide
  - cta_caption: a 1-line closer pushing the user to {cta_target}
  - hashtags: 8-12 relevant hashtags as a single string

Always output ONE valid JSON object, no prose."""

USER_TEMPLATE = """Generate a top {item_count}-item carousel for: {topic}

Audience: {audience}
Tone: {tone}

Return JSON shaped exactly like:
{{
  "hook_caption": "...",
  "hero_image_prompt": "...",
  "items": [
    {{"title": "...", "body": "...", "image_prompt": "..."}}
    // exactly {item_count} of these
  ],
  "cta_caption": "...",
  "hashtags": "#tag1 #tag2 ..."
}}
"""

TEMPLATE = Template(
    id="top_list",
    name="Top 5 / Top 10 List",
    description="Most universal viral format. Numbered list of picks, tips, or mistakes. Works for any niche.",
    slide_count_default=7,
    slide_count_min=5,
    slide_count_max=12,
    schema_fields=[
        {"key": "topic", "label": "Topic / theme", "type": "text",
         "placeholder": "e.g. 5 productivity apps for ADHD"},
        {"key": "audience", "label": "Audience", "type": "text",
         "placeholder": "e.g. busy founders, fitness beginners"},
        {"key": "tone", "label": "Tone", "type": "select",
         "options": ["edgy", "professional", "friendly", "educational"],
         "default": "edgy"},
    ],
    system_prompt=SYSTEM_PROMPT,
    user_template=USER_TEMPLATE,
)


def slide_specs(content: dict, brand: dict) -> list[dict]:
    """Translate Gemini's content JSON into a slide-by-slide render plan."""
    out = [{
        "type": "hook",
        "caption": content["hook_caption"],
        "image_prompt": content["hero_image_prompt"],
    }]
    for i, item in enumerate(content["items"], 1):
        out.append({
            "type": "list_card",
            "number": i,
            "title": item["title"],
            "body": item["body"],
            "image_prompt": item.get("image_prompt", ""),
        })
    out.append({
        "type": "cta",
        "caption": content.get("cta_caption", ""),
    })
    return out
