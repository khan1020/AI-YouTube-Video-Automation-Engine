"""
overlays.py — Overlay graphics generators using Pillow.

Produces transparent 1920×1080 PNG images that are composited on top of
video frames: progress bars, chapter indicators, and other HUD elements.
No ImageMagick or external assets required.
"""

import os
from PIL import Image, ImageDraw, ImageFont
from .config import VIDEO_WIDTH, VIDEO_HEIGHT


# ---------------------------------------------------------------------------
# Font helper
# ---------------------------------------------------------------------------

def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a clean UI font with graceful fallback."""
    for name in ("arialbd.ttf", "segoeui.ttf", "calibrib.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Rounded-rectangle helper (Pillow < 10.x compat)
# ---------------------------------------------------------------------------

def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple,
    radius: int,
    fill: tuple,
) -> None:
    """
    Draw a rounded rectangle.  Uses Pillow's built-in rounded_rectangle
    when available (Pillow ≥ 9.0), otherwise approximates with rects + arcs.
    """
    x0, y0, x1, y1 = xy
    if hasattr(draw, "rounded_rectangle"):
        draw.rounded_rectangle(xy, radius=radius, fill=fill)
    else:
        # Fallback: two overlapping rectangles + four corner circles
        draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
        draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
        draw.pieslice([x0, y0, x0 + 2 * radius, y0 + 2 * radius],
                      180, 270, fill=fill)
        draw.pieslice([x1 - 2 * radius, y0, x1, y0 + 2 * radius],
                      270, 360, fill=fill)
        draw.pieslice([x0, y1 - 2 * radius, x0 + 2 * radius, y1],
                      90, 180, fill=fill)
        draw.pieslice([x1 - 2 * radius, y1 - 2 * radius, x1, y1],
                      0, 90, fill=fill)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_progress_bar_frame(progress_pct: float, output_path: str) -> str:
    """
    Create a transparent 1920×1080 PNG with a thin progress bar at the bottom.

    Parameters
    ----------
    progress_pct : float
        Progress as a fraction in [0.0, 1.0].
    output_path : str
        Destination file path for the PNG.

    Returns
    -------
    str
        The *output_path* for easy chaining.

    The bar sits at y = 1076 (4 px tall, hugging the very bottom edge).
    The filled portion uses a horizontal gradient from gold to warm orange.
    """
    progress_pct = max(0.0, min(1.0, progress_pct))  # clamp

    img = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    bar_y = 1076
    bar_h = 4

    # Background track — full width, dark gray, semi-transparent
    draw.rectangle(
        [0, bar_y, VIDEO_WIDTH, bar_y + bar_h],
        fill=(50, 50, 50, 150),
    )

    # Filled portion — gradient from gold to warm orange
    filled_width = int(progress_pct * VIDEO_WIDTH)
    if filled_width > 0:
        for x in range(filled_width):
            t = x / max(filled_width - 1, 1)
            # Gold (255, 200, 50) → Warm orange (255, 150, 50)
            r = 255
            g = int(200 + (150 - 200) * t)  # 200 → 150
            b = 50
            draw.line([(x, bar_y), (x, bar_y + bar_h)], fill=(r, g, b, 255))

    img.save(output_path, format="PNG")
    return output_path


def create_chapter_indicator(
    chapter_num: int, total_chapters: int, output_path: str
) -> str:
    """
    Create a small "Part X/Y" badge in the top-right corner.

    The badge is a rounded semi-transparent dark rectangle at
    approximately (1720, 30) with white text.

    Parameters
    ----------
    chapter_num : int
        Current chapter number (1-based).
    total_chapters : int
        Total number of chapters.
    output_path : str
        Destination file path for the PNG.
    """
    img = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Badge geometry
    badge_x, badge_y = 1720, 30
    badge_w, badge_h = 160, 40
    corner_r = 10

    # Rounded-rectangle background
    _draw_rounded_rect(
        draw,
        (badge_x, badge_y, badge_x + badge_w, badge_y + badge_h),
        radius=corner_r,
        fill=(20, 20, 20, 180),
    )

    # "Part X/Y" label
    font = _load_font(22)
    label = f"Part {chapter_num}/{total_chapters}"
    bbox = draw.textbbox((0, 0), label, font=font)
    lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Centre the text inside the badge
    lx = badge_x + (badge_w - lw) // 2
    ly = badge_y + (badge_h - lh) // 2
    draw.text((lx, ly), label, font=font, fill=(255, 255, 255, 240))

    img.save(output_path, format="PNG")
    return output_path


# ---------------------------------------------------------------------------
# Quick CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.makedirs("_test_output", exist_ok=True)
    create_progress_bar_frame(0.0, "_test_output/progress_0.png")
    create_progress_bar_frame(0.45, "_test_output/progress_45.png")
    create_progress_bar_frame(1.0, "_test_output/progress_100.png")
    create_chapter_indicator(3, 10, "_test_output/chapter_badge.png")
    print("All overlay test images saved to _test_output/")
