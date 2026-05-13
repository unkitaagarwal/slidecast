"""
Image generator with a consistent UGC style across all slides.

We append a fixed style suffix to every prompt so all images look like the same
creator filmed them — same surface, same lighting, same camera vibe.

Uses OpenAI's gpt-image-1 by default (best food realism). Can fall back to
dall-e-3 by passing model="dall-e-3".
"""

from __future__ import annotations

import base64
import os
import time
from openai import OpenAI

# A single style suffix applied to every prompt. This is what makes 100 recipes
# look like one cohesive feed instead of a random assortment.
#
# REALISM NOTE: gpt-image-1 has a tendency toward illustration / glossy "AI
# food magazine" aesthetic if not pushed otherwise. The cues below are tuned
# to drag it back toward authentic smartphone food photography:
#   - explicitly photographic and shot on a real phone
#   - imperfect plating, asymmetric, casual home-kitchen feel
#   - visible board scratches / wear, real food shadows, real specular highlights
#   - no glossy/plastic look, no studio polish, no unrealistic color saturation
STYLE_SUFFIX = (
    " STYLE: tight overhead phone-photo of food in a single vessel — typically a "
    "stainless steel mixing bowl, a ceramic bowl, a sheet pan, a non-stick skillet, "
    "or a measuring cup. The vessel is centered and fills most of the frame. "
    "Background: extremely clean and uncluttered. ONLY a plain off-white kitchen "
    "counter, plain butcher-block wood, or a plain stovetop visible at the edges. "
    "ABSOLUTELY NOTHING ELSE in frame: no plants, no paper towels, no kitchen towels, "
    "no soap bottles, no salt shakers, no glasses, no plates on the side, no "
    "backsplash detail, no decorations, no props, no people. Just the vessel, "
    "the food inside it, and a small margin of plain surface around it. "
    "Lighting: soft natural daylight from above/slight angle, warm but not "
    "oversaturated, realistic gentle shadow under the vessel. "
    "Food: real textures, real moisture, slight imperfections — looks like "
    "someone snapped a phone photo while cooking, not a magazine shoot. "
    "Camera: square 1:1 crop, directly overhead unless otherwise specified, "
    "tight framing on the vessel. "
    "MUST look like a real photo, NOT illustration, NOT AI-generated, NOT 3D render, "
    "NOT studio glamour, NOT plastic perfect. "
    "Strict negatives: no text, no watermark, no logos, no extra props, no plants, "
    "no garnish that wasn't asked for, no oversaturation, no airbrushed AI sheen."
)

# We allow per-slide-type overrides because some slides need a different angle
# (e.g. the wrap-folding action shot reads better from a slight 30-degree angle).
ANGLE_OVERRIDES = {
    "assemble": (
        " STYLE: tight overhead phone-photo of the assembly happening — wrap being "
        "folded, sandwich being layered, bowl being plated. Centered framing on "
        "the food. Plain butcher-block or off-white counter visible at the edges, "
        "NOTHING else in frame. No plants, no towels, no props. "
        "Soft natural daylight, real textures, slight imperfections. "
        "MUST look like a real phone photo, NOT illustration, NOT AI, NOT studio. "
        "Square 1:1 crop. No text, no watermark."
    ),
    "finish": (
        " STYLE: tight overhead phone-photo of the food cooking in a non-stick pan "
        "or skillet on a clean stovetop. Pan centered, fills most of the frame. "
        "ONLY a small margin of plain dark stovetop surface visible at the edges — "
        "NOTHING else: no plants, no towels, no props, no other dishes. "
        "Realistic gentle steam wisps where appropriate, real char/sear marks, "
        "real oil shimmer. Soft natural daylight. "
        "MUST look like a real phone photo, NOT illustration, NOT AI, NOT studio. "
        "Square 1:1 crop. No text, no watermark."
    ),
}


def build_prompt(base_prompt: str, slide_type: str) -> str:
    suffix = ANGLE_OVERRIDES.get(slide_type, STYLE_SUFFIX)
    return f"{base_prompt}\n\nSTYLE: {suffix}"


def _generate_with_openai(full_prompt: str, model: str, size: str, quality: str) -> bytes:
    client = OpenAI()
    kwargs = dict(model=model, prompt=full_prompt, size=size, n=1)
    if model.startswith("gpt-image-1"):
        kwargs["quality"] = quality
    else:
        # dall-e-3 uses different quality values
        kwargs["quality"] = "standard" if quality in ("low", "medium") else "hd"
    resp = client.images.generate(**kwargs)
    img_data = resp.data[0]
    if getattr(img_data, "b64_json", None):
        return base64.b64decode(img_data.b64_json)
    import requests
    return requests.get(img_data.url, timeout=60).content


def _generate_with_gemini(full_prompt: str, model: str) -> bytes:
    """Generate an image via Google's Gemini (Nano Banana) image API."""
    from google import genai
    from google.genai import types as gtypes

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY missing from environment")
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=model,
        contents=[full_prompt],
        config=gtypes.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )
    for part in resp.candidates[0].content.parts:
        if getattr(part, "inline_data", None):
            return part.inline_data.data
    raise RuntimeError("Gemini returned no image data")


def generate_image(
    base_prompt: str,
    slide_type: str,
    output_path: str,
    model: str = "gemini-2.5-flash-image",
    size: str = "1024x1024",
    quality: str = "high",   # for gpt-image-1 family
    retries: int = 2,
) -> str:
    """Generate a single image and write it to output_path. Returns the path.

    Routes to the right provider based on model name:
        - "gpt-image-1*", "dall-e-*"   -> OpenAI
        - "gemini-*", "imagen-*"       -> Google Gemini
    """
    full_prompt = build_prompt(base_prompt, slide_type)
    is_gemini = model.startswith("gemini-") or model.startswith("imagen-")

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            if is_gemini:
                raw = _generate_with_gemini(full_prompt, model)
            else:
                raw = _generate_with_openai(full_prompt, model, size, quality)

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(raw)
            return output_path

        except Exception as e:  # noqa: BLE001
            last_err = e
            wait = 2 ** attempt
            print(f"  [image retry {attempt+1}/{retries}] {type(e).__name__}: {str(e)[:120]}; sleeping {wait}s")
            time.sleep(wait)

    raise RuntimeError(f"image generation failed after {retries+1} attempts") from last_err
