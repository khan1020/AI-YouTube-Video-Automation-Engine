"""
typography.py — Professional text overlay generators using Pillow.

Generates lower-third graphics, chapter transition cards, and watermarks
as transparent PNG images sized to the project's video resolution.
All rendering is done via Pillow (no ImageMagick required).
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import textwrap
from .config import VIDEO_WIDTH, VIDEO_HEIGHT


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

def _load_bold_font(size: int) -> ImageFont.FreeTypeFont:
    """
    Attempt to load a bold system font, falling back through several
    common Windows fonts before using the Pillow default bitmap font.
    """
    candidates = ["arialbd.ttf", "segoeui.ttf", "calibrib.ttf"]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue
    # Last resort — the built-in bitmap font (no size parameter)
    return ImageFont.load_default()


def _load_italic_font(size: int) -> ImageFont.FreeTypeFont:
    """Load an italic system font with graceful fallback."""
    candidates = ["ariali.ttf", "segoeuii.ttf", "calibrii.ttf"]
    for name in candidates:
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
    """
    Draw text with a solid outline for readability against any background.
    The outline is rendered by stamping the text at small offsets around
    the target position before drawing the main fill on top.
    """
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_subtitle_image(text: str, output_path: str) -> str:
    """
    Render a subtitle string onto a transparent 1920×1080 PNG.

    Uses a large handwriting-style font with a thick black outline so the
    text remains readable over any video footage.
    """
    img = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Try handwriting / display fonts first
    font = None
    for name in ("inkfree.ttf", "segoeprb.ttf", "comicbd.ttf"):
        try:
            font = ImageFont.truetype(name, 150)
            break
        except (IOError, OSError):
            continue
    if font is None:
        font = ImageFont.load_default()

    wrapped = textwrap.fill(text, width=15)

    # Centre the block horizontally; place it in the lower third of the frame
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center")
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (VIDEO_WIDTH - tw) / 2
    y = (VIDEO_HEIGHT / 2) + 200

    _draw_outlined_text(
        draw, (x, y), wrapped, font,
        fill=(255, 255, 255, 255),
        outline_width=4,
        align="center",
    )

    img.save(output_path, format="PNG")
    return output_path


def create_lower_third(text: str, output_path: str) -> str:
    """
    Create a professional lower-third name-strap graphic.

    Layout (on a transparent 1920×1080 canvas):
    ┌──────────────────────────────────────────────┐
    │                                              │
    │                                              │
    │  ▌██████████████████████████████████████     │  ← y=830, h=100
    │  ▌  Bold White Text                         │
    │  ▌██████████████████████████████████████     │
    │                                              │
    └──────────────────────────────────────────────┘
    Gold accent stripe (4 px) │ Dark semi-transparent bar
    """
    img = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # --- Bar dimensions ---
    bar_x, bar_y = 60, 830
    bar_w, bar_h = 640, 100  # bar runs from x=60 to x=700

    # Semi-transparent dark bar
    draw.rectangle(
        [bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
        fill=(20, 20, 20, 200),
    )

    # Gold accent stripe on the left edge
    stripe_x = 56
    stripe_w = 4
    draw.rectangle(
        [stripe_x, bar_y, stripe_x + stripe_w, bar_y + bar_h],
        fill=(255, 200, 50, 255),
    )

    # --- Text ---
    font = _load_bold_font(42)

    # Vertically centre the text inside the bar
    bbox = draw.textbbox((0, 0), text, font=font)
    text_h = bbox[3] - bbox[1]
    text_x = 80
    text_y = bar_y + (bar_h - text_h) // 2

    # Black outline for readability (2 px)
    _draw_outlined_text(
        draw, (text_x, text_y), text, font,
        fill=(255, 255, 255, 255),
        outline_color=(0, 0, 0, 255),
        outline_width=2,
    )

    img.save(output_path, format="PNG")
    return output_path


def create_chapter_card(text: str, output_path: str) -> str:
    """
    Create a full-screen chapter transition card.

    Features a vertical dark gradient background, large centred text with a
    warm gold tint, and thin decorative gold lines above and below the text
    terminated by small dots.
    """
    img = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # --- Vertical gradient background ---
    top_color = (15, 15, 25)
    bot_color = (25, 20, 35)
    for y in range(VIDEO_HEIGHT):
        t = y / VIDEO_HEIGHT
        r = int(top_color[0] + (bot_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bot_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bot_color[2] - top_color[2]) * t)
        draw.line([(0, y), (VIDEO_WIDTH, y)], fill=(r, g, b, 255))

    # --- Centred text ---
    font = _load_bold_font(80)
    wrapped = textwrap.fill(text, width=25)
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center")
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    text_x = (VIDEO_WIDTH - tw) // 2
    text_y = (VIDEO_HEIGHT - th) // 2

    gold_tint = (255, 245, 230, 255)
    _draw_outlined_text(
        draw, (text_x, text_y), wrapped, font,
        fill=gold_tint,
        outline_color=(0, 0, 0, 255),
        outline_width=2,
        align="center",
    )

    # --- Decorative lines (gold, ~200 px wide, centred) ---
    line_color = (255, 200, 50, 255)
    line_half = 100  # half-length of each line
    cx = VIDEO_WIDTH // 2
    line_thickness = 2
    dot_radius = 4

    # Line above the text
    line_above_y = text_y - 30
    draw.rectangle(
        [cx - line_half, line_above_y, cx + line_half, line_above_y + line_thickness],
        fill=line_color,
    )
    # Dots at the ends
    draw.ellipse(
        [cx - line_half - dot_radius, line_above_y - dot_radius + 1,
         cx - line_half + dot_radius, line_above_y + dot_radius + 1],
        fill=line_color,
    )
    draw.ellipse(
        [cx + line_half - dot_radius, line_above_y - dot_radius + 1,
         cx + line_half + dot_radius, line_above_y + dot_radius + 1],
        fill=line_color,
    )

    # Line below the text
    line_below_y = text_y + th + 30
    draw.rectangle(
        [cx - line_half, line_below_y, cx + line_half, line_below_y + line_thickness],
        fill=line_color,
    )
    draw.ellipse(
        [cx - line_half - dot_radius, line_below_y - dot_radius + 1,
         cx - line_half + dot_radius, line_below_y + dot_radius + 1],
        fill=line_color,
    )
    draw.ellipse(
        [cx + line_half - dot_radius, line_below_y - dot_radius + 1,
         cx + line_half + dot_radius, line_below_y + dot_radius + 1],
        fill=line_color,
    )

    img.save(output_path, format="PNG")
    return output_path


def create_watermark(text: str, output_path: str) -> str:
    """
    Create a barely-visible watermark in the bottom-right corner.

    The text is rendered at very low opacity so it does not distract
    from the video content but is still present for branding.
    """
    img = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font = _load_bold_font(24)
    watermark_color = (255, 255, 255, 80)  # very subtle

    draw.text((1700, 1040), text, font=font, fill=watermark_color)

    img.save(output_path, format="PNG")
    return output_path


# ---------------------------------------------------------------------------
# Quick CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.makedirs("_test_output", exist_ok=True)
    create_subtitle_image("Test subtitle!", "_test_output/subtitle.png")
    create_lower_third("John Doe — Producer", "_test_output/lower_third.png")
    create_chapter_card("Chapter 1: Introduction", "_test_output/chapter_card.png")
    create_watermark("© MyChannel", "_test_output/watermark.png")
    print("All typography test images saved to _test_output/")
