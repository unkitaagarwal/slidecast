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
from concurrent.futures import ThreadPoolExecutor, as_completed


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


def run_one_compilation(theme: str) -> str:
    print(f"\n=== {theme} ===")
    comp = generate_compilation(theme)
    print(f"  -> {comp.slug}")
    print(f"  -> hook: {comp.hook_caption}")
    print(f"  -> recipes: {[r.title for r in comp.recipes]}")

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

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_gen, n, p, st): n for n, p, st in tasks}
        for f in as_completed(futures):
            n = futures[f]
            try:
                f.result()
                print(f"  raw: {n}")
            except Exception as e:
                print(f"  RAW FAIL {n}: {e}")

    # ---- Step 2: composite 12 slides ----
    print("  compositing slides...")
    composite_hook(raw_paths["hook"], comp.hook_caption,
                   os.path.join(slides_dir, "01_hook.png"))

    # Recipes 1 & 2 (photo + page)
    composite_photo(raw_paths["hero1"], comp.recipes[0].title,
                    os.path.join(slides_dir, "02_recipe1_photo.png"))
    composite_recipe_page(comp.recipes[0].__dict__,
                          os.path.join(slides_dir, "03_recipe1_page.png"))
    composite_photo(raw_paths["hero2"], comp.recipes[1].title,
                    os.path.join(slides_dir, "04_recipe2_photo.png"))
    composite_recipe_page(comp.recipes[1].__dict__,
                          os.path.join(slides_dir, "05_recipe2_page.png"))

    # Mid-carousel CTA
    composite_cta(comp.cta_caption,
                  os.path.join(slides_dir, "06_cta.png"))

    # Recipes 3, 4, 5
    composite_photo(raw_paths["hero3"], comp.recipes[2].title,
                    os.path.join(slides_dir, "07_recipe3_photo.png"))
    composite_recipe_page(comp.recipes[2].__dict__,
                          os.path.join(slides_dir, "08_recipe3_page.png"))
    composite_photo(raw_paths["hero4"], comp.recipes[3].title,
                    os.path.join(slides_dir, "09_recipe4_photo.png"))
    composite_recipe_page(comp.recipes[3].__dict__,
                          os.path.join(slides_dir, "10_recipe4_page.png"))
    composite_photo(raw_paths["hero5"], comp.recipes[4].title,
                    os.path.join(slides_dir, "11_recipe5_photo.png"))
    composite_recipe_page(comp.recipes[4].__dict__,
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
