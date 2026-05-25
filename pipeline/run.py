"""
Orchestrator: take a list of recipe briefs, generate everything, save to disk.

Usage:
    python run.py                       # runs the 5 sample briefs
    python run.py "wagyu beef bowl"     # runs a single ad-hoc brief
    python run.py --briefs briefs.txt   # one brief per line

Output structure:
    output/
      <slug>/
        recipe.json       # full recipe definition
        raw/01.png ...    # generator output (no overlays)
        slides/01.png ... # final composited slides
"""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Make .env available
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

from recipes import generate_recipe, save_recipe_json   # noqa: E402
from images import generate_image                       # noqa: E402
from compositor import composite_slide                  # noqa: E402


# 5 sample briefs covering breakfast / lunch / dinner / snack / dessert
SAMPLE_BRIEFS = [
    "high-protein chicken caesar wrap (5 minutes)",
    "overnight oats with berries and almond butter (breakfast)",
    "spicy tuna avocado rice bowl (lunch, 10 minutes)",
    "garlic butter shrimp pasta (dinner, 15 minutes)",
    "no-bake peanut butter chocolate energy bites (snack)",
]


OUTPUT_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


def run_one_recipe(brief: str, *, image_quality: str = "medium",
                   progress_cb=None) -> str:
    """Generate one single-recipe carousel.

    progress_cb: optional callable(message:str) for streaming phase updates
                 to a UI poller. Failures inside the callback are swallowed.
    """
    def _emit(msg: str) -> None:
        if progress_cb is None:
            return
        try:
            progress_cb(msg)
        except Exception as _e:
            print(f"  [progress_cb] swallowed: {_e}")

    print(f"\n=== {brief} ===")
    _emit("Drafting recipe + slide plan with Gemini…")
    recipe = generate_recipe(brief)
    print(f"  -> {recipe.slug}: {recipe.title}")
    _emit(f"Got recipe spec: {recipe.title}")

    rdir = os.path.join(OUTPUT_ROOT, recipe.slug)
    raw_dir = os.path.join(rdir, "raw")
    slides_dir = os.path.join(rdir, "slides")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(slides_dir, exist_ok=True)
    save_recipe_json(recipe, rdir)

    # Generate images in parallel (4 at a time to be friendly to API rate limits)
    def _do_one(slide):
        raw_path = os.path.join(raw_dir, f"{slide.index:02d}.png")
        if not os.path.exists(raw_path):
            generate_image(
                slide.image_prompt,
                slide.slide_type,
                raw_path,
                quality=image_quality,
            )
        out_path = os.path.join(slides_dir, f"{slide.index:02d}.png")
        composite_slide(
            raw_path,
            out_path,
            slide_type=slide.slide_type,
            caption=slide.caption,
            callouts=slide.callouts,
        )
        return out_path

    total = len(recipe.slides)
    default_workers = "2" if os.environ.get("RENDER") else "4"
    image_workers = max(1, min(total, int(os.environ.get("IMAGE_GEN_WORKERS", default_workers))))
    _emit(f"Generating {total} slides (image + composite, {image_workers} at a time)…")
    done_count = 0
    with ThreadPoolExecutor(max_workers=image_workers) as pool:
        futures = {pool.submit(_do_one, s): s for s in recipe.slides}
        for f in as_completed(futures):
            slide = futures[f]
            done_count += 1
            try:
                p = f.result()
                print(f"  [{slide.index:02d}] {slide.caption}  -> {os.path.basename(p)}")
                _emit(f"Slide {done_count}/{total} done — {slide.caption}")
            except Exception as e:  # noqa: BLE001
                print(f"  [{slide.index:02d}] FAILED: {e}")
                _emit(f"Slide {done_count}/{total} failed: {e}")
    return rdir


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("brief", nargs="?", help="single recipe brief")
    parser.add_argument("--briefs", help="file with one brief per line")
    parser.add_argument("--quality", default="medium",
                        choices=["low", "medium", "high"])
    args = parser.parse_args()

    if args.brief:
        briefs = [args.brief]
    elif args.briefs:
        briefs = [l.strip() for l in open(args.briefs) if l.strip()]
    else:
        briefs = SAMPLE_BRIEFS

    for b in briefs:
        try:
            run_one_recipe(b, image_quality=args.quality)
        except Exception as e:  # noqa: BLE001
            print(f"!! recipe FAILED for '{b}': {e}")


if __name__ == "__main__":
    main()
