"""Day in the Life / Routine Breakdown template.

Format: hook → time-tagged moments through the day → soft-CTA bridge → final brand CTA.

Highest retention format per the research — viewers want to see how it ends.
Builds parasocial trust → strong follower-conversion signal.

Each moment slide uses a TIME tag (e.g. "7AM" / "MORNING" / "MIDDAY") instead
of a number, so the deck reads like a journal, not a listicle.

Slide-position rules:
  Slide 1 (Cover):    <10 words, voice-y, sets the day
  Slide 2 (Bridge):   one-line context — what's this routine for
  Moments:            block_cards with time-label + moment title + body
  Penultimate:        soft "build your own routine with X" CTA
  Final:              reward — the punchline of the day
"""
from .registry import Template


SYSTEM_PROMPT = """You design "Day in the Life" or "Routine" carousel content. Format:
a swipe-through of moments in a single day, each with a time-tag (or chunk
of day) instead of a number. Voice should feel personal, voice-y, journal-ish.
NOT a numbered listicle.

Output ONE valid JSON object. Apply these slide-position rules:

  Slide 1 (hook_caption): Under 10 words. Voice-y, sets the day.
      Examples:
        "A day of dinners that almost cooked themselves"
        "My most-saved recipes, eaten in one day"
        "How I plan a full week of meals in 5 minutes"

  Slide 2 (bridge_caption): One sentence of context — who this is for / why.
      Examples:
        "I used to scroll Uber Eats every night. Here's what I do now."

  Moments (variable count): Each is one stacked card representing a chunk of the day.
      time_label:   the time or part of day, ALL CAPS — vary across moments.
                    Examples:
                      "7 AM", "MORNING", "10 AM", "MIDDAY", "12 PM",
                      "AFTERNOON LOW", "5 PM PANIC", "DINNER TIME",
                      "9 PM WIND-DOWN", "MIDNIGHT SNACK"
      title:        what happened — a recipe name, a moment, an activity
      body:         2-3 sentences. Personal voice, specific details, low fluff.
      image_prompt: cinematic, real photo prompt (food, hands, kitchen)

  Penultimate (soft_cta_title + soft_cta_body): Soft save-this CTA.
      title:    "Build your own week in 5 minutes"
      body:     1-2 lines nudging the user toward your brand to plan/save

  Final (final_caption): The closing punchline. Reward swipers.
      Examples:
        "And that's how I stopped eating cold cereal for dinner."
        "Save this carousel. Or just steal my whole rotation."

  hashtags: 8-12 relevant tags
  hero_image_prompt: cinematic establishing-shot photo of the day
"""

USER_TEMPLATE = """Generate a Day in the Life carousel for: {topic}

Number of moments: {item_count}
Audience: {audience}
Brand promoted: {brand_name}

JSON shape:
{{
  "hook_caption": "...",
  "hero_image_prompt": "...",
  "bridge_caption": "...",
  "moments": [
    {{"time_label": "7 AM", "title": "...", "body": "...", "image_prompt": "..."}}
    // {item_count} of these, each with a different time_label progressing through the day
  ],
  "soft_cta_title": "...",
  "soft_cta_body": "...",
  "final_caption": "...",
  "hashtags": "..."
}}
"""

TEMPLATE = Template(
    id="day_in_life",
    name="Day in the Life",
    description="Time-tagged journal of one day. Highest-retention format. Builds parasocial trust → drives follows.",
    slide_count_default=8,
    slide_count_min=5,
    slide_count_max=9,
    schema_fields=[
        {"key": "topic", "label": "What kind of day?", "type": "text",
         "placeholder": "e.g. a day of dinners, my week of meal-prep, a Sunday cook-along"},
        {"key": "audience", "label": "Audience", "type": "text",
         "placeholder": "e.g. busy weeknight cooks, working parents"},
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
        "label": "THE ROUTINE",
        "title": content.get("bridge_caption", ""),
        "body": "",
        "image_prompt": content["hero_image_prompt"],
    })
    for m in content.get("moments", []):
        out.append({
            "type": "block_card",
            "label": m.get("time_label", "MOMENT"),
            "title": m.get("title", ""),
            "body": m.get("body", ""),
            "image_prompt": m.get("image_prompt", ""),
        })
    bn = (brand or {}).get("name", "your routine")
    out.append({
        "type": "block_card",
        "label": "YOUR TURN",
        "title": content.get("soft_cta_title") or f"Build your week in 5 minutes",
        "body": content.get("soft_cta_body") or
                f"Save these recipes one-tap with {bn} and plan the whole week from your phone.",
        "image_prompt": "",
    })
    out.append({
        "type": "cta",
        "caption": content.get("final_caption", "Save this for next week."),
    })
    return out
