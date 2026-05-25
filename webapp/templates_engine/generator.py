"""Template generator: takes (template_id, inputs, brand) → produces a slide deck.

Steps:
  1. Call Gemini with the template's prompt → JSON content
  2. Call Nano Banana for each slide that has an image_prompt → raw image
  3. Render each slide via compositor.render_slide()
  4. Write a manifest JSON

Output structure per generated carousel:
  output_templates/<batch_id>/<carousel_id>/
    spec.json
    raw/01.png 02.png ...
    slides/01_<type>.png 02_<type>.png ...
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# Reuse the existing Nano Banana image generator
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
sys.path.insert(0, os.path.join(ROOT, "compilation_pipeline"))

from . import registry
from . import compositor

OUTPUT_ROOT = os.path.join(ROOT, "output_templates")
os.makedirs(OUTPUT_ROOT, exist_ok=True)


def _slug(s: str, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")
    return s[:n] or "untitled"


# ---------------------------------------------------------------------------
# Gemini text generation
# ---------------------------------------------------------------------------

def _gemini_json(model: str, system_prompt: str, user_prompt: str,
                 temperature: float = 0.9) -> dict:
    from google import genai
    from google.genai import types as gtypes
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY missing")
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=model,
        contents=[system_prompt + "\n\n" + user_prompt],
        config=gtypes.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )
    raw = resp.candidates[0].content.parts[0].text
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate_one(template_id: str, inputs: dict, brand: dict,
                 item_count: int, batch_dir: str,
                 carousel_index: int = 0,
                 image_model: str = "gemini-2.0-flash-preview-image-generation") -> dict:
    """Generate ONE carousel. Returns a dict with paths + metadata."""
    tpl = registry.get_template(template_id)
    if not tpl:
        raise ValueError(f"unknown template: {template_id}")

    # 1. Render Gemini prompt
    fmt_args = dict(inputs)
    fmt_args["item_count"] = item_count
    user_prompt = tpl.user_template.format(**fmt_args)

    content = _gemini_json(
        model="gemini-2.5-flash",
        system_prompt=tpl.system_prompt,
        user_prompt=user_prompt,
        temperature=0.9 + (carousel_index * 0.02 % 0.3),  # slight variation per item
    )

    # 2. Translate content -> slide specs
    specs = tpl.module.slide_specs(content, brand)

    # 3. Set up output dir
    base = _slug(content.get("hook_caption", ""), 50) or f"carousel_{carousel_index}"
    cdir = os.path.join(batch_dir, f"{carousel_index+1:02d}_{base}")
    raw_dir = os.path.join(cdir, "raw")
    slides_dir = os.path.join(cdir, "slides")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(slides_dir, exist_ok=True)
    with open(os.path.join(cdir, "spec.json"), "w") as f:
        json.dump({
            "template_id": template_id,
            "inputs": inputs,
            "brand": brand,
            "content": content,
            "specs": specs,
        }, f, indent=2)

    # 4. Generate raw images in parallel
    from images import generate_image

    def _gen_image(idx: int, prompt: str) -> Optional[str]:
        if not prompt:
            return None
        raw = os.path.join(raw_dir, f"{idx+1:02d}.png")
        try:
            generate_image(prompt, "carousel", raw, model=image_model)
            return raw
        except Exception as e:
            print(f"    image {idx+1} failed: {e}")
            return None

    raw_paths: dict[int, Optional[str]] = {}
    default_workers = "2" if os.environ.get("RENDER") else "6"
    image_workers = max(1, min(len(specs), int(os.environ.get("IMAGE_GEN_WORKERS", default_workers))))
    with ThreadPoolExecutor(max_workers=image_workers) as pool:
        futures = {}
        for i, sp in enumerate(specs):
            prompt = sp.get("image_prompt", "")
            if prompt:
                futures[pool.submit(_gen_image, i, prompt)] = i
        for f in as_completed(futures):
            i = futures[f]
            try:
                raw_paths[i] = f.result()
            except Exception as e:
                print(f"    raw {i+1} exception: {e}")
                raw_paths[i] = None

    # 5. Composite each slide
    for i, sp in enumerate(specs):
        out = os.path.join(slides_dir, f"{i+1:02d}_{sp['type']}.png")
        compositor.render_slide(sp, brand, raw_paths.get(i), out)

    return {
        "dir": cdir,
        "slide_count": len(specs),
        "hook_caption": content.get("hook_caption", ""),
        "hashtags": content.get("hashtags", ""),
        "cta_caption": content.get("cta_caption", ""),
    }


def generate_batch(template_id: str, inputs: dict, brand: dict,
                   count: int, item_count: int,
                   batch_label: str = "") -> dict:
    """Generate ``count`` carousels, each with ``item_count`` items.
    Returns batch metadata.
    """
    batch_id = f"{int(time.time())}_{_slug(batch_label, 30) or template_id}"
    batch_dir = os.path.join(OUTPUT_ROOT, batch_id)
    os.makedirs(batch_dir, exist_ok=True)

    results = []
    for i in range(count):
        try:
            print(f"  generating carousel {i+1}/{count}...")
            r = generate_one(template_id, inputs, brand, item_count,
                             batch_dir, carousel_index=i)
            results.append(r)
        except Exception as e:
            traceback.print_exc()
            results.append({"error": str(e), "index": i})

    meta = {
        "batch_id": batch_id,
        "template_id": template_id,
        "inputs": inputs,
        "brand": brand,
        "count": count,
        "item_count": item_count,
        "results": results,
        "created_at": int(time.time()),
    }
    with open(os.path.join(batch_dir, "batch.json"), "w") as f:
        json.dump(meta, f, indent=2)
    return meta
