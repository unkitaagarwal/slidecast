"""
Text overlay compositor — clean white text with soft drop shadow, full-bleed food image.

Layout:
    1080 x 1350 slide (Instagram 4:5 portrait)
    Food image scaled-to-cover the full slide (center-crop)
    Text rendered as bold white Inter with a soft, blurred dark drop shadow
    for legibility on any photo — no pill, no rectangle, just clean text.

For the sauce slide (#6) we render multiple small text labels around the bowl,
one per callout ingredient, plus a larger "<sauce name>" label at the bottom.
"""

from __future__ import annotations

import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ---------------------------------------------------------------------------
# Font resolution. We bundle Inter (premium modern sans-serif) in
# ../assets/fonts. Falls back to system fonts if missing.
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_FONT_DIR = os.path.normpath(os.path.join(_HERE, "..", "assets", "fonts"))

FONT_BOLD_PATH = os.path.join(_FONT_DIR, "PlusJakartaSans-Bold.ttf")
FONT_XBOLD_PATH = os.path.join(_FONT_DIR, "PlusJakartaSans-ExtraBold.ttf")
FONT_REG_PATH = os.path.join(_FONT_DIR, "PlusJakartaSans-Regular.ttf")

FALLBACK_BOLD = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _load_font(size: int, *, weight: str = "bold") -> ImageFont.FreeTypeFont:
    paths = []
    if weight == "xbold":
        paths.append(FONT_XBOLD_PATH)
    if weight in ("bold", "xbold"):
        paths.append(FONT_BOLD_PATH)
    if weight == "regular":
        paths.append(FONT_REG_PATH)
    paths.extend(FALLBACK_BOLD)

    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Slide canvas. 1080x1350 = Instagram feed portrait (4:5).
# ---------------------------------------------------------------------------

SLIDE_W, SLIDE_H = 1080, 1350


# ---------------------------------------------------------------------------
# Image fitting: full-bleed, scale-to-cover, center-cropped.
# ---------------------------------------------------------------------------


def _fit_image_cover(src: Image.Image) -> Image.Image:
    """Scale src so it covers SLIDE_W x SLIDE_H, then center-crop."""
    sw, sh = src.size
    scale = max(SLIDE_W / sw, SLIDE_H / sh)
    new_w, new_h = int(sw * scale + 0.5), int(sh * scale + 0.5)
    src = src.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - SLIDE_W) // 2
    top = (new_h - SLIDE_H) // 2
    return src.crop((left, top, left + SLIDE_W, top + SLIDE_H))


# ---------------------------------------------------------------------------
# Clean text drawing — white text on a soft blurred dark drop shadow.
# No pill, no background rectangle. Just legible white text on the photo.
# ---------------------------------------------------------------------------


def _draw_text_centered(
    canvas: Image.Image,
    center_xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    *,
    fg: tuple[int, int, int, int] = (255, 255, 255, 255),
    stroke_width: int = 4,
    stroke_color: tuple[int, int, int, int] = (0, 0, 0, 255),
    shadow: bool = True,
) -> None:
    """Draw centered white text with a sharp black outline. Optionally adds
    a subtle hard drop shadow behind the stroked text for depth — gives the
    type a more 'premium' weight without losing the clean look.
    """
    if not text:
        return

    tmp = ImageDraw.Draw(canvas)
    bbox = tmp.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    text_y_offset = bbox[1]

    cx, cy = center_xy
    text_x = cx - tw // 2 - bbox[0]
    text_y = cy - th // 2 - text_y_offset

    # --- Subtle hard drop shadow for depth (NOT blurry) -----------------------
    if shadow:
        shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_layer)
        sd.text(
            (text_x + 3, text_y + 5),
            text,
            font=font,
            fill=(0, 0, 0, 110),
            stroke_width=stroke_width,
            stroke_fill=(0, 0, 0, 110),
        )
        # very small blur for soft edge but still sharp-feeling
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(2))
        canvas.alpha_composite(shadow_layer)

    fg_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(fg_layer)
    fd.text(
        (text_x, text_y),
        text,
        font=font,
        fill=fg,
        stroke_width=stroke_width,
        stroke_fill=stroke_color,
    )
    canvas.alpha_composite(fg_layer)


# ---------------------------------------------------------------------------
# Caption sizing — bigger for short text, smaller for long titles.
# ---------------------------------------------------------------------------


def _caption_font_size(text: str, *, is_hook: bool = False) -> int:
    """Sized to fit inside TikTok's safe zone (~65% width). Smaller and
    cleaner — multi-line wrapping is fine because the text stays centered."""
    n = len(text)
    if is_hook:
        # Recipe titles — wrap freely onto 2-3 lines, keep size moderate
        if n <= 16:
            return 76
        if n <= 26:
            return 66
        if n <= 36:
            return 58
        return 50
    # Action labels are usually 1-3 words; small enough to fit narrow zone
    if n <= 12:
        return 80
    if n <= 22:
        return 64
    return 54


def _wrap_text_to_width(text: str, font, max_width: int) -> list[str]:
    """Greedy word-wrap. Pre-existing \\n line breaks are preserved."""
    out: list[str] = []
    tmp_img = Image.new("RGBA", (10, 10))
    tmp = ImageDraw.Draw(tmp_img)
    for paragraph in text.split("\n"):
        words = paragraph.split()
        cur = ""
        for w in words:
            trial = (cur + " " + w).strip()
            bbox = tmp.textbbox((0, 0), trial, font=font)
            if bbox[2] - bbox[0] <= max_width or not cur:
                cur = trial
            else:
                out.append(cur)
                cur = w
        if cur:
            out.append(cur)
    return out


# ---------------------------------------------------------------------------
# Main caption / sauce-callouts renderers
# ---------------------------------------------------------------------------


def _draw_caption(
    canvas: Image.Image,
    caption: str,
    *,
    position: str = "center",
    is_hook: bool = False,
    is_final: bool = False,
) -> None:
    if not caption:
        return
    if is_final:
        # Smaller so it fits the narrower TikTok safe zone (65% width).
        size = 42
    else:
        size = _caption_font_size(caption, is_hook=is_hook)
    # Use ExtraBold across all slides now for a heavier, more premium feel
    font = _load_font(size, weight="xbold")

    # Wrap to a max width of ~65% of slide width — leaves 17.5% margin on
    # each side so text never collides with TikTok's right-rail UI chrome
    # (action buttons, account avatar, like/comment/share icons).
    max_text_w = int(SLIDE_W * 0.65)
    lines = _wrap_text_to_width(caption, font, max_text_w)

    # Y anchor depending on position. Hook is now CENTERED.
    if position == "top":
        y_center = 220
    elif position == "bottom":
        y_center = SLIDE_H - 220
    elif position == "below_cta":
        # final slide: caption sits in the upper-middle, ending near the slide center
        y_center = 530
    else:
        y_center = SLIDE_H // 2

    line_gap = 14
    line_h = int(font.size * 1.05)
    total_h = line_h * len(lines) + line_gap * max(0, len(lines) - 1)
    y_start = y_center - total_h // 2 + line_h // 2

    for i, line in enumerate(lines):
        cy = y_start + i * (line_h + line_gap)
        _draw_text_centered(canvas, (SLIDE_W // 2, cy), line, font)


def _draw_apple_logo(d: ImageDraw.ImageDraw, cx: int, cy: int, size: int,
                     color: tuple[int, int, int] = (255, 255, 255),
                     bg: tuple[int, int, int] = (20, 20, 20)) -> None:
    """Draw a simplified Apple logo (filled apple silhouette + leaf) at center
    coordinates (cx, cy) with given diameter size. Uses bg color to subtract
    the bite shape on the right side.
    """
    r = size // 2
    # body
    d.ellipse([(cx - r, cy - r + 2), (cx + r, cy + r + 2)], fill=color)
    # leaf
    d.polygon(
        [
            (cx + 1, cy - r - 1),
            (cx + size * 0.32, cy - r - 8),
            (cx + size * 0.28, cy - r + 4),
        ],
        fill=color,
    )
    # bite cut
    d.ellipse(
        [(cx + r - size * 0.2, cy - size * 0.18),
         (cx + r + size * 0.2, cy + size * 0.22)],
        fill=bg,
    )


def _draw_app_card(canvas: Image.Image, *, app_name: str, app_subtitle: str,
                   tagline: str, top_y: int) -> int:
    """Draw the white app-info card with orange icon + Open button.
    Returns the y coordinate of the bottom of the card."""
    card_w, card_h = 820, 220
    card_x = (SLIDE_W - card_w) // 2
    card_y = top_y

    # Drop shadow
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [(card_x, card_y + 8), (card_x + card_w, card_y + card_h + 14)],
        radius=24, fill=(0, 0, 0, 70),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    canvas.alpha_composite(shadow)

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # White rounded card
    d.rounded_rectangle(
        [(card_x, card_y), (card_x + card_w, card_y + card_h)],
        radius=22, fill=(255, 255, 255, 252),
    )

    # --- Orange icon (clipboard / checklist with utensils style) -------------
    icon_size = 156
    icon_x = card_x + 30
    icon_y = card_y + (card_h - icon_size) // 2
    d.rounded_rectangle(
        [(icon_x, icon_y), (icon_x + icon_size, icon_y + icon_size)],
        radius=34, fill=(245, 124, 50),
    )
    # Inside the icon: 3 horizontal "list rows" each with a check + a line
    row_inset_x = icon_size * 0.20
    row_w = icon_size * 0.62
    row_h = 6
    spacing = icon_size * 0.20
    start_y = icon_y + icon_size * 0.30
    for i in range(3):
        ry = start_y + i * spacing
        # checkmark V on the left
        cx0 = icon_x + row_inset_x
        d.line(
            [(cx0, ry), (cx0 + 8, ry + 8), (cx0 + 22, ry - 8)],
            fill=(255, 255, 255), width=5,
        )
        # row line on the right
        line_x0 = icon_x + row_inset_x + 36
        d.rectangle(
            [(line_x0, ry - row_h // 2), (line_x0 + row_w * 0.7, ry + row_h // 2)],
            fill=(255, 255, 255),
        )
    # crossed fork+knife in top-right corner of icon
    fk_cx = icon_x + icon_size * 0.78
    fk_cy = icon_y + icon_size * 0.22
    d.line([(fk_cx - 8, fk_cy - 8), (fk_cx + 12, fk_cy + 12)], fill=(255, 255, 255), width=4)
    d.line([(fk_cx + 12, fk_cy - 8), (fk_cx - 8, fk_cy + 12)], fill=(255, 255, 255), width=4)

    # --- App name + subtitle + tagline ---------------------------------------
    text_x = icon_x + icon_size + 26
    name_font = _load_font(38, weight="xbold")
    tag_font = _load_font(22, weight="regular")
    d.text(
        (text_x, card_y + 28),
        f"{app_name}:",
        font=name_font, fill=(20, 20, 20),
    )
    d.text(
        (text_x, card_y + 76),
        app_subtitle,
        font=name_font, fill=(20, 20, 20),
    )
    d.text(
        (text_x, card_y + 132),
        tagline,
        font=tag_font, fill=(120, 120, 120),
    )

    # --- Blue Open button (bottom-right of card) ------------------------------
    btn_w, btn_h = 130, 48
    btn_x = card_x + card_w - btn_w - 28
    btn_y = card_y + card_h - btn_h - 24
    d.rounded_rectangle(
        [(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)],
        radius=btn_h // 2, fill=(0, 122, 255),
    )
    btn_font = _load_font(24, weight="xbold")
    d.text(
        (btn_x + btn_w // 2, btn_y + btn_h // 2 + 1),
        "Open",
        font=btn_font, fill=(255, 255, 255), anchor="mm",
    )

    canvas.alpha_composite(layer)
    return card_y + card_h


def _draw_app_store_badge(canvas: Image.Image, top_y: int) -> int:
    """Draw the standalone 'Download on the App Store' black pill below the
    main app card. Returns the y coordinate of the bottom of the badge."""
    badge_w, badge_h = 320, 84
    badge_x = (SLIDE_W - badge_w) // 2
    badge_y = top_y

    # Drop shadow
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [(badge_x, badge_y + 6), (badge_x + badge_w, badge_y + badge_h + 10)],
        radius=14, fill=(0, 0, 0, 70),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    canvas.alpha_composite(shadow)

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)],
        radius=14, fill=(15, 15, 15),
    )

    # Apple logo
    apple_cx = badge_x + 38
    apple_cy = badge_y + badge_h // 2
    _draw_apple_logo(d, apple_cx, apple_cy, size=42, color=(255, 255, 255), bg=(15, 15, 15))

    # Text
    small_font = _load_font(18, weight="regular")
    big_font = _load_font(34, weight="xbold")
    text_x = apple_cx + 32
    d.text((text_x, badge_y + 14), "Download on the", font=small_font, fill=(255, 255, 255))
    d.text((text_x, badge_y + 36), "App Store", font=big_font, fill=(255, 255, 255))

    canvas.alpha_composite(layer)
    return badge_y + badge_h


CTA_CARD_PATH = os.path.normpath(
    os.path.join(_HERE, "..", "assets", "cta_card.png")
)


def _draw_final_cta(
    canvas: Image.Image,
    *,
    target_width: int = 720,
    top_y: int = 320,
) -> None:
    """Paste the user-provided CTA card image (cta_card.png) onto the slide,
    centered horizontally, at the given top_y. Falls back to programmatic
    drawing if the file is missing.
    """
    if not os.path.exists(CTA_CARD_PATH):
        # Fallback: programmatic card + badge
        card_bottom = _draw_app_card(
            canvas,
            app_name="Slidecast",
            app_subtitle="Recipe Keeper",
            tagline="Meal Planner & Grocery List",
            top_y=top_y,
        )
        _draw_app_store_badge(canvas, top_y=card_bottom + 28)
        return

    cta = Image.open(CTA_CARD_PATH).convert("RGBA")
    sw, sh = cta.size
    scale = target_width / sw
    new_w = int(sw * scale + 0.5)
    new_h = int(sh * scale + 0.5)
    cta = cta.resize((new_w, new_h), Image.LANCZOS)

    # Soft shadow under the asset for premium lift
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sx0 = (SLIDE_W - new_w) // 2
    sy0 = top_y + 8
    sd.rounded_rectangle(
        [(sx0, sy0), (sx0 + new_w, sy0 + new_h + 6)],
        radius=24, fill=(0, 0, 0, 70),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    canvas.alpha_composite(shadow)

    # Paste the CTA centered horizontally
    paste_x = (SLIDE_W - new_w) // 2
    canvas.alpha_composite(cta, dest=(paste_x, top_y))


def _draw_sauce_callouts(canvas: Image.Image, callouts: list[str]) -> None:
    """Place callout text labels around the center sauce bowl (no pills)."""
    if not callouts:
        return
    font = _load_font(40, weight="bold")
    cx = SLIDE_W // 2
    cy = SLIDE_H // 2 - 40
    radius_x = 360
    radius_y = 340

    n = len(callouts)
    for i, label in enumerate(callouts):
        # spread evenly around a circle, starting at top
        angle = -math.pi / 2 + (2 * math.pi * i / n)
        x = cx + int(math.cos(angle) * radius_x)
        y = cy + int(math.sin(angle) * radius_y)
        # clamp inside frame margins
        x = max(140, min(SLIDE_W - 140, x))
        y = max(140, min(SLIDE_H - 140, y))
        _draw_text_centered(canvas, (x, y), label, font, stroke_width=3)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def composite_slide(
    src_image_path: str,
    out_path: str,
    *,
    slide_type: str,
    caption: str,
    callouts: list[str] | None = None,
    recipe_title: str | None = None,
) -> str:
    src = Image.open(src_image_path).convert("RGB")
    canvas = _fit_image_cover(src).convert("RGBA")

    is_hook = slide_type == "hook"
    is_final = slide_type == "final"

    # --- Hook slide: use the recipe title as the caption (overrides whatever
    # caption was generated). The hook is the "name card" of the slideshow.
    if is_hook and recipe_title:
        caption = recipe_title

    # --- Final slide: override caption with one of the rotating CTA variants,
    # picked deterministically by hashing the recipe title.
    if is_final:
        variants = [
            "Don't lose recipes in screenshots\nsave them via slidecast app",
            "Save recipes from any social media\nwith one tap on slidecast",
            "Never lose a recipe again\ndownload slidecast app",
            "Stop screenshotting recipes\nuse slidecast to save them all",
            "Save any recipe in seconds\ndownload slidecast app",
        ]
        seed_str = recipe_title or "default"
        caption = variants[abs(hash(seed_str)) % len(variants)]

    # Position varies by slide type
    if is_hook:
        position = "center"
    elif is_final:
        # caption sits below the CTA card (which is at top), centered between
        # card bottom (~330) and slide bottom
        position = "below_cta"
    elif slide_type == "sauce":
        position = "bottom"
    else:
        position = "center"

    if slide_type == "sauce":
        _draw_sauce_callouts(canvas, callouts or [])

    # For the final slide: caption sits in upper-middle area, CTA just below
    # the slide center — both visually anchored to the center horizontal axis.
    if is_final:
        _draw_caption(
            canvas, caption,
            position=position, is_hook=is_hook, is_final=is_final,
        )
        # CTA image at 480px wide ≈ 189 tall, top_y=720 puts the bottom at ~y=909.
        _draw_final_cta(canvas, target_width=480, top_y=720)
    else:
        _draw_caption(
            canvas, caption,
            position=position, is_hook=is_hook, is_final=is_final,
        )

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.convert("RGB").save(out_path, "PNG", optimize=True)
    return out_path
