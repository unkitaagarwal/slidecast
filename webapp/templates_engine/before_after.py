"""Before / After Transformation template."""
from .registry import Template


SYSTEM_PROMPT = """You design "Before & After transformation" carousels — high emotional
engagement on TikTok/Instagram.

Output ONE valid JSON object.

Fields:
  - hook_caption: punchy headline naming the transformation.
    Examples:
      "I lost 30 lbs in 6 months — here's exactly what I did"
      "From cluttered chaos → minimalist apartment in 30 days"
  - hero_image_prompt: cinematic establishing shot
  - before: { title, body, image_prompt }
      title:  "Where I started"
      body:   2-3 sentences describing the starting state
      image_prompt: cinematic "before" photo
  - process_steps: list of N objects, each:
      title:        what was done (2-5 words)
      body:         2-3 sentences
      image_prompt: cinematic photo of the step in progress
  - after: { title, body, image_prompt }
      title:  "Where I am now"
      body:   2-3 sentences describing the end state
      image_prompt: cinematic "after" photo
  - cta_caption: 1-line closer
  - hashtags: 8-12 relevant tags
"""

USER_TEMPLATE = """Generate a before/after transformation carousel for:

Transformation topic: {topic}
Before state: {before_state}
After state: {after_state}
Process step count: {item_count}
Audience: {audience}
Tone: {tone}

JSON:
{{
  "hook_caption": "...",
  "hero_image_prompt": "...",
  "before": {{"title": "...", "body": "...", "image_prompt": "..."}},
  "process_steps": [
    {{"title": "...", "body": "...", "image_prompt": "..."}},
    // exactly {item_count} of these
  ],
  "after": {{"title": "...", "body": "...", "image_prompt": "..."}},
  "cta_caption": "...",
  "hashtags": "..."
}}
"""

TEMPLATE = Template(
    id="before_after",
    name="Before / After",
    description="Transformation arc: before state → 3-5 process steps → after state. Strong emotional pull.",
    slide_count_default=7,
    slide_count_min=5,
    slide_count_max=9,
    schema_fields=[
        {"key": "topic", "label": "Transformation topic", "type": "text",
         "placeholder": "e.g. weight loss, room makeover, business growth"},
        {"key": "before_state", "label": "Before state (where you started)", "type": "text",
         "placeholder": "e.g. 220 lbs, eating fast food daily"},
        {"key": "after_state", "label": "After state (where you ended up)", "type": "text",
         "placeholder": "e.g. 175 lbs, meal prepping every Sunday"},
        {"key": "audience", "label": "Audience", "type": "text",
         "placeholder": "e.g. anyone struggling with the same issue"},
        {"key": "tone", "label": "Tone", "type": "select",
         "options": ["edgy", "inspirational", "friendly", "professional"],
         "default": "inspirational"},
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
    n_steps = len(content["process_steps"])
    out.append({"type": "block_card",
                "label": "BEFORE",
                "title": content["before"]["title"],
                "body": content["before"]["body"],
                "image_prompt": content["before"].get("image_prompt", "")})
    for i, step in enumerate(content["process_steps"], 1):
        # Story-arc style — "STEP X of N" small tag, NOT a giant numbered card.
        # Keeps the visual rhythm of the BEFORE/AFTER slides.
        out.append({"type": "block_card",
                    "label": f"STEP {i} OF {n_steps}",
                    "title": step["title"],
                    "body": step["body"],
                    "image_prompt": step.get("image_prompt", "")})
    out.append({"type": "block_card",
                "label": "AFTER",
                "title": content["after"]["title"],
                "body": content["after"]["body"],
                "image_prompt": content["after"].get("image_prompt", "")})
    out.append({"type": "cta",
                "caption": content.get("cta_caption", "")})
    return out
