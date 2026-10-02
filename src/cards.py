"""
cards.py — Intro and outro card generators using Pillow.

Produces full-screen 1920×1080 PNG images for hooks/teasers, title screens,
and outro screens.  Every function is self-contained: pass in text, get back
a path to the saved PNG.  No ImageMagick or external assets required.
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import textwrap
from .config import VIDEO_WIDTH, VIDEO_HEIGHT


# ---------------------------------------------------------------------------
# Font helpers (shared with typography.py logic)
# ---------------------------------------------------------------------------

def _load_bold_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a bold system font with graceful fallback."""
    for name in ("arialbd.ttf", "segoeui.ttf", "calibrib.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _load_italic_font(size: int) -> ImageFont.FreeTypeFont:
    """Load an italic system font with graceful fallback."""
    for name in ("ariali.ttf", "segoeuii.ttf", "calibrii.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue
    return _load_bold_font(size)


def _draw_outlined_text(
    draw: ImageDraw.ImageDraw,
    position: tuple,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    outline_color: tuple = (0, 0, 0, 255),
    outline_width: int = 2,
    align: str = "left",
) -> None:
    """Draw text with a solid outline for readability."""
    x, y = position
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx == 0 and dy == 0:
                continue
            draw.multiline_text(
                (x + dx, y + dy), text, font=font,
                fill=outline_color, align=align,
            )
    draw.multiline_text(position, text, font=font, fill=fill, align=align)


def _draw_radial_gradient(img: Image.Image, center_color: tuple, edge_color: tuple) -> None:
    """
    Paint a radial gradient onto *img* (in-place).

    The gradient runs from *center_color* at the image centre to
    *edge_color* at the corners.  Both colours are (R, G, B) tuples.
    """
    w, h = img.size
    cx, cy = w // 2, h // 2
    max_dist = math.hypot(cx, cy)
    pixels = img.load()
    for y in range(h):
        for x in range(w):
            dist = math.hypot(x - cx, y - cy)
            t = min(dist / max_dist, 1.0)
            r = int(center_color[0] + (edge_color[0] - center_color[0]) * t)
            g = int(center_color[1] + (edge_color[1] - center_color[1]) * t)
            b = int(center_color[2] + (edge_color[2] - center_color[2]) * t)
            pixels[x, y] = (r, g, b, 255)


def _draw_vertical_gradient(draw: ImageDraw.ImageDraw, width: int, height: int,
                             top: tuple, bottom: tuple) -> None:
    """Fill the canvas with a smooth vertical gradient."""
    for y in range(height):
        t = y / height
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_hook_card(hook_text: str, output_path: str) -> str:
    """
    Generate a 1920×1080 hook / teaser image.

    Features a dark radial gradient background (centre slightly brighter)
    with centred italic text wrapped in decorative quotation marks and a
    "Did you know?" header.
    """
    img = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 255))

    # Radial gradient: slightly lighter centre
    _draw_radial_gradient(img, center_color=(40, 38, 50), edge_color=(12, 10, 18))

    draw = ImageDraw.Draw(img)

    # --- "Did you know?" header ---
    header_font = _load_bold_font(36)
    header = "Did you know?"
    hbox = draw.textbbox((0, 0), header, font=header_font)
    hw = hbox[2] - hbox[0]
    draw.text(
        ((VIDEO_WIDTH - hw) // 2, VIDEO_HEIGHT // 2 - 160),
        header, font=header_font,
        fill=(255, 200, 50, 255),  # gold
    )

    # --- Main hook text with quotation marks ---
    body_font = _load_italic_font(60)
    wrapped = textwrap.fill(hook_text, width=30)
    quoted = f'"{wrapped}"'

    bbox = draw.multiline_textbbox((0, 0), quoted, font=body_font, align="center")
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (VIDEO_WIDTH - tw) // 2
    ty = (VIDEO_HEIGHT - th) // 2 - 30

    _draw_outlined_text(
        draw, (tx, ty), quoted, body_font,
        fill=(255, 255, 255, 200),
        outline_color=(0, 0, 0, 180),
        outline_width=2,
        align="center",
    )

    img.save(output_path, format="PNG")
    return output_path


def create_title_card(title: str, output_path: str) -> str:
    """
    Generate a 1920×1080 title card.

    Rich dark gradient (deep blue-black → purple-black), large bold centred
    title with a soft glow behind it, and a thin gold decorative line below.
    """
    img = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # Gradient background
    _draw_vertical_gradient(
        draw, VIDEO_WIDTH, VIDEO_HEIGHT,
        top=(8, 8, 30),      # deep blue-black
        bottom=(25, 10, 35), # purple-black
    )

    font = _load_bold_font(90)
    wrapped = textwrap.fill(title, width=20)

    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center")
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (VIDEO_WIDTH - tw) // 2
    ty = (VIDEO_HEIGHT - th) // 2 - 40

    # --- Glow effect: draw blurred larger text behind the sharp text ---
    glow_layer = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    glow_font = _load_bold_font(96)  # slightly larger for the glow
    glow_bbox = glow_draw.multiline_textbbox((0, 0), wrapped, font=glow_font, align="center")
    gtw, gth = glow_bbox[2] - glow_bbox[0], glow_bbox[3] - glow_bbox[1]
    gx = (VIDEO_WIDTH - gtw) // 2
    gy = (VIDEO_HEIGHT - gth) // 2 - 40
    glow_draw.multiline_text(
        (gx, gy), wrapped, font=glow_font,
        fill=(255, 255, 255, 60), align="center",
    )
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=18))
    img = Image.alpha_composite(img, glow_layer)

    # Re-create draw on the composited image
    draw = ImageDraw.Draw(img)

    # Sharp title text on top
    _draw_outlined_text(
        draw, (tx, ty), wrapped, font,
        fill=(255, 255, 255, 255),
        outline_color=(0, 0, 0, 200),
        outline_width=3,
        align="center",
    )

    # --- Gold decorative line below the title ---
    line_y = ty + th + 35
    line_half = 120
    cx = VIDEO_WIDTH // 2
    gold = (255, 200, 50, 255)
    draw.rectangle([cx - line_half, line_y, cx + line_half, line_y + 2], fill=gold)

    img.save(output_path, format="PNG")
    return output_path


def create_outro_card(channel_name: str, output_path: str) -> str:
    """
    Generate a 1920×1080 outro card.

    Dark background with "Thanks for Watching!" headline, the channel name,
    and a "Like & Subscribe" call-to-action encircled by a hand-drawn ring.
    Gold accent colours throughout.
    """
    img = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # Subtle gradient background
    _draw_vertical_gradient(
        draw, VIDEO_WIDTH, VIDEO_HEIGHT,
        top=(15, 12, 22),
        bottom=(22, 18, 30),
    )

    gold = (255, 200, 50, 255)
    white = (255, 255, 255, 255)

    # --- "Thanks for Watching!" ---
    thanks_font = _load_bold_font(70)
    thanks = "Thanks for Watching!"
    tbox = draw.textbbox((0, 0), thanks, font=thanks_font)
    tw = tbox[2] - tbox[0]
    tx = (VIDEO_WIDTH - tw) // 2
    ty = VIDEO_HEIGHT // 2 - 160
    _draw_outlined_text(draw, (tx, ty), thanks, thanks_font,
                        fill=white, outline_width=2)

    # --- Thin gold separator ---
    sep_y = ty + (tbox[3] - tbox[1]) + 20
    cx = VIDEO_WIDTH // 2
    draw.rectangle([cx - 80, sep_y, cx + 80, sep_y + 2], fill=gold)

    # --- Channel name ---
    ch_font = _load_bold_font(40)
    cbox = draw.textbbox((0, 0), channel_name, font=ch_font)
    cw = cbox[2] - cbox[0]
    ch = cbox[3] - cbox[1]
    ch_x = (VIDEO_WIDTH - cw) // 2
    ch_y = sep_y + 30
    draw.text((ch_x, ch_y), channel_name, font=ch_font, fill=gold)

    # --- "Like & Subscribe" with hand-drawn circle ---
    sub_font = _load_bold_font(34)
    sub_text = "Like & Subscribe"
    sbox = draw.textbbox((0, 0), sub_text, font=sub_font)
    sw, sh = sbox[2] - sbox[0], sbox[3] - sbox[1]
    sx = (VIDEO_WIDTH - sw) // 2
    sy = ch_y + ch + 60
    draw.text((sx, sy), sub_text, font=sub_font, fill=white)

    # Draw an imperfect (hand-drawn look) ellipse around the CTA
    pad_x, pad_y = 30, 18
    ecx = sx + sw // 2
    ecy = sy + sh // 2
    for angle_offset in range(360):
        # Slight radius wobble for a hand-drawn feel
        wobble = 2.5 * math.sin(angle_offset * 0.15)
        rx = sw // 2 + pad_x + wobble
        ry = sh // 2 + pad_y + wobble * 0.7
        rad = math.radians(angle_offset)
        px = ecx + rx * math.cos(rad)
        py = ecy + ry * math.sin(rad)
        # Draw small dot at each position
        draw.ellipse([px - 1, py - 1, px + 1, py + 1], fill=gold)

    img.save(output_path, format="PNG")
    return output_path


# ---------------------------------------------------------------------------
# Quick CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.makedirs("_test_output", exist_ok=True)
    create_hook_card("Honey never spoils — archaeologists have found 3000-year-old honey.", "_test_output/hook.png")
    create_title_card("Top 10 Mind-Blowing Facts", "_test_output/title.png")
    create_outro_card("FactsUnlocked", "_test_output/outro.png")
    print("All card test images saved to _test_output/")
