"""Universal slide compositor for template engine.

Supported slide types (driven by `spec["type"]`):
  hook          : full-bleed photo + big headline
  list_card     : big number + title + body, photo background dimmed
  tip_card      : tip card style — title in big text, body below, dimmed photo
  mistake_fix   : split slide — top half "MISTAKE" + body, bottom half "DO THIS"
  block_card    : labeled block (e.g. "THE PROBLEM" / "BEFORE") + title + body
  feature_card  : numbered feature with photo + title + body
  cta           : full-bleed photo + brand logo + caption + URL/handle
"""
from __future__ import annotations
import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import Optional


SLIDE_W, SLIDE_H = 1080, 1350

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
_FONT_DIR = os.path.normpath(os.path.join(_ROOT, "assets", "fonts"))

FONT_BOLD = os.path.join(_FONT_DIR, "PlusJakartaSans-Bold.ttf")
FONT_XBOLD = os.path.join(_FONT_DIR, "PlusJakartaSans-ExtraBold.ttf")
FONT_REG = os.path.join(_FONT_DIR, "PlusJakartaSans-Regular.ttf")

_FALLBACK = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size: int, weight: str = "bold") -> ImageFont.FreeTypeFont:
    paths = []
    if weight == "xbold":
        paths.append(FONT_XBOLD)
    if weight in ("bold", "xbold"):
        paths.append(FONT_BOLD)
    if weight == "regular":
        paths.append(FONT_REG)
    paths.extend(_FALLBACK)
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _fit_cover(src: Image.Image, w: int, h: int) -> Image.Image:
    sw, sh = src.size
    sr = sw / sh
    tr = w / h
    if sr > tr:
        nh = h; nw = int(h * sr)
    else:
        nw = w; nh = int(w / sr)
    src = src.resize((nw, nh), Image.LANCZOS)
    x = (nw - w) // 2
    y = (nh - h) // 2
    return src.crop((x, y, x + w, y + h))


def _wrap(text: str, font, max_w: int) -> list[str]:
    out = []
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    for para in text.split("\n"):
        words = para.split()
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


def _stroked_text(canvas, xy, text, font, fill=(255, 255, 255),
                  stroke=(0, 0, 0), stroke_w=3, shadow=True):
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
        sh = sh.filter(ImageFilter.GaussianBlur(4))
        canvas.alpha_composite(sh)
    d.text((x, y), text, font=font, fill=fill,
           stroke_width=stroke_w, stroke_fill=stroke)


def _photo_canvas(image_path: Optional[str], dim: float = 0.45) -> Image.Image:
    """Load a photo and return a 1080x1350 dimmed canvas. Falls back to gradient."""
    if image_path and os.path.exists(image_path):
        try:
            src = Image.open(image_path).convert("RGB")
            canvas = _fit_cover(src, SLIDE_W, SLIDE_H).convert("RGBA")
        except Exception:
            canvas = _gradient_bg()
    else:
        canvas = _gradient_bg()
    # Dim layer for legibility
    dim_layer = Image.new("RGBA", canvas.size, (0, 0, 0, int(255 * dim)))
    canvas.alpha_composite(dim_layer)
    return canvas


def _gradient_bg() -> Image.Image:
    canvas = Image.new("RGBA", (SLIDE_W, SLIDE_H), (24, 18, 16, 255))
    d = ImageDraw.Draw(canvas)
    for y in range(SLIDE_H):
        f = y / SLIDE_H
        r = int(24 + 30 * f); g = int(18 + 20 * f); b = int(16 + 20 * f)
        d.line([(0, y), (SLIDE_W, y)], fill=(r, g, b, 255))
    return canvas


def _brand_color(brand: dict) -> tuple[int, int, int]:
    hexs = (brand or {}).get("primary_color", "#ff5c7a")
    try:
        h = hexs.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return (255, 92, 122)


# ---------------------------------------------------------------------------
# Slide renderers
# ---------------------------------------------------------------------------

def _render_hook(spec, brand, image_path, out_path):
    canvas = _photo_canvas(image_path, dim=0.40)
    text = spec.get("caption", "")
    safe_w = int(SLIDE_W * 0.78)
    size = 100
    while size > 50:
        font = _font(size, "xbold")
        lines = _wrap(text, font, safe_w)
        if len(lines) <= 3:
            break
        size -= 6
    lh = int(font.size * 1.05)
    total_h = lh * len(lines) + 14 * (len(lines) - 1)
    y0 = (SLIDE_H - total_h) // 2 + lh // 2
    for i, line in enumerate(lines):
        _stroked_text(canvas, (SLIDE_W // 2, y0 + i * (lh + 14)),
                      line, font, stroke_w=5)
    canvas.convert("RGB").save(out_path, "PNG")


def _render_list_card(spec, brand, image_path, out_path):
    canvas = _photo_canvas(image_path, dim=0.55)
    d = ImageDraw.Draw(canvas)
    safe_w = int(SLIDE_W * 0.78)
    color = _brand_color(brand)
    # Big number top-left of central block
    num = str(spec.get("number", ""))
    num_font = _font(220, "xbold")
    num_bbox = d.textbbox((0, 0), num, font=num_font)
    num_w = num_bbox[2] - num_bbox[0]
    d.text(((SLIDE_W - num_w) // 2, 200), num, font=num_font,
           fill=(*color, 255), stroke_width=4, stroke_fill=(0, 0, 0))
    # Title
    title = spec.get("title", "")
    title_size = 64
    while title_size > 36:
        tf = _font(title_size, "xbold")
        tlines = _wrap(title, tf, safe_w)
        if len(tlines) <= 2:
            break
        title_size -= 4
    tlh = int(tf.size * 1.05)
    ty = 470
    for i, ln in enumerate(tlines):
        _stroked_text(canvas, (SLIDE_W // 2, ty + i * (tlh + 6)),
                      ln, tf, stroke_w=4)
    # Body
    body = spec.get("body", "")
    body_size = 36
    while body_size > 22:
        bf = _font(body_size, "regular")
        blines = _wrap(body, bf, safe_w)
        if len(blines) <= 6:
            break
        body_size -= 2
    by = ty + tlh * len(tlines) + 40
    blh = int(bf.size * 1.30)
    for i, ln in enumerate(blines):
        _stroked_text(canvas, (SLIDE_W // 2, by + i * blh),
                      ln, bf, stroke_w=3, shadow=False)
    canvas.convert("RGB").save(out_path, "PNG")


def _render_tip_card(spec, brand, image_path, out_path):
    # Same as list_card but with a colored "TIP #N" tag instead of huge number
    canvas = _photo_canvas(image_path, dim=0.58)
    d = ImageDraw.Draw(canvas)
    safe_w = int(SLIDE_W * 0.78)
    color = _brand_color(brand)
    # Tag
    tag = f"TIP {spec.get('number', '')}"
    tag_font = _font(36, "xbold")
    tag_bbox = d.textbbox((0, 0), tag, font=tag_font)
    tag_w = tag_bbox[2] - tag_bbox[0]
    tag_h = 56
    tag_x = (SLIDE_W - tag_w - 56) // 2
    d.rounded_rectangle([(tag_x, 280), (tag_x + tag_w + 56, 280 + tag_h)],
                        radius=28, fill=(*color, 255))
    d.text((tag_x + 28, 280 + (tag_h - 36) // 2 - 4), tag,
           font=tag_font, fill=(20, 12, 12, 255))
    # Title
    title = spec.get("title", "")
    title_size = 78
    while title_size > 40:
        tf = _font(title_size, "xbold")
        tlines = _wrap(title, tf, safe_w)
        if len(tlines) <= 2:
            break
        title_size -= 4
    tlh = int(tf.size * 1.0)
    ty = 460
    for i, ln in enumerate(tlines):
        _stroked_text(canvas, (SLIDE_W // 2, ty + i * (tlh + 6)),
                      ln, tf, stroke_w=4)
    # Body
    body = spec.get("body", "")
    body_size = 40
    while body_size > 24:
        bf = _font(body_size, "regular")
        blines = _wrap(body, bf, safe_w)
        if len(blines) <= 6:
            break
        body_size -= 2
    by = ty + tlh * len(tlines) + 50
    blh = int(bf.size * 1.30)
    for i, ln in enumerate(blines):
        _stroked_text(canvas, (SLIDE_W // 2, by + i * blh),
                      ln, bf, stroke_w=3, shadow=False)
    canvas.convert("RGB").save(out_path, "PNG")


def _render_mistake_fix(spec, brand, image_path, out_path):
    """Split slide: top half = MISTAKE (red wash), bottom half = FIX (brand color)."""
    color = _brand_color(brand)
    half = SLIDE_H // 2
    canvas_top = _photo_canvas(image_path, dim=0.55).crop((0, 0, SLIDE_W, half))
    canvas_bot = _photo_canvas(image_path, dim=0.55).crop((0, half, SLIDE_W, SLIDE_H))
    canvas = Image.new("RGBA", (SLIDE_W, SLIDE_H))
    # Red wash on top
    red_wash = Image.new("RGBA", (SLIDE_W, half), (180, 30, 40, 110))
    canvas.alpha_composite(canvas_top, (0, 0))
    canvas.alpha_composite(red_wash, (0, 0))
    # Brand-color wash on bottom
    bot_wash = Image.new("RGBA", (SLIDE_W, half), (*color, 100))
    canvas.alpha_composite(canvas_bot, (0, half))
    canvas.alpha_composite(bot_wash, (0, half))

    d = ImageDraw.Draw(canvas)
    safe_w = int(SLIDE_W * 0.82)
    # MISTAKE block
    tag_font = _font(32, "xbold")
    d.text((SLIDE_W // 2 - 100, 80), "✗ MISTAKE", font=tag_font, fill=(255, 220, 220, 255))
    title_font = _font(56, "xbold")
    tlines = _wrap(spec.get("mistake_title", ""), title_font, safe_w)[:2]
    for i, ln in enumerate(tlines):
        _stroked_text(canvas, (SLIDE_W // 2, 180 + i * 64), ln, title_font, stroke_w=3)
    body_font = _font(30, "regular")
    blines = _wrap(spec.get("mistake_body", ""), body_font, safe_w)[:4]
    for i, ln in enumerate(blines):
        _stroked_text(canvas, (SLIDE_W // 2, 310 + i * 40), ln, body_font,
                      stroke_w=2, shadow=False)
    # FIX block
    d.text((SLIDE_W // 2 - 90, half + 80), "✓ DO THIS", font=tag_font, fill=(*color, 255))
    tlines = _wrap(spec.get("fix_title", ""), title_font, safe_w)[:2]
    for i, ln in enumerate(tlines):
        _stroked_text(canvas, (SLIDE_W // 2, half + 180 + i * 64), ln, title_font, stroke_w=3)
    blines = _wrap(spec.get("fix_body", ""), body_font, safe_w)[:4]
    for i, ln in enumerate(blines):
        _stroked_text(canvas, (SLIDE_W // 2, half + 310 + i * 40), ln, body_font,
                      stroke_w=2, shadow=False)
    canvas.convert("RGB").save(out_path, "PNG")


def _render_block_card(spec, brand, image_path, out_path):
    canvas = _photo_canvas(image_path, dim=0.55)
    d = ImageDraw.Draw(canvas)
    safe_w = int(SLIDE_W * 0.80)
    color = _brand_color(brand)
    # Label tag
    label = spec.get("label", "")
    label_font = _font(34, "xbold")
    lb_bbox = d.textbbox((0, 0), label, font=label_font)
    lb_w = lb_bbox[2] - lb_bbox[0]
    lb_h = 56
    lb_x = (SLIDE_W - lb_w - 56) // 2
    d.rounded_rectangle([(lb_x, 300), (lb_x + lb_w + 56, 300 + lb_h)],
                        radius=28, fill=(*color, 255))
    d.text((lb_x + 28, 300 + (lb_h - 34) // 2 - 4), label,
           font=label_font, fill=(20, 12, 12, 255))
    # Title
    title = spec.get("title", "")
    title_size = 76
    while title_size > 40:
        tf = _font(title_size, "xbold")
        tlines = _wrap(title, tf, safe_w)
        if len(tlines) <= 2: break
        title_size -= 4
    ty = 470
    tlh = int(tf.size * 1.0)
    for i, ln in enumerate(tlines):
        _stroked_text(canvas, (SLIDE_W // 2, ty + i * (tlh + 6)), ln, tf, stroke_w=4)
    # Body
    body = spec.get("body", "")
    body_size = 38
    while body_size > 24:
        bf = _font(body_size, "regular")
        blines = _wrap(body, bf, safe_w)
        if len(blines) <= 7: break
        body_size -= 2
    by = ty + tlh * len(tlines) + 60
    blh = int(bf.size * 1.30)
    for i, ln in enumerate(blines):
        _stroked_text(canvas, (SLIDE_W // 2, by + i * blh), ln, bf,
                      stroke_w=3, shadow=False)
    canvas.convert("RGB").save(out_path, "PNG")


def _render_feature_card(spec, brand, image_path, out_path):
    # Same as list_card but uses a colored "FEATURE #N" tag
    spec2 = dict(spec)
    spec2["__feature__"] = True
    canvas = _photo_canvas(image_path, dim=0.55)
    d = ImageDraw.Draw(canvas)
    safe_w = int(SLIDE_W * 0.80)
    color = _brand_color(brand)
    tag = f"FEATURE 0{spec.get('number', '')}"
    tag_font = _font(34, "xbold")
    tag_bbox = d.textbbox((0, 0), tag, font=tag_font)
    tag_w = tag_bbox[2] - tag_bbox[0]
    tag_h = 56
    tag_x = (SLIDE_W - tag_w - 56) // 2
    d.rounded_rectangle([(tag_x, 280), (tag_x + tag_w + 56, 280 + tag_h)],
                        radius=28, fill=(*color, 255))
    d.text((tag_x + 28, 280 + (tag_h - 34) // 2 - 4), tag,
           font=tag_font, fill=(20, 12, 12, 255))
    title = spec.get("title", "")
    title_size = 76
    while title_size > 40:
        tf = _font(title_size, "xbold")
        tlines = _wrap(title, tf, safe_w)
        if len(tlines) <= 2: break
        title_size -= 4
    ty = 450
    tlh = int(tf.size * 1.0)
    for i, ln in enumerate(tlines):
        _stroked_text(canvas, (SLIDE_W // 2, ty + i * (tlh + 6)), ln, tf, stroke_w=4)
    body = spec.get("body", "")
    body_size = 38
    while body_size > 24:
        bf = _font(body_size, "regular")
        blines = _wrap(body, bf, safe_w)
        if len(blines) <= 6: break
        body_size -= 2
    by = ty + tlh * len(tlines) + 50
    blh = int(bf.size * 1.30)
    for i, ln in enumerate(blines):
        _stroked_text(canvas, (SLIDE_W // 2, by + i * blh), ln, bf,
                      stroke_w=3, shadow=False)
    canvas.convert("RGB").save(out_path, "PNG")


def _render_cta(spec, brand, image_path, out_path):
    """Brand-customized closer slide.
    Uses brand.primary_color as the background, brand.logo_path (if any) as a card,
    brand.name + brand.cta_text + brand.cta_url as text.
    """
    color = _brand_color(brand)
    # Vertical gradient using brand color
    grad = Image.new("RGBA", (SLIDE_W, SLIDE_H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(SLIDE_H):
        f = y / SLIDE_H
        bri = 0.85 + 0.20 * (1 - abs(f - 0.45) * 2)
        r = max(0, min(255, int(color[0] * bri)))
        g = max(0, min(255, int(color[1] * bri)))
        b = max(0, min(255, int(color[2] * bri)))
        gd.line([(0, y), (SLIDE_W, y)], fill=(r, g, b, 255))
    canvas = grad
    d = ImageDraw.Draw(canvas)

    # Caption
    caption = spec.get("caption", "Save these for later.")
    safe_w = int(SLIDE_W * 0.78)
    size = 80
    while size > 40:
        f = _font(size, "xbold")
        lines = _wrap(caption, f, safe_w)
        if len(lines) <= 3: break
        size -= 4
    lh = int(f.size * 1.10)
    total_h = lh * len(lines)
    cap_y0 = (SLIDE_H - 380) // 2
    for i, ln in enumerate(lines):
        bbox = d.textbbox((0, 0), ln, font=f)
        tw = bbox[2] - bbox[0]
        d.text(((SLIDE_W - tw) // 2, cap_y0 + i * lh), ln,
               font=f, fill=(255, 255, 255, 255))
    after_caption_y = cap_y0 + total_h

    # Brand card with logo + name + CTA
    card_top = after_caption_y + 40
    card_w = 720
    card_h = 200
    card_x = (SLIDE_W - card_w) // 2
    d.rounded_rectangle([(card_x, card_top), (card_x + card_w, card_top + card_h)],
                        radius=24, fill=(255, 255, 255, 250))

    logo_path = (brand or {}).get("logo_path")
    logo_box = (card_x + 24, card_top + 24, card_x + 24 + 152, card_top + card_h - 24)
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((152, 152), Image.LANCZOS)
            lx = logo_box[0] + (152 - logo.width) // 2
            ly = logo_box[1] + (152 - logo.height) // 2
            canvas.alpha_composite(logo, (lx, ly))
        except Exception:
            d.rounded_rectangle(logo_box, radius=18, fill=(*color, 255))
    else:
        d.rounded_rectangle(logo_box, radius=18, fill=(*color, 255))

    # Brand name + URL
    text_x = card_x + 200
    brand_name = (brand or {}).get("name", "Your Brand")
    bname_font = _font(38, "xbold")
    d.text((text_x, card_top + 32), brand_name, font=bname_font, fill=(24, 16, 14, 255))
    cta_text = (brand or {}).get("cta_text", "Get the app")
    cta_font = _font(28, "regular")
    d.text((text_x, card_top + 80), cta_text, font=cta_font, fill=(60, 50, 50, 255))
    cta_url = (brand or {}).get("cta_url", "")
    if cta_url:
        url_font = _font(22, "bold")
        d.text((text_x, card_top + 130), cta_url[:50], font=url_font,
               fill=(*color, 255))

    canvas.convert("RGB").save(out_path, "PNG")


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_RENDERERS = {
    "hook":          _render_hook,
    "list_card":     _render_list_card,
    "tip_card":      _render_tip_card,
    "mistake_fix":   _render_mistake_fix,
    "block_card":    _render_block_card,
    "feature_card":  _render_feature_card,
    "cta":           _render_cta,
}


def render_slide(spec: dict, brand: dict, image_path: Optional[str],
                 out_path: str) -> str:
    fn = _RENDERERS.get(spec.get("type", ""))
    if not fn:
        raise ValueError(f"unknown slide type: {spec.get('type')}")
    fn(spec, brand or {}, image_path, out_path)
    return out_path
