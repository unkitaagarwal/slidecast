"""
Postiz publisher — upload all slides for each recipe and create draft posts
on the user's connected social accounts.

Usage:
    python3 postiz_publish.py                       # all recipes, drafts on TikTok
    python3 postiz_publish.py --recipe <slug>       # single recipe
    python3 postiz_publish.py --type schedule \\
            --date 2026-05-10T15:00:00.000Z         # schedule instead of draft
    python3 postiz_publish.py --integrations <id>,<id>  # custom target list

By default it targets the TikTok integration found in the user's Postiz
account ("NutriLens" / nutrilens.ai). YouTube is skipped because YouTube
doesn't natively support photo carousels.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Iterable

import requests


API_BASE = "https://api.postiz.com/public/v1"
OUTPUT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "output"))


# ---------------------------------------------------------------------------
# Env loading
# ---------------------------------------------------------------------------


def _load_env() -> None:
    env_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


_load_env()
POSTIZ_KEY = os.environ.get("POSTIZ_API_KEY")
if not POSTIZ_KEY:
    sys.exit("ERROR: POSTIZ_API_KEY missing from .env")


def _headers(json_body: bool = False) -> dict[str, str]:
    h = {"Authorization": POSTIZ_KEY}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


# ---------------------------------------------------------------------------
# Postiz API helpers
# ---------------------------------------------------------------------------


def list_integrations() -> list[dict]:
    r = requests.get(f"{API_BASE}/integrations", headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def upload_image(path: str, retries: int = 4) -> dict:
    """Upload a single image file. Returns {'id', 'path', ...}.
    Retries on transient SSL/connection errors with exponential backoff."""
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with open(path, "rb") as f:
                r = requests.post(
                    f"{API_BASE}/upload",
                    headers=_headers(),
                    files={"file": (os.path.basename(path), f, "image/png")},
                    timeout=120,
                )
            if r.status_code >= 400:
                raise RuntimeError(f"upload failed [{r.status_code}]: {r.text[:300]}")
            return r.json()
        except (requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            last_err = e
            wait = 2 ** attempt
            print(f"      retry {attempt+1}/{retries} after {wait}s ({type(e).__name__})")
            time.sleep(wait)
    raise RuntimeError(f"upload failed after {retries+1} attempts: {last_err}")


def create_post(payload: dict) -> dict:
    r = requests.post(
        f"{API_BASE}/posts",
        headers=_headers(json_body=True),
        json=payload,
        timeout=60,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"create_post failed [{r.status_code}]: {r.text[:500]}")
    return r.json()


# ---------------------------------------------------------------------------
# Caption builder
# ---------------------------------------------------------------------------

# Hashtags pool — we pick a few that match each recipe's keywords.
KEYWORD_HASHTAGS = {
    "wrap":      ["#wraps", "#easywraps"],
    "salad":     ["#saladrecipe", "#freshsalad"],
    "bowl":      ["#bowlrecipe", "#riceboule"],
    "rice":      ["#ricebowl", "#easyrice"],
    "pasta":     ["#pastarecipe", "#easydinner"],
    "shrimp":    ["#shrimprecipe", "#seafood"],
    "chicken":   ["#chickenrecipe", "#chickendinner"],
    "tuna":      ["#tunarecipe", "#highprotein"],
    "salmon":    ["#salmon", "#omega3"],
    "oats":      ["#overnightoats", "#breakfastideas"],
    "berries":   ["#berries"],
    "smoothie":  ["#smoothierecipe"],
    "snack":     ["#healthysnack"],
    "energy":    ["#energybites"],
    "peanut":    ["#peanutbutter"],
    "chocolate": ["#chocolatesnacks"],
    "vegan":     ["#vegan", "#plantbased"],
    "vegetarian": ["#vegetarian"],
    "breakfast": ["#breakfast"],
    "dinner":    ["#easydinner"],
    "lunch":     ["#lunchideas"],
    "dessert":   ["#dessertrecipe"],
    "high-protein": ["#highprotein", "#proteinmeal"],
    "spicy":     ["#spicyfood"],
    "garlic":    ["#garlic"],
    # ── Trending TikTok search keywords (Creator Search Insights) ──
    "sushi":         ["#realsushi", "#sushiathome", "#sushibowl"],
    "mini egg":      ["#minieggs", "#easterbaking", "#minieggdesserts"],
    "easter":        ["#easterbaking"],
    "cookie":        ["#cookierecipe", "#bakingathome"],
    "brown butter":  ["#brownbutter", "#bakingathome"],
    "protein bar":   ["#lunabar", "#proteinbars"],
    "korean":        ["#koreanfood", "#kfood"],
    "tteok":         ["#buttertteok", "#koreanfood"],
    "latte":         ["#heartlatte", "#latteart"],
    "brunch":        ["#brunchideas"],
    "anti-inflammatory": ["#antiinflammatoryfoods", "#guthealth"],
    "new years":     ["#newyearsevenoodles"],
}

DEFAULT_HASHTAGS = ["#recipe", "#easyrecipes", "#healthyfood", "#fyp", "#foodtok"]


def _pick_hashtags(recipe: dict) -> list[str]:
    haystack = (
        recipe.get("title", "") + " " +
        recipe.get("short_pitch", "") + " " +
        " ".join(recipe.get("ingredients", []))
    ).lower()
    tags: list[str] = []
    for kw, hs in KEYWORD_HASHTAGS.items():
        if kw in haystack:
            for t in hs:
                if t not in tags:
                    tags.append(t)
    # Always include defaults at the end
    for t in DEFAULT_HASHTAGS:
        if t not in tags:
            tags.append(t)
    # Cap at 12 to stay readable
    return tags[:12]


_CTA_CAPTION_GENERIC = [
    "Save this carousel before you scroll on.",
    "Like → Share → Bookmark.",
    "Comes back when you need it.",
]

_CTA_CAPTION_RECIPEVAULT = [
    "Here's the trick for saving recipes:",
    "Like > Share > RecipeVault.",
    "That's all it takes to keep the full recipe.",
]


def build_caption(recipe: dict) -> str:
    """Caption builder. The "Ingredients:" dump + RecipeVault CTA is only used
    when the recipe explicitly came from a RecipeVault brief (title or short
    pitch mentions it). Otherwise we emit a clean generic post — title +
    pitch + neutral save prompt + hashtags — with an option to swap in an
    app/link CTA if the user's pitch contains one.
    """
    import re as _re

    title = recipe.get("title", "Recipe")
    pitch = recipe.get("short_pitch", "")
    ingredients = recipe.get("ingredients", [])
    hashtags = " ".join(_pick_hashtags(recipe))

    # Detect "this is a RecipeVault-flavoured post" — checks both the title
    # and the short pitch (which is closest to the user's original brief).
    blob = f"{title} {pitch}".lower()
    is_recipevault = "recipevault" in blob

    # Detect a user-supplied app link / @handle / bare app name in either
    # the pitch or the title. We check URL → @handle → "promo for <Name>".
    blob_for_match = f"{title} {pitch}"
    app_mention = None
    m = _re.search(r"(https?://[^\s)\]\}>,;'\"]+)", blob_for_match)
    if m:
        app_mention = m.group(1)
    else:
        m = _re.search(r"(@[\w.\-]+)", blob_for_match)
        if m:
            app_mention = m.group(1)
        else:
            KEYWORDS = (
                "promo for", "promo by", "promoting", "promote",
                "push for", "advert for", "sponsored by", "sponsoring",
                "shoutout for", "shoutout to",
            )
            blob_lc = blob_for_match.lower()
            for kw in KEYWORDS:
                idx = blob_lc.find(kw)
                if idx < 0:
                    continue
                rest = blob_for_match[idx + len(kw):].lstrip(" -:—")
                mm = _re.match(r"([A-Z][\w.\-]{1,30})", rest)
                if mm:
                    app_mention = mm.group(1)
                    break

    lines = [title]
    if pitch:
        lines.append(pitch)
    lines.append("")

    if is_recipevault:
        # Legacy recipe-dump format — only when it's an actual RecipeVault post
        lines.append("Ingredients:")
        for i in ingredients:
            lines.append(f"- {i}")
        lines.append("")
        lines += _CTA_CAPTION_RECIPEVAULT
    elif app_mention:
        # Personalised CTA mentioning the user's app/link
        lines += [
            "Want more like this?",
            f"Check out {app_mention}",
            "Save this so future-you doesn't have to search.",
        ]
    else:
        lines += _CTA_CAPTION_GENERIC

    lines.append("")
    lines.append(hashtags)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-recipe publisher
# ---------------------------------------------------------------------------


def _slide_paths(recipe_dir: str) -> list[str]:
    sd = os.path.join(recipe_dir, "slides")
    files = sorted(f for f in os.listdir(sd) if f.endswith(".png"))
    return [os.path.join(sd, f) for f in files]


def publish_recipe(
    slug: str,
    *,
    integrations: list[dict],
    post_type: str = "draft",
    date: str | None = None,
) -> list[dict]:
    """Upload slides for one recipe and create posts on each integration.

    Returns a list of {integration_id, post_id} created.
    """
    rdir = os.path.join(OUTPUT_ROOT, slug)
    if not os.path.isdir(rdir):
        raise FileNotFoundError(f"no recipe dir: {rdir}")

    with open(os.path.join(rdir, f"{slug}.json")) as f:
        recipe = json.load(f)

    slides = _slide_paths(rdir)
    if not slides:
        raise RuntimeError(f"no slide PNGs in {rdir}/slides")

    print(f"\n=== {recipe['title']} ({slug}) ===")

    # Prefer the stored caption baked into the JSON (so edits + viral-keyword
    # hashtags stick). Fall back to building one fresh if not present.
    caption = (recipe.get("caption") or "").strip()
    if not caption:
        caption = build_caption(recipe)

    posts_payload = []
    for integ in integrations:
        # Upload a fresh set of media for each integration — Postiz binds
        # uploaded media IDs to a single post object, so reusing the same IDs
        # across multiple integrations in one create_post call causes the
        # second (and any subsequent) integration to fail silently.
        print(f"  uploading {len(slides)} slides for {integ['name']} ...")
        media: list[dict] = []
        for i, path in enumerate(slides, 1):
            m = upload_image(path)
            media.append({"id": m["id"], "path": m["path"]})
            print(f"    [{i:02d}/{len(slides)}] {os.path.basename(path)} -> {m['path']}")
        post_value = {"content": caption, "image": media}
        if integ["identifier"] == "tiktok":
            # UPLOAD mode = post lands in TikTok app's inbox/drafts where the
            # user manually finalizes settings and hits Post. Final caption,
            # privacy, and music can be edited from the TikTok app before
            # publishing. This is the safest review-before-publish flow.
            settings = {
                "__type": "tiktok",
                "title": recipe["title"][:90],
                "privacy_level": "SELF_ONLY",
                "duet": False,
                "stitch": False,
                "comment": True,
                "autoAddMusic": "no",
                "brand_content_toggle": False,
                "brand_organic_toggle": False,
                "video_made_with_ai": True,
                "content_posting_method": "UPLOAD",
            }
        elif integ["identifier"] == "youtube":
            settings = {
                "__type": "youtube",
                "title": recipe["title"][:100],
                "type": "public",
                "selfDeclaredMadeForKids": False,
                "tags": [],
            }
        else:
            settings = {"__type": integ["identifier"]}

        posts_payload.append({
            "integration": {"id": integ["id"]},
            "value": [post_value],
            "settings": settings,
        })

    payload = {
        "type": post_type,
        "date": date or "2026-06-01T12:00:00.000Z",  # required by schema even for drafts
        "shortLink": False,
        "tags": [],
        "posts": posts_payload,
    }
    out = create_post(payload)
    print(f"  created post(s): {out}")
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", help="single recipe slug to publish (default: all)")
    p.add_argument("--type", default="draft",
                   choices=["draft", "schedule", "now"],
                   help="post type")
    p.add_argument("--date",
                   help="ISO date, required for type=schedule")
    p.add_argument("--integrations",
                   help="comma-separated integration ids; default: all TikTok integrations")
    args = p.parse_args()

    all_integrations = list_integrations()
    print("Available integrations:")
    for it in all_integrations:
        print(f"  - {it['name']:24}  ({it['identifier']:10})  id={it['id']}")

    if args.integrations:
        ids = set(args.integrations.split(","))
        target_ints = [i for i in all_integrations if i["id"] in ids]
    else:
        # default: ONLY @nutrilens.ai TikTok account. We deliberately skip the
        # second TikTok ("recipehackswithsusan", whose mobile app needs updating)
        # and YouTube (no carousel support). Pass --integrations <id>,<id> to
        # target a custom list.
        target_ints = [i for i in all_integrations
                       if i["identifier"] == "tiktok" and i["name"] == "NutriLens"]
    if not target_ints:
        sys.exit("No target integrations found.")

    print("\nTargets:")
    for it in target_ints:
        print(f"  -> {it['name']} ({it['identifier']})")

    # Discover recipes
    if args.recipe:
        slugs = [args.recipe]
    else:
        slugs = sorted(d for d in os.listdir(OUTPUT_ROOT)
                       if os.path.isdir(os.path.join(OUTPUT_ROOT, d))
                       and os.path.exists(os.path.join(OUTPUT_ROOT, d, f"{d}.json")))

    print(f"\nPublishing {len(slugs)} recipe(s) as type={args.type} ...")
    results = []
    for slug in slugs:
        try:
            results.append({
                "slug": slug,
                "result": publish_recipe(slug,
                                         integrations=target_ints,
                                         post_type=args.type,
                                         date=args.date),
            })
        except Exception as e:  # noqa: BLE001
            print(f"  !! {slug} FAILED: {e}")
            results.append({"slug": slug, "error": str(e)})
        # be polite to the rate limit
        time.sleep(1)

    print("\nDone.")
    for r in results:
        print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
