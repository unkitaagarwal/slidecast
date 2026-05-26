"""End-to-end runner for ONE compilation carousel.

Usage:
    python3 run_compilation.py "5 lazy weeknight dinners"
    python3 run_compilation.py --theme "5 high-protein lunches"

Pipeline order:
    1. generate_compilation(theme)   -> compilation JSON (5 recipes + hook + cta)
    2. generate hook image (Nano Banana)
    3. generate 5 hero photos (Nano Banana, parallel)
    4. composite 12 slides:
         01_hook
         02_recipe1_photo
         03_recipe1_page
         04_recipe2_photo
         05_recipe2_page
         06_cta
         07_recipe3_photo
         08_recipe3_page
         09_recipe4_photo
         10_recipe4_page
         11_recipe5_photo
         12_recipe5_page
    5. write everything to ../output_compilations/<slug>/

Output layout per compilation:
    output_compilations/<slug>/
        <slug>.json       # full compilation spec
        raw/              # 6 raw Nano Banana images (hook + 5 hero shots)
        slides/           # 12 final composited slides
"""
from __future__ import annotations
import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed, wait as _futures_wait


def _load_env():
    env = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env):
        for line in open(env):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


_load_env()
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTPUT_ROOT = os.path.join(ROOT, "output_compilations")

# Reuse the existing image generator (Nano Banana default)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from images import generate_image  # noqa: E402

sys.path.insert(0, HERE)
from recipes_compilation import (  # noqa: E402
    generate_compilation,
    save_compilation_json,
)
from compositor_compilation import (  # noqa: E402
    composite_hook,
    composite_photo,
    composite_recipe_page,
    composite_cta,
)


_APP_KEYWORDS = (
    "promo for", "promo by", "promoting", "promote",
    "push for", "advert for", "sponsored by", "sponsoring",
    "shoutout for", "shoutout to",
)


def _detect_cta_context(theme: str) -> tuple[Optional[str], bool]:
    """Inspect the user's brief and return (app_name, is_recipevault).

    app_name: the matched URL / @handle / bare app name, or None.
    is_recipevault: True iff the brief explicitly mentions RecipeVault (the
    only context that should keep the legacy recipe-keeper card image).
    """
    import re as _re
    if not theme:
        return None, False
    theme_lc = theme.lower()
    is_rv = "recipevault" in theme_lc

    # URL
    m = _re.search(r"(https?://[^\s)\]\}>,;'\"]+)", theme)
    if m:
        return m.group(1), is_rv
    # @handle
    m = _re.search(r"(@[\w.\-]+)", theme)
    if m:
        return m.group(1), is_rv
    # Bare app name after a promotional keyword
    for kw in _APP_KEYWORDS:
        idx = theme_lc.find(kw)
        if idx < 0:
            continue
        rest = theme[idx + len(kw):].lstrip(" -:—")
        m = _re.match(r"([A-Z][\w.\-]{1,30})", rest)
        if m:
            return m.group(1), is_rv
    return None, is_rv


from typing import Optional


def run_one_compilation(theme: str, progress_cb=None) -> str:
    """Generate one compilation carousel.

    progress_cb: optional callable(message:str) called at each phase boundary
                 so a long-running job can report intermediate status to a UI.
                 Safe to omit (CLI path) — failures inside the callback are
                 swallowed so a bad UI integration can never break the pipeline.
    """
    def _emit(msg: str) -> None:
        if progress_cb is None:
            return
        try:
            progress_cb(msg)
        except Exception as _e:
            # Never let a UI callback crash the pipeline
            print(f"  [progress_cb] swallowed: {_e}")

    print(f"\n=== {theme} ===")
    _emit("Brainstorming your hook + 5 items (this usually takes 1-2 minutes)…")
    comp = generate_compilation(theme)
    print(f"  -> {comp.slug}")
    print(f"  -> hook: {comp.hook_caption}")
    print(f"  -> recipes: {[r.title for r in comp.recipes]}")
    _emit(f"Got it — {len(comp.recipes)} items locked in ✓")

    cdir = os.path.join(OUTPUT_ROOT, comp.slug)
    raw_dir = os.path.join(cdir, "raw")
    slides_dir = os.path.join(cdir, "slides")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(slides_dir, exist_ok=True)
    save_compilation_json(comp, cdir)

    # ---- Step 1: generate 6 raw images in parallel (1 hook + 5 heroes) ----
    raw_paths = {
        "hook": os.path.join(raw_dir, "00_hook.png"),
    }
    for i, r in enumerate(comp.recipes, 1):
        raw_paths[f"hero{i}"] = os.path.join(raw_dir, f"{i:02d}_hero.png")

    def _gen(name, prompt, slide_type):
        if not os.path.exists(raw_paths[name]):
            generate_image(prompt, slide_type, raw_paths[name])
        return name

    tasks = [("hook", comp.hook_image_prompt, "hook")]
    for i, r in enumerate(comp.recipes, 1):
        tasks.append((f"hero{i}", r.hero_image_prompt, "hero"))

    # Hard wall-clock limit on the image generation phase.
    # Render Standard has 1 CPU / 2 GB RAM, so avoid running all six image
    # requests at once there. Locally we keep the old higher concurrency.
    _IMAGE_TIMEOUT = int(os.environ.get("IMAGE_GEN_TIMEOUT", "180"))
    default_workers = "2" if os.environ.get("RENDER") else "6"
    _IMAGE_WORKERS = max(1, min(len(tasks), int(os.environ.get("IMAGE_GEN_WORKERS", default_workers))))

    _emit(f"Painting {len(tasks)} cinematic visuals in parallel — hold tight…")
    _completed = 0
    with ThreadPoolExecutor(max_workers=_IMAGE_WORKERS) as pool:
        futures = {pool.submit(_gen, n, p, st): n for n, p, st in tasks}
        # Poll completions so the UI sees a heartbeat per image, not just
        # one big silence between submit and wait().
        from concurrent.futures import as_completed as _as_completed
        try:
            for f in _as_completed(futures, timeout=_IMAGE_TIMEOUT):
                n = futures[f]
                _completed += 1
                try:
                    f.result()
                    print(f"  raw: {n}")
                    _emit(f"Visual {_completed}/{len(tasks)} ready ✓")
                except Exception as e:
                    print(f"  RAW FAIL {n}: {e}")
                    _emit(f"Visual {_completed}/{len(tasks)} had a hiccup — moving on")
        except TimeoutError:
            for f, n in futures.items():
                if not f.done():
                    f.cancel()
                    print(f"  RAW TIMEOUT {n}: image took >{_IMAGE_TIMEOUT}s — skipping")
            _emit("Visuals took a bit too long — using what's ready")

    # ---- Step 2: composite 12 slides ----
    print("  compositing slides...")
    _emit("Stitching everything into your final slides…")

    def _compose(label, fn, *args):
        fn(*args)
        _emit(f"Slide {label} ready")

    _compose("1/12 hook", composite_hook, raw_paths["hook"], comp.hook_caption,
             os.path.join(slides_dir, "01_hook.png"))

    # Recipes 1 & 2 (photo + page)
    _compose("2/12 recipe 1 photo", composite_photo, raw_paths["hero1"], comp.recipes[0].title,
             os.path.join(slides_dir, "02_recipe1_photo.png"))
    _compose("3/12 recipe 1 page", composite_recipe_page, comp.recipes[0].__dict__,
             os.path.join(slides_dir, "03_recipe1_page.png"))
    _compose("4/12 recipe 2 photo", composite_photo, raw_paths["hero2"], comp.recipes[1].title,
             os.path.join(slides_dir, "04_recipe2_photo.png"))
    _compose("5/12 recipe 2 page", composite_recipe_page, comp.recipes[1].__dict__,
             os.path.join(slides_dir, "05_recipe2_page.png"))

    # Mid-carousel CTA — detect promotional context from the user's theme
    # so we render the right card: RecipeVault static image vs. user-supplied
    # app pill vs. nothing.
    cta_app_name, cta_is_recipevault = _detect_cta_context(theme)
    composite_cta(
        comp.cta_caption,
        os.path.join(slides_dir, "06_cta.png"),
        app_name=cta_app_name,
        is_recipevault=cta_is_recipevault,
    )
    _emit("Slide 6/12 CTA ready")

    # Recipes 3, 4, 5
    _compose("7/12 recipe 3 photo", composite_photo, raw_paths["hero3"], comp.recipes[2].title,
             os.path.join(slides_dir, "07_recipe3_photo.png"))
    _compose("8/12 recipe 3 page", composite_recipe_page, comp.recipes[2].__dict__,
             os.path.join(slides_dir, "08_recipe3_page.png"))
    _compose("9/12 recipe 4 photo", composite_photo, raw_paths["hero4"], comp.recipes[3].title,
             os.path.join(slides_dir, "09_recipe4_photo.png"))
    _compose("10/12 recipe 4 page", composite_recipe_page, comp.recipes[3].__dict__,
             os.path.join(slides_dir, "10_recipe4_page.png"))
    _compose("11/12 recipe 5 photo", composite_photo, raw_paths["hero5"], comp.recipes[4].title,
             os.path.join(slides_dir, "11_recipe5_photo.png"))
    _compose("12/12 recipe 5 page", composite_recipe_page, comp.recipes[4].__dict__,
             os.path.join(slides_dir, "12_recipe5_page.png"))

    print(f"  DONE -> {cdir}")
    return cdir


def main():
    p = argparse.ArgumentParser()
    p.add_argument("theme", nargs="?", help="compilation theme")
    p.add_argument("--theme", dest="theme_kw", help="alt way to pass --theme")
    args = p.parse_args()

    theme = args.theme or args.theme_kw
    if not theme:
        sys.exit("Usage: run_compilation.py 'theme string'")
    run_one_compilation(theme)


if __name__ == "__main__":
    main()
