"""Curated Favourites / Monthly Picks template.

Format: hook → 5-7 curated picks (each with photo + name + one-line review)
        → soft-CTA bridge slide → final brand CTA.

Slide-position rules applied:
  Slide 1 (Cover):     <10 words, curiosity-driven, "is this for me?"
  Slide 2 (Bridge):    sets the stakes / reduces skepticism
  Middle slides:       each pick = block_card with small "FAV" / "PICK" tag
  Penultimate slide:   soft "save these for later" CTA
  Final slide:         brand card

No big numbers — picks are stacked, not ranked.

Best for:
  - Recurring monthly/weekly content engines
  - High save rate (people save to try later)
  - Affiliate / monetization-friendly
"""
from .registry import Template


SYSTEM_PROMPT = """You design viral "Curated Favourites" carousel content. The format
is a roundup of curated picks — recipes, products, apps, books, whatever the
user's topic is. Each pick is shown as its own slide WITHOUT being ranked or
numbered. Just stacked: pick, pick, pick.

Output ONE valid JSON object. Apply these slide-position rules:

  Slide 1 (hook_caption): Under 10 words. Curiosity-driven.
      Answers "Is this for me?" in the first 5 words.
      Examples:
        "Recipes I'm hoarding this month"
        "Apps I can't stop opening lately"
        "Things saving my dinner this week"

  Slide 2 (bridge_caption): One short sentence that sets stakes / reduces skepticism.
      Examples:
        "Real recipes I've actually made — not just saved."
        "All from creators I trust. None paid to be here."

  Picks (variable count): Each is one stacked card.
      title:        the recipe/product/app name itself (3-7 words)
      body:         WHY this pick — 2 sentences. Specific, no fluff.
      tag:          short label shown above the title — vary across picks
                    so they don't feel identical. Examples for recipe content:
                    "WEEKNIGHT WIN", "5-INGREDIENT", "MUST-TRY", "WEEKEND
                    PROJECT", "PANTRY-RAID FRIENDLY", "FAV", "OBSESSED".
      image_prompt: cinematic, real food photography prompt

  Penultimate (soft_cta_title + soft_cta_body): Save-CTA bridge slide.
      title:   "Save these for next week" (or topic-appropriate variant)
      body:    1-2 sentences nudging the viewer to use the brand to save them

  Final (final_caption): One BANGER closing line. Reward the viewer for swiping to the end.
      Examples:
        "Trust me — your future self will thank you."
        "Screenshot this. Or just open Slidecast. Up to you."

  hashtags: 8-12 relevant tags as one space-separated string

  hero_image_prompt: cinematic establishing-shot photo for the hook slide
"""

USER_TEMPLATE = """Generate a Curated Favourites carousel for: {topic}

Pick count: {item_count}
Audience: {audience}
Brand promoted: {brand_name}

JSON shape:
{{
  "hook_caption": "...",
  "hero_image_prompt": "...",
  "bridge_caption": "...",
  "picks": [
    {{"tag": "...", "title": "...", "body": "...", "image_prompt": "..."}}
    // {item_count} of these
  ],
  "soft_cta_title": "...",
  "soft_cta_body": "...",
  "final_caption": "...",
  "hashtags": "..."
}}
"""

TEMPLATE = Template(
    id="curated_picks",
    name="Curated Favourites",
    description="Stacked picks (no rankings, no numbers). Highest save-rate format. Perfect for recurring monthly/weekly content.",
    slide_count_default=8,  # hook + bridge + 5 picks + soft cta + final
    slide_count_min=4,
    slide_count_max=8,
    schema_fields=[
        {"key": "topic", "label": "Topic / theme", "type": "text",
         "placeholder": "e.g. recipes I'm saving this month, apps I can't stop using"},
        {"key": "audience", "label": "Audience", "type": "text",
         "placeholder": "e.g. home cooks, weeknight-dinner survivors"},
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
    # Bridge slide (slide 2) — sets stakes
    out.append({
        "type": "block_card",
        "label": "WHAT'S INSIDE",
        "title": content.get("bridge_caption", ""),
        "body": "",
        "image_prompt": content["hero_image_prompt"],
    })
    # Picks — each stacked card, NO numbers
    for p in content.get("picks", []):
        out.append({
            "type": "block_card",
            "label": p.get("tag", "FAV"),
            "title": p.get("title", ""),
            "body": p.get("body", ""),
            "image_prompt": p.get("image_prompt", ""),
        })
    # Soft CTA (penultimate)
    bn = (brand or {}).get("name", "your saved feed")
    out.append({
        "type": "block_card",
        "label": "SAVE THIS",
        "title": content.get("soft_cta_title") or f"Keep these in {bn}",
        "body": content.get("soft_cta_body") or
                f"Save the whole carousel — or grab the recipes one-tap with {bn}.",
        "image_prompt": "",
    })
    # Final reward slide + brand CTA
    out.append({
        "type": "cta",
        "caption": content.get("final_caption", "Save them for later."),
    })
    return out
