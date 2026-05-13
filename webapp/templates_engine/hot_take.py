"""Hot Take / Debate template.

Format: a controversial claim on slide 1, evidence/argument slides, then
"do this instead" closing slide, then final brand CTA.

TikTok-specific format — drives the platform's primary engagement signal:
COMMENTS. People want to argue with hot takes.

No numbered slides. Each evidence point gets a tagged block_card with
"EVIDENCE" / "THE PROOF" / "WHY" style labels.

Slide-position rules:
  Slide 1 (Hook):     THE TAKE. Bold claim. <12 words.
  Slide 2 (Bridge):   "Hear me out..." — defuse instant pushback, preview structure
  Evidence:           each supporting point — block_card with "EVIDENCE" tag
  Penultimate:        the alternative — what to do instead
  Final:              punchy closer
"""
from .registry import Template


SYSTEM_PROMPT = """You design "Hot Take" / Debate carousel content for TikTok. Format:
slide 1 makes a bold, slightly controversial claim. Following slides defend it
with concrete evidence. Penultimate offers the alternative. Final slide is a
mic-drop closer.

Critical: hot takes drive COMMENTS — TikTok's primary engagement signal. Be
slightly provocative but never offensive. The claim should make the viewer
say "wait, what?" or "actually they're right" or "this is wrong" — any of
those drives a comment.

Output ONE valid JSON object.

  hook_caption (Slide 1 = THE TAKE): bold claim, <12 words.
    Examples:
      "Screenshot folders are not a recipe system."
      "Your meal plan died the moment you saved it to camera roll."
      "You don't have a recipe problem. You have a saving problem."

  bridge_caption (Slide 2 = "Hear me out..."):
    Short sentence that defuses pushback + previews what's coming.
    Examples:
      "Before you fight me — here's why."

  evidence (variable count): each = one stacked argument card.
    tag:           ALL CAPS short label. Vary: "EVIDENCE", "THE PROOF",
                   "WHY", "EXHIBIT A", "FACT", "RECEIPT", "THE TRUTH IS"
    title:         a one-line punch — the argument itself
    body:          2-3 sentences supporting it. Specific. Voice-y.
    image_prompt:  cinematic photo that visually supports the argument

  alternative (penultimate = "Here's what works instead"):
    title:   the alternative behavior or product
    body:    1-2 sentences

  final_caption (Slide N): the mic drop. Voice-y.
    Examples:
      "Stop screenshotting. Start saving."
      "I'll wait."
      "Your therapist agrees."

  hashtags: 8-12 relevant tags
  hero_image_prompt: cinematic establishing image for the hook
"""

USER_TEMPLATE = """Generate a Hot Take carousel for:

The take / topic: {topic}
Audience: {audience}
Brand promoted: {brand_name}
Number of evidence slides: {item_count}

JSON shape:
{{
  "hook_caption": "...",
  "hero_image_prompt": "...",
  "bridge_caption": "...",
  "evidence": [
    {{"tag": "EVIDENCE", "title": "...", "body": "...", "image_prompt": "..."}}
    // {item_count} of these
  ],
  "alternative": {{"title": "...", "body": "...", "image_prompt": "..."}},
  "final_caption": "...",
  "hashtags": "..."
}}
"""

TEMPLATE = Template(
    id="hot_take",
    name="Hot Take / Debate",
    description="Bold claim + evidence + alternative + mic drop. TikTok-native. Drives the platform's primary signal: COMMENTS.",
    slide_count_default=7,
    slide_count_min=5,
    slide_count_max=8,
    schema_fields=[
        {"key": "topic", "label": "The take / claim", "type": "text",
         "placeholder": "e.g. screenshot folders are not a recipe system"},
        {"key": "audience", "label": "Audience", "type": "text",
         "placeholder": "e.g. people drowning in saved TikToks"},
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
    out.append({
        "type": "block_card",
        "label": "HEAR ME OUT",
        "title": content.get("bridge_caption", ""),
        "body": "",
        "image_prompt": content["hero_image_prompt"],
    })
    for ev in content.get("evidence", []):
        out.append({
            "type": "block_card",
            "label": ev.get("tag", "EVIDENCE"),
            "title": ev.get("title", ""),
            "body": ev.get("body", ""),
            "image_prompt": ev.get("image_prompt", ""),
        })
    alt = content.get("alternative", {})
    out.append({
        "type": "block_card",
        "label": "DO THIS INSTEAD",
        "title": alt.get("title", ""),
        "body": alt.get("body", ""),
        "image_prompt": alt.get("image_prompt", ""),
    })
    out.append({
        "type": "cta",
        "caption": content.get("final_caption", "I'll wait."),
    })
    return out
