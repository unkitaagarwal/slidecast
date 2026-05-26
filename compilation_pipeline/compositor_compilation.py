"""Compilation slide compositor.

4 slide types:
  - hook        : full-bleed image + edgy white title text (like the existing format)
  - photo       : food photo + recipe title overlay (white on bottom 25%)
  - recipe_page : parchment background with INGREDIENTS + INSTRUCTIONS columns
  - cta         : warm pink/coral background, tagline at top, cta_card.png at bottom

Canvas is 1080 x 1350 (Instagram 4:5 portrait — same as our other format).
Text safe zone keeps to ~70% width to clear TikTok's right-rail UI.
"""
from __future__ import annotations
import os
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SLIDE_W, SLIDE_H = 1080, 1350

_HERE = os.path.dirname(os.path.abspath(__file__))
_FONT_DIR = os.path.normpath(os.path.join(_HERE, "..", "assets", "fonts"))

FONT_BOLD_PATH = os.path.join(_FONT_DIR, "PlusJakartaSans-Bold.ttf")
FONT_XBOLD_PATH = os.path.join(_FONT_DIR, "PlusJakartaSans-ExtraBold.ttf")
FONT_REG_PATH = os.path.join(_FONT_DIR, "PlusJakartaSans-Regular.ttf")
CTA_CARD_PATH = os.path.normpath(os.path.join(_HERE, "..", "assets", "cta_card.png"))
PARCHMENT_PATTERN_PATH = os.path.normpath(
    os.path.join(_HERE, "..", "assets", "parchment_pattern.png")
)

# Parchment / cream colors (recipe page)
PARCHMENT_BG = (244, 232, 211)         # warm cream
PARCHMENT_TITLE = (146, 38, 34)        # deep red, like a printed cookbook header
PARCHMENT_HEADER = (120, 60, 40)       # warm brown for INGREDIENTS / INSTRUCTIONS
PARCHMENT_BODY = (60, 45, 35)          # dark brown body text

# CTA slide colors
CTA_BG = (255, 92, 122)                # warm coral pink
CTA_TEXT = (255, 255, 255)


# ---------------------------------------------------------------------------
# Domain detection — used to switch the recipe-page layout between the
# food-cookbook style (INGREDIENTS + INSTRUCTIONS) and the generic
# information-page style (OVERVIEW + KEY POINTS) for other niches.
# ---------------------------------------------------------------------------

_FOOD_SECTION_KEYWORDS = (
    "ingredient", "for the", "for dish", "for serving",
    "protein", "marinade", "garnish", "topping", "sauce",
    "creaminess", "spice", "dressing", "filling", "dough",
    "batter", "glaze", "rub", "seasoning",
)


def _is_food_item(recipe: dict) -> bool:
    """Heuristic: is this item from the food/recipe domain?

    Looks at the section names Gemini chose for ``ingredient_sections``. Recipe
    outputs use names like "FOR THE PROTEIN" / "FOR THE SAUCE" / "MARINADE";
    non-food outputs use things like "WARM-UP" / "KEY FACTS" / "TOOLS".

    Falls back to ``True`` (food) when the recipe is missing sections — that
    preserves the original behaviour for legacy JSON specs in the library.
    """
    # Honour an explicit domain override if Gemini wrote one
    domain = (recipe.get("domain") or "").strip().lower()
    if domain in ("food", "recipe", "recipes", "cooking"):
        return True
    if domain and domain not in ("auto", ""):
        return False  # an explicit non-food domain was set

    sections = recipe.get("ingredient_sections") or []
    if not sections:
        return True
    joined = " ".join(str(s.get("name", "")).lower() for s in sections)
    return any(kw in joined for kw in _FOOD_SECTION_KEYWORDS)


def _load_font(size: int, weight: str = "bold") -> ImageFont.FreeTypeFont:
    paths = []
    if weight == "xbold":
        paths.append(FONT_XBOLD_PATH)
    if weight in ("bold", "xbold"):
        paths.append(FONT_BOLD_PATH)
    if weight == "regular":
        paths.append(FONT_REG_PATH)
    paths.extend([
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ])
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fit_image_cover(src: Image.Image, w: int = SLIDE_W, h: int = SLIDE_H) -> Image.Image:
    """Center-crop scale to fill (w,h)."""
    src_w, src_h = src.size
    sr = src_w / src_h
    tr = w / h
    if sr > tr:
        nh = h
        nw = int(h * sr)
    else:
        nw = w
        nh = int(w / sr)
    src = src.resize((nw, nh), Image.LANCZOS)
    x = (nw - w) // 2
    y = (nh - h) // 2
    return src.crop((x, y, x + w, y + h))


def _wrap(text: str, font, max_w: int) -> list[str]:
    out: list[str] = []
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    for paragraph in text.split("\n"):
        words = paragraph.split()
        cur = ""
        for w in words:
            trial = (cur + " " + w).strip()
            if tmp.textbbox((0, 0), trial, font=font)[2] <= max_w or not cur:
                cur = trial
            else:
                out.append(cur)
                cur = w
        if cur:
            out.append(cur)
    return out


def _draw_text_with_stroke(canvas, xy, text, font, fill=(255, 255, 255),
                           stroke=(0, 0, 0), stroke_w=4, shadow=True):
    """Draw centered text with stroke and optional drop shadow."""
    d = ImageDraw.Draw(canvas)
    bbox = d.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    cx, cy = xy
    x = cx - tw // 2 - bbox[0]
    y = cy - th // 2 - bbox[1]
    if shadow:
        sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        sd.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 110))
        sh = sh.filter(ImageFilter.GaussianBlur(5))
        canvas.alpha_composite(sh)
    d.text((x, y), text, font=font, fill=fill, stroke_width=stroke_w, stroke_fill=stroke)


# ---------------------------------------------------------------------------
# Slide type: HOOK
# ---------------------------------------------------------------------------

def composite_hook(src_image_path: str, hook_caption: str, out_path: str) -> str:
    src = Image.open(src_image_path).convert("RGB")
    canvas = _fit_image_cover(src).convert("RGBA")

    # Subtle dark vignette at top + bottom for text legibility
    vignette = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    for i in range(220):
        alpha = int(140 * (1 - i / 220))
        vd.line([(0, i), (SLIDE_W, i)], fill=(0, 0, 0, alpha))
        vd.line([(0, SLIDE_H - i), (SLIDE_W, SLIDE_H - i)], fill=(0, 0, 0, alpha))
    canvas.alpha_composite(vignette)

    # Pick a font size that lets the caption fit on at most 3 centered lines
    # within 75% width.
    max_w = int(SLIDE_W * 0.78)
    size = 100
    while size > 50:
        font = _load_font(size, weight="xbold")
        lines = _wrap(hook_caption, font, max_w)
        if len(lines) <= 3:
            break
        size -= 6

    line_h = int(font.size * 1.05)
    total_h = line_h * len(lines) + 14 * (len(lines) - 1)
    y_start = (SLIDE_H - total_h) // 2 + line_h // 2

    for i, line in enumerate(lines):
        cy = y_start + i * (line_h + 14)
        _draw_text_with_stroke(canvas, (SLIDE_W // 2, cy), line, font,
                               fill=(255, 255, 255), stroke=(0, 0, 0), stroke_w=5)

    canvas.convert("RGB").save(out_path, "PNG")
    return out_path


# ---------------------------------------------------------------------------
# Slide type: PHOTO (food photo + recipe title)
# ---------------------------------------------------------------------------

def composite_photo(src_image_path: str, recipe_title: str, out_path: str) -> str:
    src = Image.open(src_image_path).convert("RGB")
    canvas = _fit_image_cover(src).convert("RGBA")

    # Subtle gradient overlay at the bottom 40% so the title pops
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    grad_top = int(SLIDE_H * 0.55)
    for y in range(grad_top, SLIDE_H):
        a = int(170 * ((y - grad_top) / (SLIDE_H - grad_top)))
        od.line([(0, y), (SLIDE_W, y)], fill=(0, 0, 0, a))
    canvas.alpha_composite(overlay)

    max_w = int(SLIDE_W * 0.80)
    size = 88
    while size > 44:
        font = _load_font(size, weight="xbold")
        lines = _wrap(recipe_title, font, max_w)
        if len(lines) <= 2:
            break
        size -= 4

    line_h = int(font.size * 1.05)
    total_h = line_h * len(lines) + 12 * (len(lines) - 1)
    y_start = SLIDE_H - 240 - total_h // 2

    for i, line in enumerate(lines):
        cy = y_start + i * (line_h + 12)
        _draw_text_with_stroke(canvas, (SLIDE_W // 2, cy), line, font,
                               fill=(255, 255, 255), stroke=(0, 0, 0), stroke_w=4)

    canvas.convert("RGB").save(out_path, "PNG")
    return out_path


# ---------------------------------------------------------------------------
# Slide type: RECIPE PAGE (parchment + columns)
# ---------------------------------------------------------------------------

def _draw_parchment_texture(canvas: Image.Image) -> None:
    """Add subtle paper-fiber noise to the parchment so it doesn't look flat."""
    import random
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rnd = random.Random(42)
    for _ in range(14000):
        x = rnd.randint(0, SLIDE_W - 1)
        y = rnd.randint(0, SLIDE_H - 1)
        a = rnd.randint(8, 22)
        d.point((x, y), fill=(120, 80, 50, a))
    layer = layer.filter(ImageFilter.GaussianBlur(0.6))
    canvas.alpha_composite(layer)


def _parchment_gradient_bg() -> Image.Image:
    """Premium cookbook background: parchment cream + decorative kitchen
    line-art pattern + subtle radial vignette. Mirrors the @emerybrookscook
    look — pattern fills the page so it never feels empty."""
    canvas = Image.new("RGBA", (SLIDE_W, SLIDE_H), PARCHMENT_BG + (255,))

    # Layer 1: tile the line-art pattern at ~28% opacity so it reads as
    # decorative wallpaper, not foreground content.
    if os.path.exists(PARCHMENT_PATTERN_PATH):
        pattern = Image.open(PARCHMENT_PATTERN_PATH).convert("RGBA")
        # Resize pattern to fully cover the slide (one big stamp, no tiling
        # seams). Center-crop scale to fit.
        pat = _fit_image_cover(pattern.convert("RGB"), SLIDE_W, SLIDE_H).convert("RGBA")
        # Reduce its opacity / desaturate so it sits behind text
        # Convert the pattern to a desaturated warm tint
        bands = pat.split()
        # Blend the pattern with the parchment color heavily so it tints
        tinted = Image.new("RGBA", canvas.size, PARCHMENT_BG + (255,))
        # Use alpha 60 over parchment to keep the pattern subtle
        pat.putalpha(60)
        tinted.alpha_composite(pat)
        canvas = tinted

    # Layer 2: radial vignette for depth
    overlay = Image.new("RGBA", (SLIDE_W, SLIDE_H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    cx, cy = SLIDE_W // 2, SLIDE_H // 2
    max_r = (cx ** 2 + cy ** 2) ** 0.5
    steps = 60
    for i in range(steps):
        r = int(max_r * (1 - i / steps))
        a = int(34 * (i / steps) ** 1.6)
        od.ellipse([(cx - r, cy - r * 1.05), (cx + r, cy + r * 1.05)],
                   fill=(110, 70, 35, a))
    overlay = overlay.filter(ImageFilter.GaussianBlur(60))
    canvas.alpha_composite(overlay)
    return canvas


# ---------------------------------------------------------------------------
# Helpers for richer instruction / ingredient formatting
# ---------------------------------------------------------------------------

# Common cooking-action words that map to bold step labels.
_ACTION_VERBS = [
    "preheat", "heat", "warm", "cook", "boil", "simmer", "reduce", "add",
    "mix", "stir", "whisk", "combine", "fold", "season", "saute", "sauté",
    "sear", "pan-fry", "fry", "roast", "bake", "grill", "broil", "crisp",
    "toast", "drain", "rinse", "chop", "dice", "mince", "slice", "shred",
    "grate", "blend", "pour", "drizzle", "garnish", "top", "serve",
    "assemble", "arrange", "place", "transfer", "remove", "set", "rest",
    "marinate", "rub", "coat", "brush", "sprinkle", "layer", "fill",
    "wrap", "spread", "scoop", "flip", "cool", "freeze", "chill",
    "deglaze", "char", "caramelize", "thicken", "ladle", "press",
    "knead", "proof", "rise", "ready", "finish", "plate",
    # Common recipe-step starters that were missing
    "prepare", "make", "let", "tip", "uncover", "cover", "bring", "stir-fry",
    "return", "toss", "drizzle", "spoon", "season", "garnish", "fluff",
    "create", "drain", "discard", "skim", "scrape", "pat", "trim",
    "gently", "carefully", "slowly", "while", "once", "after", "before",
    "meanwhile", "during", "remove", "blend", "puree", "purée",
    "microwave", "pulse", "stuff", "tuck", "nestle", "roll", "fold",
    "shape", "form", "crack", "beat", "fluff",
]


_STOPWORDS = {
    "a", "an", "the", "in", "on", "to", "for", "with", "your", "until",
    "and", "of", "over", "into", "through", "from", "about", "this",
    "that", "some", "by", "as", "at", "or", "but", "if", "is", "are",
    "be", "you",
}


def _step_label_and_body(step: str, idx: int) -> tuple[str, str]:
    """Split an instruction into a 1-2 word bold action label and a body.
    The label is always derived from the first meaningful words so it never
    falls back to a generic 'Step N:' string.
    """
    txt = step.strip()
    import re
    m = re.match(r"^\s*\d+[.)]\s*", txt)
    if m:
        txt = txt[m.end():]

    words = txt.split()
    if not words:
        return "", txt

    # Strategy 1: if the first word is an action verb, use it + next noun.
    first = words[0].rstrip(",.;:").lower()
    label_words: list[str] = []
    if first in _ACTION_VERBS:
        label_words.append(words[0].rstrip(",.;:").capitalize())
        for w in words[1:5]:
            wl = w.rstrip(",.;:").lower()
            if wl in _STOPWORDS:
                continue
            label_words.append(w.rstrip(",.;:").capitalize())
            if len(label_words) >= 2:
                break
    else:
        # Strategy 2: scan first 6 words for an action verb.
        for i, w in enumerate(words[:6]):
            wl = w.rstrip(",.;:").lower()
            if wl in _ACTION_VERBS:
                label_words.append(w.rstrip(",.;:").capitalize())
                # add next non-stopword
                for w2 in words[i + 1:i + 5]:
                    wl2 = w2.rstrip(",.;:").lower()
                    if wl2 in _STOPWORDS:
                        continue
                    label_words.append(w2.rstrip(",.;:").capitalize())
                    break
                break

    if not label_words:
        # Strategy 3: just take first 2 meaningful words.
        for w in words[:6]:
            wl = w.rstrip(",.;:").lower()
            if wl in _STOPWORDS:
                continue
            label_words.append(w.rstrip(",.;:").capitalize())
            if len(label_words) >= 2:
                break

    if not label_words:
        return "", txt

    return " ".join(label_words) + ":", txt


def _format_ingredient_line(item: str) -> tuple[str, str]:
    """Try to split an ingredient like '8 oz spaghetti' into ('Spaghetti:', '8 oz').
    Heuristic: if the item starts with a quantity, separate the qty from the name.
    Returns (bold_label, value). If we can't confidently split, returns ('', item)."""
    import re
    txt = item.strip()
    # Match a leading quantity: number, fraction, or both, optional unit
    m = re.match(
        r"^\s*([\d/.\s]+(?:cups?|cup|tbsp|tsp|oz|lbs?|lb|grams?|g|kg|ml|l|pinch|cloves?|sprigs?)?\s*[-–—]?\s*)(.+)$",
        txt, flags=re.IGNORECASE,
    )
    if m:
        qty = m.group(1).strip(" -–—")
        name = m.group(2).strip()
        if qty and name:
            # Capitalize first letter of name for the label
            label_name = name.split(",")[0].strip()
            label = label_name[:30].title() + ":"
            value = txt
            return label, value
    return "", txt


def composite_recipe_page(recipe: dict, out_path: str,
                          top_photo_path: Optional[str] = None,
                          photo_height: int = 440) -> str:
    """Premium cookbook-page recipe slide.
    All content sits in the central ~78% width to clear TikTok right-rail UI.

    If ``top_photo_path`` is provided, the food photo is rendered full-bleed
    at the top of the slide (``photo_height`` px) and the recipe content
    starts below it. Used for Instagram 10-slide carousels where we trim
    the standalone photo slide by merging it into the recipe page.
    """
    canvas = _parchment_gradient_bg()
    _draw_parchment_texture(canvas)

    # ---- Optional top photo (combined Instagram-style slide) ----
    PHOTO_H = photo_height if top_photo_path else 0
    if top_photo_path and os.path.exists(top_photo_path):
        src_photo = Image.open(top_photo_path).convert("RGB")
        photo_fit = _fit_image_cover(src_photo, SLIDE_W, PHOTO_H).convert("RGBA")
        canvas.alpha_composite(photo_fit, (0, 0))
        # Soft fade at the bottom of the photo so it transitions into parchment
        fade = Image.new("RGBA", (SLIDE_W, 80), (0, 0, 0, 0))
        fd = ImageDraw.Draw(fade)
        for fy in range(80):
            a = int(140 * (fy / 80) ** 1.5)
            fd.line([(0, fy), (SLIDE_W, fy)], fill=(20, 12, 8, a))
        canvas.alpha_composite(fade, (0, PHOTO_H - 80))

    d = ImageDraw.Draw(canvas)

    # Safe-zone padding (clears TikTok UI on both sides)
    SAFE_X = 110     # left+right padding
    safe_w = SLIDE_W - 2 * SAFE_X

    # ---- Top decorative double-line (below photo if present) ----
    line_y = PHOTO_H + 30 if PHOTO_H else 90
    d.rectangle([(SAFE_X, line_y), (SLIDE_W - SAFE_X, line_y + 5)], fill=PARCHMENT_TITLE)
    d.rectangle([(SAFE_X, line_y + 15), (SLIDE_W - SAFE_X, line_y + 19)], fill=PARCHMENT_TITLE)

    # ---- Title — fit within safe-w, max 2 lines, all caps ----
    title = recipe["title"].upper()
    # When a photo is present, give the title a touch less room so columns get more
    max_title_size = 52 if PHOTO_H else 60
    size = max_title_size
    while size > 32:
        title_font = _load_font(size, weight="xbold")
        lines = _wrap(title, title_font, safe_w)
        if len(lines) <= 2:
            break
        size -= 3
    title_y = line_y + 55
    line_h = int(title_font.size * 1.0)
    for i, line in enumerate(lines):
        bbox = d.textbbox((0, 0), line, font=title_font)
        tw = bbox[2] - bbox[0]
        d.text(((SLIDE_W - tw) // 2, title_y + i * (line_h + 6)),
               line, font=title_font, fill=PARCHMENT_TITLE)

    title_block_bottom = title_y + line_h * len(lines) + 14

    # ---- Bottom of title divider ----
    d.rectangle([(SAFE_X, title_block_bottom + 8),
                 (SLIDE_W - SAFE_X, title_block_bottom + 12)], fill=PARCHMENT_TITLE)
    d.rectangle([(SAFE_X, title_block_bottom + 22),
                 (SLIDE_W - SAFE_X, title_block_bottom + 26)], fill=PARCHMENT_TITLE)

    # ---- Two columns: INGREDIENTS (left) and INSTRUCTIONS (right) ----
    col_top = title_block_bottom + 80
    col_gap = 40
    col_w = (safe_w - col_gap) // 2
    left_x = SAFE_X
    right_x = SAFE_X + col_w + col_gap

    # Reserve 140px at the bottom for the watermark/footer band so absolutely
    # no text can collide with the RECIPEVAULT footer.
    FOOTER_RESERVE = 140
    available_h = SLIDE_H - col_top - FOOTER_RESERVE - int(34 * 1.40)
    # ^ subtract the height of the "INGREDIENTS:" / "INSTRUCTIONS:" headers

    sections = recipe.get("ingredient_sections", [])
    steps_list = recipe.get("instructions", [])

    # ---- Iteratively pick a body font size that makes BOTH columns fit ----
    chosen_body_size = 22
    for body_size in range(22, 13, -1):
        section_size = max(body_size + 2, body_size)  # roughly ~24-16 range
        sec_f = _load_font(section_size, weight="xbold")
        bod_f = _load_font(body_size, weight="regular")
        bld_f = _load_font(body_size, weight="bold")

        # Measure ingredients column
        ing_h = 0
        for sec in sections:
            ing_h += int(sec_f.size * 1.30)
            for item in sec.get("items", []):
                _, body_txt = _format_ingredient_line(item)
                bullet = "• "
                bullet_w = ImageDraw.Draw(canvas).textbbox(
                    (0, 0), bullet, font=bld_f)[2]
                avail_w = col_w - bullet_w - 8
                wrapped = _wrap(body_txt, bod_f, avail_w)
                ing_h += int(bod_f.size * 1.28) * max(1, len(wrapped))
            ing_h += 10

        # Measure instructions column
        ins_h = 0
        tmp_d = ImageDraw.Draw(canvas)
        for ix, step in enumerate(steps_list, 1):
            label, body_txt = _step_label_and_body(step, ix)
            prefix = f"{ix}. "
            prefix_w = tmp_d.textbbox((0, 0), prefix, font=bld_f)[2]
            label_w = tmp_d.textbbox((0, 0), label, font=bld_f)[2]
            full_prefix_w = prefix_w + label_w + 8
            avail_w = col_w - full_prefix_w
            wrapped_first = _wrap(body_txt, bod_f, avail_w) if avail_w > 60 \
                else _wrap(body_txt, bod_f, col_w - 18)
            n_lines = max(1, len(wrapped_first))
            ins_h += int(bod_f.size * 1.28) * n_lines + 8

        if max(ing_h, ins_h) <= available_h:
            chosen_body_size = body_size
            break
    else:
        chosen_body_size = 14  # smallest we go; will likely truncate

    header_font = _load_font(34, weight="xbold")
    section_font = _load_font(chosen_body_size + 2, weight="xbold")
    body_font = _load_font(chosen_body_size, weight="regular")
    body_bold = _load_font(chosen_body_size, weight="bold")

    # Domain-aware column headers — food keeps the cookbook-style INGREDIENTS
    # / INSTRUCTIONS labels, anything else uses generic OVERVIEW / KEY POINTS
    # so the slide reads correctly for fitness, finance, productivity etc.
    is_food = _is_food_item(recipe)
    LEFT_HEADER  = "INGREDIENTS:" if is_food else "OVERVIEW:"
    RIGHT_HEADER = "INSTRUCTIONS:" if is_food else "KEY POINTS:"

    # ---- Left column: INGREDIENTS / OVERVIEW ----
    y = col_top
    LEFT_MAX_Y = SLIDE_H - FOOTER_RESERVE
    d.text((left_x, y), LEFT_HEADER, font=header_font, fill=PARCHMENT_HEADER)
    y += int(header_font.size * 1.40)

    for sec in sections:
        if y > LEFT_MAX_Y - int(section_font.size * 1.4):
            break
        d.text((left_x, y), sec["name"] + ":", font=section_font, fill=PARCHMENT_HEADER)
        y += int(section_font.size * 1.30)
        for item in sec.get("items", []):
            if y > LEFT_MAX_Y:
                break
            _, body_txt = _format_ingredient_line(item)
            bullet = "• "
            d.text((left_x + 4, y), bullet, font=body_bold, fill=PARCHMENT_HEADER)
            bullet_w = d.textbbox((0, 0), bullet, font=body_bold)[2]
            avail_w = col_w - bullet_w - 8
            text_x = left_x + 4 + bullet_w
            wrapped = _wrap(body_txt, body_font, avail_w)
            for j, w_line in enumerate(wrapped):
                if y > LEFT_MAX_Y:
                    break
                tx = text_x if j == 0 else left_x + 4 + bullet_w
                d.text((tx, y), w_line, font=body_font, fill=PARCHMENT_BODY)
                y += int(body_font.size * 1.28)
        y += 10

    # ---- Right column: INSTRUCTIONS / KEY POINTS (with bold action labels) ----
    y = col_top
    # Hard ceiling: anything past this y must NOT be drawn (footer reserve).
    MAX_Y = SLIDE_H - FOOTER_RESERVE
    d.text((right_x, y), RIGHT_HEADER, font=header_font, fill=PARCHMENT_HEADER)
    y += int(header_font.size * 1.40)

    line_h_body = int(body_font.size * 1.28)
    for idx, step in enumerate(recipe.get("instructions", []), 1):
        # Stop if even the first line of this step won't fit
        if y + line_h_body > MAX_Y:
            break
        label, body_txt = _step_label_and_body(step, idx)
        prefix = f"{idx}. "
        d.text((right_x, y), prefix, font=body_bold, fill=PARCHMENT_HEADER)
        prefix_w = d.textbbox((0, 0), prefix, font=body_bold)[2]
        d.text((right_x + prefix_w, y), label, font=body_bold, fill=PARCHMENT_HEADER)
        label_w = d.textbbox((0, 0), label, font=body_bold)[2]
        full_prefix_w = prefix_w + label_w + 8
        avail_w = max(60, col_w - full_prefix_w)
        wrapped_first = _wrap(body_txt, body_font, avail_w)
        first_line = wrapped_first[0] if wrapped_first else ""
        d.text((right_x + full_prefix_w, y), first_line, font=body_font,
               fill=PARCHMENT_BODY)
        y += line_h_body
        if len(wrapped_first) > 1:
            cont_text = " ".join(wrapped_first[1:])
            cont_wrapped = _wrap(cont_text, body_font, col_w - 18)
            stopped = False
            for w_line in cont_wrapped:
                # Per-line check — never let a wrapped line cross MAX_Y
                if y + line_h_body > MAX_Y:
                    stopped = True
                    break
                d.text((right_x + 18, y), w_line, font=body_font,
                       fill=PARCHMENT_BODY)
                y += line_h_body
            if stopped:
                break  # don't render any more steps
        y += 8

    # ---- Bottom decorative band + brand watermark ----
    d.rectangle([(SAFE_X, SLIDE_H - 90), (SLIDE_W - SAFE_X, SLIDE_H - 86)],
                fill=PARCHMENT_TITLE)
    d.rectangle([(SAFE_X, SLIDE_H - 76), (SLIDE_W - SAFE_X, SLIDE_H - 73)],
                fill=PARCHMENT_TITLE)

    # Domain-flavoured watermark: food slides keep the meal-planner tagline,
    # everything else uses the generic SlideCast brand line.
    wm_font = _load_font(22, weight="bold")
    wm = "THE SLIDECAST  /  meal planner & grocery list" if is_food \
        else "THE SLIDECAST  /  save & share carousels"
    bbox = d.textbbox((0, 0), wm, font=wm_font)
    wm_w = bbox[2] - bbox[0]
    d.text(((SLIDE_W - wm_w) // 2, SLIDE_H - 56), wm,
           font=wm_font, fill=PARCHMENT_TITLE)

    canvas.convert("RGB").save(out_path, "PNG")
    return out_path


# ---------------------------------------------------------------------------
# Slide type: CTA (mid-carousel, with cta_card.png embedded)
# ---------------------------------------------------------------------------

def composite_cta(cta_lines: list[str], out_path: str,
                  *, app_name: Optional[str] = None,
                  is_recipevault: bool = False) -> str:
    """Mid-carousel CTA: warm coral pink with radial-style shading.
    Layout: caption text sits in upper-middle, app card sits DIRECTLY
    below it. The whole text+card group is centered vertically and stays
    inside the 75% horizontal safe zone.

    Card behaviour:
      - ``is_recipevault=True``  → embed the static ``assets/cta_card.png``
        (RecipeVault recipe-keeper card). Use ONLY for RecipeVault carousels.
      - ``app_name=<str>``       → render a text-based pill-card with "Get
        <app_name>". Used when the user mentioned their own app in the brief.
      - neither                  → no card; the CTA lines stand alone."""
    # Build a vertical pink gradient with subtle radial brightening
    grad = Image.new("RGBA", (SLIDE_W, SLIDE_H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(SLIDE_H):
        f = y / SLIDE_H
        # darker top, brighter middle, slightly darker bottom — premium feel
        bri = 0.88 + 0.18 * (1 - abs(f - 0.45) * 2)
        r = max(0, min(255, int(CTA_BG[0] * bri)))
        g = max(0, min(255, int(CTA_BG[1] * bri)))
        b = max(0, min(255, int(CTA_BG[2] * bri)))
        gd.line([(0, y), (SLIDE_W, y)], fill=(r, g, b, 255))
    canvas = grad

    # Add a soft radial highlight in the upper-middle for depth
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gld = ImageDraw.Draw(glow)
    cx, cy = SLIDE_W // 2, int(SLIDE_H * 0.42)
    for i in range(40):
        r = 380 - i * 8
        a = int(80 * (1 - i / 40))
        gld.ellipse([(cx - r, cy - r), (cx + r, cy + r)],
                    fill=(255, 200, 200, a))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    canvas.alpha_composite(glow)

    d = ImageDraw.Draw(canvas)

    # ---- Text — keep within 75% width safe zone ----
    SAFE_X = 130
    max_w = SLIDE_W - 2 * SAFE_X  # = 820 ~ 76% width
    base_size = 80 if len(cta_lines) >= 3 else 92
    line_blocks = []  # (text, font, line_h)
    for line in cta_lines:
        size = base_size
        while size > 40:
            f = _load_font(size, weight="xbold")
            wrapped = _wrap(line, f, max_w)
            if len(wrapped) == 1:
                break
            size -= 4
        else:
            f = _load_font(size, weight="xbold")
            wrapped = _wrap(line, f, max_w)
        for sub in wrapped:
            line_blocks.append((sub, f, int(f.size * 1.15)))

    text_h = sum(lh for _, _, lh in line_blocks)

    # ---- Build the CTA card (sits directly under text) ----
    # Three modes: RecipeVault image / user-app text pill / nothing
    card = None
    card_h = 0
    if is_recipevault and os.path.exists(CTA_CARD_PATH):
        card = Image.open(CTA_CARD_PATH).convert("RGBA")
        target_w = 760  # respects safe zone (~70% width)
        ratio = target_w / card.width
        card = card.resize((target_w, int(card.height * ratio)), Image.LANCZOS)
        card_h = card.height
    elif app_name:
        # Render a clean white-pill card with the user's app name. Strips a
        # leading "@" or trailing TLD ("focuskit.app" → "focuskit") so the
        # name reads naturally on the slide.
        import re as _re_local
        display = app_name.lstrip("@")
        if display.lower().startswith(("http://", "https://")):
            # Use just the hostname's first label as the display name
            display = display.split("://", 1)[-1].split("/", 1)[0].split(".", 1)[0]
        display = _re_local.sub(r"\.(com|app|io|co|ai|net|org)$", "", display, flags=_re_local.IGNORECASE)
        # Card dimensions
        card_w = 760
        card_h = 200
        card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        # White rounded pill background
        cd.rounded_rectangle([(0, 0), (card_w, card_h)],
                             radius=32, fill=(255, 255, 255, 255))
        # "Get / Try" small label
        kicker_font = _load_font(24, weight="bold")
        kicker = "GET THE APP"
        kbb = cd.textbbox((0, 0), kicker, font=kicker_font)
        kw_ = kbb[2] - kbb[0]
        cd.text(((card_w - kw_) // 2, 32), kicker,
                font=kicker_font, fill=(180, 80, 100, 255))
        # Big app name in coral
        name_font = _load_font(64, weight="xbold")
        # Auto-shrink long names
        while name_font.size > 40:
            nbb = cd.textbbox((0, 0), display, font=name_font)
            if (nbb[2] - nbb[0]) <= card_w - 80:
                break
            name_font = _load_font(name_font.size - 4, weight="xbold")
        nbb = cd.textbbox((0, 0), display, font=name_font)
        nw_ = nbb[2] - nbb[0]
        cd.text(((card_w - nw_) // 2, 72), display,
                font=name_font, fill=CTA_BG)
        # Optional link/handle line if app_name was a URL or @handle
        if app_name != display:
            sub_font = _load_font(20, weight="regular")
            sub = app_name if len(app_name) <= 36 else app_name[:33] + "…"
            sbb = cd.textbbox((0, 0), sub, font=sub_font)
            sw_ = sbb[2] - sbb[0]
            cd.text(((card_w - sw_) // 2, card_h - 36), sub,
                    font=sub_font, fill=(120, 60, 80, 200))

    # ---- Center the whole group (text + 32px gap + card) vertically ----
    GAP = 56
    group_h = text_h + (GAP + card_h if card else 0)
    group_top = (SLIDE_H - group_h) // 2

    # Draw text with a subtle drop shadow so it pops on the pink
    y = group_top
    for text, f, lh in line_blocks:
        bbox = d.textbbox((0, 0), text, font=f)
        tw = bbox[2] - bbox[0]
        x = (SLIDE_W - tw) // 2
        # shadow
        sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        sd.text((x + 3, y + 3), text, font=f, fill=(0, 0, 0, 100))
        sh = sh.filter(ImageFilter.GaussianBlur(4))
        canvas.alpha_composite(sh)
        # main text
        ImageDraw.Draw(canvas).text((x, y), text, font=f, fill=CTA_TEXT)
        y += lh

    # Place the card directly below the text (with GAP)
    if card is not None:
        cx_pos = (SLIDE_W - card.width) // 2
        cy_pos = group_top + text_h + GAP
        # Subtle drop shadow under the card for depth
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        sd2 = ImageDraw.Draw(shadow)
        sd2.rounded_rectangle(
            [(cx_pos + 6, cy_pos + 12),
             (cx_pos + card.width - 6, cy_pos + card.height + 18)],
            radius=24, fill=(0, 0, 0, 70),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(14))
        canvas.alpha_composite(shadow)
        canvas.alpha_composite(card, (cx_pos, cy_pos))

    canvas.convert("RGB").save(out_path, "PNG")
    return out_path
