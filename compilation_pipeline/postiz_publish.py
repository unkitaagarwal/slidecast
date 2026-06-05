"""Postiz publisher for COMPILATION carousels (12-slide format).

Mirrors pipeline/postiz_publish.py but:
  - Uploads 12 slides per carousel (not 10)
  - Uses a SHORT, clean caption (not ingredient dump)
  - Includes #RecipeVault and curated viral hashtags
  - Lands in TikTok inbox via content_posting_method=UPLOAD

Usage:
    python3 compilation_pipeline/postiz_publish.py                       # all comps -> NutriLens TikTok inbox
    python3 compilation_pipeline/postiz_publish.py --slug <slug>         # single compilation
    python3 compilation_pipeline/postiz_publish.py --type schedule --date <ISO>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import requests


API_BASE = "https://api.postiz.com/public/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTPUT_ROOT = os.path.join(ROOT, "output_compilations")
PUBLISHED_LOG = os.path.join(OUTPUT_ROOT, "published.json")


# ---------------------------------------------------------------------------
# Env loading
# ---------------------------------------------------------------------------

def _load_env() -> None:
    env_path = os.path.join(ROOT, ".env")
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
# Publish-state tracker — prevents duplicate posts
# ---------------------------------------------------------------------------


def _load_published() -> dict:
    if os.path.exists(PUBLISHED_LOG):
        with open(PUBLISHED_LOG) as f:
            return json.load(f)
    return {}


def _save_published(data: dict) -> None:
    os.makedirs(os.path.dirname(PUBLISHED_LOG), exist_ok=True)
    with open(PUBLISHED_LOG, "w") as f:
        json.dump(data, f, indent=2)


def _mark_published(slug: str, post_type: str, response: object) -> None:
    data = _load_published()
    data[slug] = {
        "published_at": datetime.now(timezone.utc).isoformat(),
        "post_type": post_type,
    }
    _save_published(data)


def is_already_published(slug: str) -> bool:
    return slug in _load_published()


# ---------------------------------------------------------------------------
# Postiz API helpers
# ---------------------------------------------------------------------------

def list_integrations() -> list[dict]:
    r = requests.get(f"{API_BASE}/integrations", headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def upload_image(path: str, retries: int = 4) -> dict:
    """Upload a single image with retries on transient errors."""
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
    r = requests.post(f"{API_BASE}/posts", headers=_headers(json_body=True),
                      json=payload, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"create_post [{r.status_code}]: {r.text[:600]}")
    return r.json()


# ---------------------------------------------------------------------------
# Caption + hashtags — short, clean, conversion-oriented
# ---------------------------------------------------------------------------

# Theme keyword → relevant hashtags. The first matching keyword's tags get
# inserted before the universal tags so each carousel has theme-specific reach.
THEME_HASHTAGS = {
    # Audience / relationship
    "wife":         ["#dinnersforhusbands", "#cookforyourwife", "#wifelife"],
    "husband":      ["#dinnersforwives", "#cookforyourhusband", "#husbandapproved"],
    "boyfriend":    ["#dinnersforhim", "#datenightdinner"],
    "girlfriend":   ["#dinnersforher", "#datenightdinner"],
    "couples":      ["#couplelife", "#datenightdinner"],
    "roommate":     ["#roommatelife"],
    "moms":         ["#momlife", "#dinnerideasformoms"],
    "mom":          ["#momlife", "#dinnerideasformoms"],
    "single dad":   ["#singledadlife"],
    "kids":         ["#kidfriendly", "#familydinner"],
    "family":       ["#familydinner", "#familymeals"],
    "broke":        ["#cheapeats", "#budgetmeals", "#cheapdinners"],
    "college":      ["#collegelife", "#cheapeats", "#dormcooking"],
    # Effort / vibe
    "lazy":         ["#lazydinners", "#lazygirldinner"],
    "tired":        ["#lazydinners", "#easydinners"],
    "exhausted":    ["#lazydinners", "#easydinners"],
    "easy":         ["#easyrecipes", "#easydinner"],
    "beginner":     ["#beginnercook", "#easyrecipes"],
    "5 ingredient": ["#5ingredientdinners", "#fiveingredients", "#minimalingredients"],
    "5-ingredient": ["#5ingredientdinners", "#fiveingredients", "#minimalingredients"],
    "fancy":        ["#fancydinner", "#impressivemeals"],
    "one-pan":      ["#onepan", "#onepandinners", "#sheetpan"],
    "one pan":      ["#onepan", "#onepandinners", "#sheetpan"],
    "no dishes":    ["#onepan", "#minimalcleanup"],
    "30-minute":    ["#30minutemeals", "#quickdinner"],
    "30 minute":    ["#30minutemeals", "#quickdinner"],
    "20-minute":    ["#20minutemeals", "#quickdinner"],
    "quick":        ["#quickdinner", "#quickmeals"],
    "last-minute":  ["#lastminutedinner", "#pantrymeals"],
    "last minute":  ["#lastminutedinner", "#pantrymeals"],
    "fridge":       ["#fridgedinner", "#leftovers", "#pantrymeals"],
    "tonight":      ["#tonightsdinner", "#whatscooking"],
    "no plan":      ["#tonightsdinner", "#whatscooking"],
    "no bother":    ["#lazydinners", "#easydinners"],
    "zero effort":  ["#lazydinners", "#easydinners"],
    # Time of day / week
    "weekend":      ["#weekendvibes", "#weekendcooking"],
    "weeknight":    ["#weeknightdinner", "#easydinners"],
    "sunday":       ["#sundaymealprep", "#mealprep"],
    "meal prep":    ["#mealprep", "#mealprepideas"],
    "midnight":     ["#latenighteats", "#midnightsnack"],
    "brunch":       ["#brunchideas", "#brunch"],
    "friday":       ["#fridaynight", "#weekendvibes"],
    "monday":       ["#mondaymotivation"],
    "5pm panic":    ["#whatscooking", "#tonightsdinner"],
    # Mood / vibe
    "cozy":         ["#cozyseason", "#cozydinner"],
    "solo":         ["#solodinner", "#dinnerforone"],
    "alone":        ["#solodinner", "#dinnerforone"],
    "main character": ["#maincharacterenergy", "#solodinner"],
    "comfort":      ["#comfortfood", "#cozydinner"],
    "quiet":        ["#cozydinner"],
    "rainy":        ["#cozyseason", "#cozydinner"],
    # Health / dietary
    "gym":          ["#gymdinners", "#highprotein", "#postworkoutmeal"],
    "high-protein": ["#highprotein", "#proteinrich"],
    "high protein": ["#highprotein", "#proteinrich"],
    "girl dinner":  ["#girldinner", "#girldinners"],
    "vegetarian":   ["#vegetarian", "#meatlessmeals"],
    "vegan":        ["#vegan", "#plantbased"],
    "hangover":     ["#hangoverfood", "#hangovercure"],
    "period":       ["#periodfood"],
    "post-breakup": ["#breakuprecovery"],
    "breakup":      ["#breakuprecovery"],
    "post-workout": ["#postworkoutmeal"],
    "post-gym":     ["#postworkoutmeal", "#highprotein"],
    "sick":         ["#comfortfood", "#sickdaymeals"],
    "low-carb":     ["#lowcarb", "#keto"],
    "anti-inflam":  ["#antiinflammatory", "#guthealth"],
    "gut":          ["#guthealth", "#guthealing"],
    "weight":       ["#weightloss", "#healthyrecipes"],
    "mediterranean":["#mediterraneandiet", "#mediterranean"],
    "anti-bloat":   ["#antibloat", "#guthealth"],
    "bloat":        ["#antibloat", "#guthealth"],
    "calorie":      ["#lowcalorie", "#weightloss"],
    "glow up":      ["#glowupmeals", "#mediterranean"],
    "therapy":      ["#mentalhealthmeals"],
    # Cuisines
    "korean":       ["#koreanfood", "#kfood"],
    "italian":      ["#italianfood", "#italianrecipes"],
    "mexican":      ["#mexicanfood", "#tacos"],
    "thai":         ["#thaifood", "#thairecipe"],
    "indian":       ["#indianfood", "#indianrecipes"],
    "japanese":     ["#japanesefood"],
    # Trending / niche
    "viral":        ["#viralrecipe", "#trendingrecipe"],
    "tiktok":       ["#tiktokrecipes", "#tiktokfood"],
    "dense bean":   ["#densebeansalad"],
    "cottage":      ["#cottagecheese"],
    "fast food":    ["#fastfooddupe", "#highproteindupe"],
    "trader joe":   ["#traderjoes"],
    "summer":       ["#summerrecipes"],
    "fall":         ["#fallfood", "#cozyseason"],
    "winter":       ["#winterfood", "#cozyseason"],
    "spring":       ["#springfood"],
    "takeout":      ["#betterthantakeout", "#takeoutathome"],
    "uber eats":    ["#betterthantakeout"],
    "save money":   ["#cheapeats", "#budgetmeals"],
    "save ":        ["#cheapeats", "#budgetmeals"],
    "save you":     ["#cheapeats", "#budgetmeals"],
    "pinterest":    ["#pinterestrecipes"],
    "pov":          ["#povtiktok"],
    "stop making":  ["#cookingmistakes"],
    "never make":   ["#cookingmistakes"],
    "in-laws":      ["#dinnerparty", "#impressivemeals"],
    "guests":       ["#dinnerparty"],
    "date night":   ["#datenightdinner"],
    "valentine":    ["#valentinesday", "#datenightdinner"],
    "anniversary":  ["#anniversarydinner", "#datenightdinner"],
    "gameday":      ["#gameday", "#superbowl"],
    "game day":     ["#gameday", "#superbowl"],
    "holiday":      ["#holidayrecipes"],
    "birthday":     ["#birthdaydinner"],
    "potluck":      ["#potluckideas"],

    # ── Currently-viral keywords from TikTok Creator Search Insights ──
    "sushi":           ["#realsushi", "#sushiathome", "#sushibowl"],
    "pizza hut":       ["#pizzahutoriginal", "#pizzacopycat"],
    "protein bar":     ["#lunabar", "#proteinbars", "#homemadeproteinbars"],
    "luna":            ["#lunabar", "#proteinbars"],
    "korean":          ["#koreanfood", "#kfood", "#buttertteok", "#tteokbokki"],
    "tteok":           ["#buttertteok", "#tteokbokki", "#koreanfood"],
    "new years":       ["#newyearsevenoodles", "#luckynoodles", "#nye"],
    "noodle":          ["#newyearsevenoodles", "#noodlerecipe"],
    "anti-inflammatory": ["#antiinflammatoryfoods", "#guthealth", "#guthealing"],
    "anti inflam":     ["#antiinflammatoryfoods", "#guthealth"],
    "mini egg":        ["#minieggs", "#minieggdesserts", "#easterbaking"],
    "easter":          ["#easterbaking", "#easterrecipes"],
    "heart latte":     ["#heartlatte", "#latteart", "#coffeeathome"],
    "latte":           ["#heartlatte", "#latteart", "#coffeeathome"],
    "brunch":          ["#brunchideas", "#brunchrecipes"],
    "tuna":            ["#tunarecipes", "#tunabowl"],
    "cookie":          ["#cookierecipe", "#bakingathome"],
}

# Domain-specific hashtag banks. The first matching domain's pack is used as
# the "universal" tail of hashtags for the compilation. Falls back to the
# generic save-magnet pack when no domain is detected.
_DOMAIN_HASHTAGS = {
    "food": [
        "#cookwithme", "#mealideas", "#recipeideas", "#whattocook",
        "#Recipe", "#DinnerIdeas", "#EasyRecipe", "#comfortfood",
        "#foodtok", "#fyp",
    ],
    "fashion": [
        "#OOTD", "#styleinspo", "#wardrobeessentials", "#capsulewardrobe",
        "#fashiontiktok", "#stylehacks", "#GetReadyWithMe", "#fyp",
    ],
    "fitness": [
        "#fittok", "#gymtok", "#workoutroutine", "#fitnesstips",
        "#healthandfitness", "#strengthtraining", "#gymmotivation", "#fyp",
    ],
    "finance": [
        "#moneytok", "#fintok", "#personalfinance", "#investingtips",
        "#financialfreedom", "#moneymatters", "#wealthbuilding", "#fyp",
    ],
    "productivity": [
        "#productivitytips", "#productivityhacks", "#worksmarter",
        "#deepwork", "#focustime", "#timemanagement", "#fyp",
    ],
    "lifestyle": [
        "#lifestyletips", "#dailyhabits", "#selfcare", "#wellnesstok",
        "#mindfulness", "#routinetok", "#fyp",
    ],
    "tech": [
        "#techtok", "#techhacks", "#productivityapps", "#apps",
        "#techreview", "#tech", "#fyp",
    ],
}

# Backwards-compatible alias — older code paths that imported this constant
# still work, but new code should call _pick_hashtags() and let it pick the
# right bank based on the brief.
UNIVERSAL_HASHTAGS = ["#RecipeVault"] + _DOMAIN_HASHTAGS["food"]


# Domain keywords. Order matters — we pick the first domain whose keyword
# fires. "food" stays the default for backward compatibility with the recipe
# library, so non-food domains need decent keyword coverage to win.
_DOMAIN_KEYWORDS = {
    "fashion":      ("wardrobe", "outfit", "ootd", "style", "fashion", "clothing", "clothes",
                     "closet", "accessor", "shoe", "boot", "dress ", "jeans", "denim",
                     "capsule"),
    "fitness":      ("workout", "gym", "lift", "bench", "squat", "deadlift", "cardio",
                     "training", "exercise", "muscle", "fitness", "stretch", "yoga",
                     "pilates", "running"),
    "finance":      ("invest", "money", "budget", "saving", "stock", "index fund",
                     "etf", "401k", "ira", "personal finance", "wealth", "debt",
                     "credit score", "tax", "salary", "income"),
    "productivity": ("productivity", "focus", "deep work", "time block", "habit",
                     "morning routine", "evening routine", "workflow", "to-do",
                     "schedule", "calendar", "task management"),
    "tech":         ("app", "software", "saas", "tool", "tech", "ai ", "extension",
                     "plugin", "developer", "coding", "automation"),
    "lifestyle":    ("self-care", "selfcare", "wellness", "mindful", "meditat",
                     "journal", "minimalis", "declutter", "sleep ", "rest",
                     "anxiety", "stress"),
    "food":         ("recipe", "dinner", "lunch", "breakfast", "snack", "meal",
                     "cooking", "cook ", "bake", "pantry", "kitchen", "ingredient",
                     "dish", "cuisine", "appetiz", "dessert"),
}


def _detect_domain(haystack: str) -> str:
    """Return the matched domain key for the given lowercased haystack.

    Walks _DOMAIN_KEYWORDS in declared order so non-food domains win over
    "food" when their keywords appear. Falls back to "food" if nothing
    matches — preserves existing behaviour on legacy recipe carousels."""
    for domain, kws in _DOMAIN_KEYWORDS.items():
        if any(k in haystack for k in kws):
            return domain
    return "food"


def _app_to_hashtag(app: Optional[str]) -> Optional[str]:
    """Convert a detected app mention into a hashtag.

    "Nutrilens"           -> "#Nutrilens"
    "@focuskit"           -> "#focuskit"
    "https://x.app/path"  -> "#x"
    """
    if not app:
        return None
    val = app.strip().lstrip("@")
    if val.startswith(("http://", "https://")):
        host = val.split("://", 1)[1].split("/", 1)[0]
        val = host.split(".", 1)[0]
    val = val.split(".", 1)[0]
    val = "".join(c for c in val if c.isalnum())
    return f"#{val}" if val else None


def _pick_hashtags(comp: dict) -> list[str]:
    haystack = (
        comp.get("hook_caption", "") + " " +
        comp.get("theme", "") + " " +
        " ".join(r.get("title", "") for r in comp.get("recipes", []))
    ).lower()
    domain = _detect_domain(haystack)
    tags: list[str] = []

    # 1. User-app hashtag wins the lead slot when detected
    app_tag = _app_to_hashtag(_detect_app_mention(comp))
    if app_tag:
        tags.append(app_tag)

    # 2. RecipeVault hashtag only when the brief is explicitly recipevault-flavoured
    if "recipevault" in haystack:
        tags.append("#RecipeVault")

    # 3. Theme-keyword tags (food-only bank, only fires for food domain)
    if domain == "food":
        for kw, hs in THEME_HASHTAGS.items():
            if kw in haystack:
                for t in hs:
                    if t not in tags:
                        tags.append(t)

    # 4. Universal-by-domain hashtags
    for t in _DOMAIN_HASHTAGS.get(domain, _DOMAIN_HASHTAGS["lifestyle"]):
        if t not in tags:
            tags.append(t)

    # Cap at 14 tags total — TikTok still ranks if there are too many
    return tags[:14]


# Small bank of opener emojis to keep posts looking varied
_OPENER_EMOJIS = ["😏", "😅", "🤤", "👀", "💕", "🍳", "✨"]


# Generic save-magnet CTA used for any non-RecipeVault carousel.
_CTA_CAPTION_GENERIC = [
    "Save this carousel before you scroll on.",
    "Like → Share → Bookmark.",
    "Comes back when you need it.",
]

# RecipeVault-flavoured CTA. Only used when the user's brief (theme) mentions
# RecipeVault, so we don't accidentally promote the recipe app on a finance
# or fitness carousel.
_CTA_CAPTION_RECIPEVAULT = [
    "Here's the trick for saving recipes:",
    "Like > Share > RecipeVault.",
    "That's all it takes to keep the full recipe.",
]


def _detect_app_mention(comp: dict) -> Optional[str]:
    """Return a non-empty user-supplied app/link/handle if the brief mentions one.

    Checks the compilation's ``theme`` field (the user's original prompt) in
    this order:
      1. URL like ``https://focuskit.app``
      2. @handle like ``@nutrilens``
      3. Bare app name after a promotional keyword (e.g. ``"-promo for
         Nutrilens"`` → ``"Nutrilens"``). The app name must start with a
         capital letter so we don't accidentally pick up sentence-starting
         lowercase words.
    """
    theme = (comp.get("theme") or "").strip()
    if not theme:
        return None
    import re as _re

    # 1. URL — strip trailing punctuation so "(focuskit.app)" doesn't keep ")"
    m = _re.search(r"(https?://[^\s)\]\}>,;'\"]+)", theme)
    if m:
        return m.group(1)
    # 2. @handle
    m = _re.search(r"(@[\w.\-]+)", theme)
    if m:
        return m.group(1)
    # 3. Bare app name after a promotional keyword
    KEYWORDS = (
        "promo for", "promo by", "promoting", "promote",
        "push for", "advert for", "sponsored by", "sponsoring",
        "shoutout for", "shoutout to",
    )
    theme_lc = theme.lower()
    for kw in KEYWORDS:
        idx = theme_lc.find(kw)
        if idx < 0:
            continue
        rest = theme[idx + len(kw):].lstrip(" -:—")
        m = _re.match(r"([A-Z][\w.\-]{1,30})", rest)
        if m:
            return m.group(1)
    return None


def build_caption(comp: dict) -> str:
    """Short clean caption — hook + CTA + hashtags. No recipe dump.

    CTA selection:
      1. If the user's theme explicitly mentions ``recipevault`` (case-
         insensitive), use the legacy RecipeVault-app CTA.
      2. Else if the theme contains a URL or @handle, build a personalised
         CTA promoting that app/link.
      3. Otherwise use the domain-neutral save prompt.
    """
    hook = comp.get("hook_caption", "").strip()
    # Pick a deterministic emoji based on the slug so a given compilation
    # always gets the same emoji.
    slug = comp.get("slug", "")
    emoji = _OPENER_EMOJIS[abs(hash(slug)) % len(_OPENER_EMOJIS)]

    theme_lc = (comp.get("theme") or "").lower()
    if "recipevault" in theme_lc:
        cta = _CTA_CAPTION_RECIPEVAULT
    else:
        app_mention = _detect_app_mention(comp)
        if app_mention:
            cta = [
                "Want more like this?",
                f"Check out {app_mention}",
                "Save this so future-you doesn't have to search.",
            ]
        else:
            cta = _CTA_CAPTION_GENERIC

    hashtags = " ".join(_pick_hashtags(comp))
    lines = [
        f"{hook} {emoji}",
        "",
        *cta,
        "",
        hashtags,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-compilation publisher
# ---------------------------------------------------------------------------

def _slide_paths(comp_dir: str) -> list[str]:
    sd = os.path.join(comp_dir, "slides")
    files = sorted(f for f in os.listdir(sd) if f.endswith(".png"))
    return [os.path.join(sd, f) for f in files]


def publish_compilation(
    slug: str,
    *,
    integrations: list[dict],
    post_type: str = "draft",
    date: str | None = None,
) -> list[dict]:
    cdir = os.path.join(OUTPUT_ROOT, slug)
    if not os.path.isdir(cdir):
        raise FileNotFoundError(f"no compilation dir: {cdir}")
    json_path = os.path.join(cdir, f"{slug}.json")
    with open(json_path) as f:
        comp = json.load(f)
    comp.setdefault("slug", slug)

    slides = _slide_paths(cdir)
    if len(slides) != 12:
        raise RuntimeError(f"{slug}: expected 12 slides, got {len(slides)}")

    print(f"\n=== {comp.get('hook_caption', slug)[:80]} ===")
    print(f"  uploading 12 slides ...")
    media = []
    for i, path in enumerate(slides, 1):
        m = upload_image(path)
        media.append({"id": m["id"], "path": m["path"]})
        print(f"    [{i:02d}/12] {os.path.basename(path)}")

    # Prefer the stored caption baked into the JSON (lets you edit captions in
    # the JSON and keep the trending-keyword hashtags). Fall back to building.
    caption = (comp.get("caption") or "").strip()
    if not caption:
        caption = build_caption(comp)
    print(f"  caption ({len(caption)} chars):")
    for line in caption.split("\n"):
        print(f"    {line}")

    posts_payload = []
    for integ in integrations:
        post_value = {"content": caption, "image": media}
        if integ["identifier"] == "tiktok":
            settings = {
                "__type": "tiktok",
                "title": comp.get("hook_caption", slug)[:90],
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
        else:
            settings = {"__type": integ["identifier"]}
        posts_payload.append({
            "integration": {"id": integ["id"]},
            "value": [post_value],
            "settings": settings,
        })

    payload = {
        "type": post_type,
        "date": date or "2026-06-01T12:00:00.000Z",
        "shortLink": False,
        "tags": [],
        "posts": posts_payload,
    }
    out = create_post(payload)
    _mark_published(slug, post_type, out)
    print(f"  created: {out}")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--slug", help="single compilation slug (default: all in output_compilations/)")
    p.add_argument("--type", default="now",
                   choices=["draft", "schedule", "now"],
                   help="post type — 'now' sends to TikTok inbox immediately")
    p.add_argument("--date", help="ISO date for type=schedule")
    p.add_argument("--integrations",
                   help="comma-separated integration ids; default: NutriLens TikTok only")
    p.add_argument("--dry-run", action="store_true",
                   help="print captions only; do not upload or post")
    p.add_argument("--force", action="store_true",
                   help="publish even if already in published.json")
    args = p.parse_args()

    all_integrations = list_integrations()
    print("Available integrations:")
    for it in all_integrations:
        print(f"  - {it['name']:24}  ({it['identifier']:10})  id={it['id']}")

    if args.integrations:
        ids = set(args.integrations.split(","))
        target_ints = [i for i in all_integrations if i["id"] in ids]
    else:
        # default: ONLY NutriLens TikTok
        target_ints = [i for i in all_integrations
                       if i["identifier"] == "tiktok" and i["name"] == "NutriLens"]
    if not target_ints and not args.dry_run:
        sys.exit("No target integrations found.")

    print("\nTargets:")
    for it in target_ints:
        print(f"  -> {it['name']} ({it['identifier']})")

    if args.slug:
        slugs = [args.slug]
    else:
        slugs = sorted(d for d in os.listdir(OUTPUT_ROOT)
                       if os.path.isdir(os.path.join(OUTPUT_ROOT, d))
                       and os.path.exists(os.path.join(OUTPUT_ROOT, d, f"{d}.json")))

    # Filter out already-published slugs (unless --force or --dry-run)
    if not args.force and not args.dry_run:
        before = len(slugs)
        slugs = [s for s in slugs if not is_already_published(s)]
        skipped = before - len(slugs)
        if skipped:
            print(f"\nSkipped {skipped} already-published compilation(s). Use --force to re-publish.")

    print(f"\nProcessing {len(slugs)} compilation(s) (type={args.type}, dry_run={args.dry_run})")

    if args.dry_run:
        for slug in slugs:
            jp = os.path.join(OUTPUT_ROOT, slug, f"{slug}.json")
            with open(jp) as f:
                comp = json.load(f)
            comp.setdefault("slug", slug)
            print("\n" + "=" * 60)
            print(f"SLUG: {slug}")
            print("CAPTION:")
            print((comp.get("caption") or "").strip() or build_caption(comp))
        return

    for slug in slugs:
        try:
            publish_compilation(slug, integrations=target_ints,
                                post_type=args.type, date=args.date)
        except Exception as e:
            print(f"  !! {slug} FAILED: {e}")
        time.sleep(1)


if __name__ == "__main__":
    main()
