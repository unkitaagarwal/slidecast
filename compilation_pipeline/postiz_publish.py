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

import requests


API_BASE = "https://api.postiz.com/public/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTPUT_ROOT = os.path.join(ROOT, "output_compilations")


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

# Universal hashtags appended to every compilation
UNIVERSAL_HASHTAGS = [
    "#RecipeVault",
    "#cookwithme",
    "#mealideas",
    "#recipeideas",
    "#whattocook",
    "#Recipe",
    "#DinnerIdeas",
    "#EasyRecipe",
    "#comfortfood",
    "#foodtok",
    "#fyp",
]


def _pick_hashtags(comp: dict) -> list[str]:
    haystack = (
        comp.get("hook_caption", "") + " " +
        comp.get("theme", "") + " " +
        " ".join(r.get("title", "") for r in comp.get("recipes", []))
    ).lower()
    tags: list[str] = []
    for kw, hs in THEME_HASHTAGS.items():
        if kw in haystack:
            for t in hs:
                if t not in tags:
                    tags.append(t)
    for t in UNIVERSAL_HASHTAGS:
        if t not in tags:
            tags.append(t)
    # Cap at 14 tags total — TikTok still ranks if there are too many
    return tags[:14]


# Small bank of opener emojis to keep posts looking varied
_OPENER_EMOJIS = ["😏", "😅", "🤤", "👀", "💕", "🍳", "✨"]


def build_caption(comp: dict) -> str:
    """Short clean caption — hook + RecipeVault CTA + hashtags. No recipe dump."""
    hook = comp.get("hook_caption", "").strip()
    # Pick a deterministic emoji based on the slug so a given compilation
    # always gets the same emoji.
    slug = comp.get("slug", "")
    emoji = _OPENER_EMOJIS[abs(hash(slug)) % len(_OPENER_EMOJIS)]

    hashtags = " ".join(_pick_hashtags(comp))
    lines = [
        f"{hook} {emoji}",
        "",
        "Looking for recipe ideas to cook at home? Check these out! \U0001f468‍\U0001f373\U0001f495",
        "",
        "Save these recipes easily with RecipeVault app! Link in bio \U0001f4dd\U0001f373",
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
