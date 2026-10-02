"""
effects.py — Reusable video effects library for the YouTube automation pipeline.

Each effect is a pure function: takes a MoviePy clip, returns a modified clip.
All per-frame effects use numpy arrays via fl_image() or fl().
No external assets required — everything is generated procedurally.
"""

import numpy as np
import math
import random
from PIL import Image
from scipy.ndimage import gaussian_filter

from moviepy.editor import (
    CompositeVideoClip,
    ColorClip,
    concatenate_videoclips,
)
from .config import VIDEO_WIDTH, VIDEO_HEIGHT


# ---------------------------------------------------------------------------
# 1. Ken Burns Zoom
# ---------------------------------------------------------------------------
def ken_burns_zoom(clip, zoom_ratio=0.04):
    """
    Slowly zoom into the clip over its duration for a cinematic Ken Burns look.

    Uses PIL for smooth per-frame resizing. The zoom increases linearly from
    1.0 to (1.0 + zoom_ratio) over the clip's duration.

    Args:
        clip: A MoviePy VideoClip.
        zoom_ratio: Maximum additional zoom (0.04 = 4% zoom by end).

    Returns:
        A new VideoClip with the zoom effect applied.
    """
    w, h = clip.size

    def effect(get_frame, t):
        """Crop a progressively zoomed region from the frame."""
        # Linear zoom: 1.0 at t=0, (1+zoom_ratio) at t=duration
        progress = t / max(clip.duration, 0.001)
        zoom = 1.0 + zoom_ratio * progress

        frame = get_frame(t)

        # Use PIL for high-quality resizing
        img = Image.fromarray(frame)
        # Scale up, then crop the center back to original size
        new_w, new_h = int(w * zoom), int(h * zoom)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        # Crop center region to original dimensions
        left = (new_w - w) // 2
        top = (new_h - h) // 2
        img = img.crop((left, top, left + w, top + h))

        return np.array(img)

    return clip.fl(effect)


# ---------------------------------------------------------------------------
# 2. Cinematic Color Grade
# ---------------------------------------------------------------------------
def cinematic_color_grade(image):
    """
    Per-frame color grading: teal shadows + warm orange highlights.

    Shadows (pixel mean < 128): reduce red by 0.85, boost blue by 1.15.
    Highlights (pixel mean >= 128): boost red by 1.15, reduce blue by 0.85.

    Apply via: clip.fl_image(cinematic_color_grade)

    Args:
        image: numpy array (H, W, 3) uint8.

    Returns:
        Color-graded numpy array (H, W, 3) uint8.
    """
    frame = image.astype(np.float32)

    # Calculate per-pixel luminance (mean of RGB channels)
    pixel_mean = np.mean(frame, axis=2)

    # Create shadow and highlight masks
    shadow_mask = pixel_mean < 128  # shape: (H, W)
    highlight_mask = ~shadow_mask

    # --- Shadows: teal push (less red, more blue) ---
    frame[shadow_mask, 0] *= 0.85   # Red channel down
    frame[shadow_mask, 2] *= 1.15   # Blue channel up

    # --- Highlights: warm orange push (more red, less blue) ---
    frame[highlight_mask, 0] *= 1.15  # Red channel up
    frame[highlight_mask, 2] *= 0.85  # Blue channel down

    return np.clip(frame, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# 3. Vignette
# ---------------------------------------------------------------------------
def add_vignette(image, intensity=0.5):
    """
    Per-frame vignette: radial darkening from center outward.

    Uses np.ogrid to compute normalised distance from center, then applies
    a smooth falloff to darken edges.

    Apply via: clip.fl_image(lambda img: add_vignette(img, intensity=0.5))

    Args:
        image: numpy array (H, W, 3) uint8.
        intensity: Strength of darkening (0=none, 1=very strong).

    Returns:
        Vignetted numpy array (H, W, 3) uint8.
    """
    h, w = image.shape[:2]

    # Create distance grid from center using ogrid (memory efficient)
    y, x = np.ogrid[:h, :w]
    cx, cy = w / 2.0, h / 2.0

    # Normalised distance from center (0 at center, ~1 at corners)
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    max_dist = np.sqrt(cx ** 2 + cy ** 2)
    dist_norm = dist / max_dist

    # Smooth vignette mask: 1 at center, fading to (1 - intensity) at edges
    vignette_mask = 1.0 - intensity * (dist_norm ** 2)
    vignette_mask = np.clip(vignette_mask, 0, 1)

    # Apply to all channels
    result = image.astype(np.float32) * vignette_mask[:, :, np.newaxis]
    return np.clip(result, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# 4. Film Grain
# ---------------------------------------------------------------------------
def add_film_grain(image, intensity=15):
    """
    Per-frame film grain: adds random gaussian noise for filmic texture.

    Apply via: clip.fl_image(lambda img: add_film_grain(img, intensity=15))

    Args:
        image: numpy array (H, W, 3) uint8.
        intensity: Standard deviation of the gaussian noise.

    Returns:
        Grainy numpy array (H, W, 3) uint8.
    """
    noise = np.random.normal(0, intensity, image.shape).astype(np.float32)
    result = image.astype(np.float32) + noise
    return np.clip(result, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# 5. Letterbox
# ---------------------------------------------------------------------------
def add_letterbox(clip, bar_height=60):
    """
    Add cinematic letterbox bars (2.35:1 aspect ratio look).

    Composites black ColorClip bars at the top and bottom of the frame.

    Args:
        clip: A MoviePy VideoClip.
        bar_height: Height of each black bar in pixels.

    Returns:
        A CompositeVideoClip with letterbox bars overlaid.
    """
    w, h = clip.size

    # Create black bars
    top_bar = (
        ColorClip(size=(w, bar_height), color=(0, 0, 0))
        .set_duration(clip.duration)
        .set_position(("center", "top"))
    )
    bottom_bar = (
        ColorClip(size=(w, bar_height), color=(0, 0, 0))
        .set_duration(clip.duration)
        .set_position(("center", "bottom"))
    )

    return CompositeVideoClip([clip, top_bar, bottom_bar], size=(w, h))


# ---------------------------------------------------------------------------
# 6. Light Leak
# ---------------------------------------------------------------------------
def generate_light_leak(clip):
    """
    Create a warm golden light-leak flare that drifts across the frame.

    Generates a gaussian blob of warm light using numpy, then composites it
    as a screen-blend overlay that slowly moves across the frame.

    Args:
        clip: A MoviePy VideoClip.

    Returns:
        A CompositeVideoClip with the light leak composited on top.
    """
    w, h = clip.size
    duration = clip.duration

    # Pre-compute a gaussian warm-light blob
    blob_size = int(min(w, h) * 0.6)
    y, x = np.ogrid[:blob_size, :blob_size]
    cx, cy = blob_size / 2.0, blob_size / 2.0
    sigma = blob_size / 4.0
    gaussian = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma ** 2))

    # Warm golden color: (255, 200, 80) with alpha from gaussian
    blob_rgb = np.zeros((blob_size, blob_size, 3), dtype=np.float32)
    blob_rgb[:, :, 0] = 255 * gaussian  # Red
    blob_rgb[:, :, 1] = 200 * gaussian  # Green
    blob_rgb[:, :, 2] = 80 * gaussian   # Blue

    def make_light_leak_frame(get_frame, t):
        """Screen-blend the drifting light blob onto the current frame."""
        frame = get_frame(t).astype(np.float32)
        progress = t / max(duration, 0.001)

        # Blob drifts from left-center to right-center
        bx = int((w - blob_size) * progress)
        by = int((h - blob_size) * 0.3 + (h - blob_size) * 0.4 * math.sin(progress * math.pi))

        # Clamp to frame bounds
        bx = max(0, min(bx, w - blob_size))
        by = max(0, min(by, h - blob_size))

        # Screen blend: result = 1 - (1 - base) * (1 - overlay)
        region = frame[by:by + blob_size, bx:bx + blob_size]
        blended = 255.0 - (255.0 - region) * (255.0 - blob_rgb * 0.4) / 255.0
        frame[by:by + blob_size, bx:bx + blob_size] = blended

        return np.clip(frame, 0, 255).astype(np.uint8)

    return clip.fl(make_light_leak_frame)


# ---------------------------------------------------------------------------
# 7. Zoom Punch
# ---------------------------------------------------------------------------
def zoom_punch(clip, peak_zoom=1.15, duration=0.4):
    """
    Quick dramatic zoom-in then settle back to normal scale.

    The clip zooms from 1.0 to peak_zoom and back over the specified duration.
    Uses a sine curve for smooth easing.

    Args:
        clip: A MoviePy VideoClip.
        peak_zoom: Maximum zoom factor at the peak.
        duration: How long the zoom punch lasts (seconds).

    Returns:
        A CompositeVideoClip with the zoom-punch effect.
    """
    w, h = clip.size

    def zoom_func(t):
        """Calculate zoom factor at time t."""
        if t > duration:
            return 1.0
        # Sine curve: ramps up to peak then back down
        progress = t / duration
        return 1.0 + (peak_zoom - 1.0) * math.sin(progress * math.pi)

    zoomed = clip.resize(zoom_func)

    return CompositeVideoClip(
        [zoomed.set_position("center")],
        size=(w, h),
    )


# ---------------------------------------------------------------------------
# 8. Screen Shake
# ---------------------------------------------------------------------------
def screen_shake(clip, intensity=5, duration=0.5):
    """
    Subtle random camera-shake effect for the first `duration` seconds.

    Uses deterministic random offsets seeded by time so the shake is
    consistent across renders.

    Args:
        clip: A MoviePy VideoClip.
        intensity: Max pixel offset in each direction.
        duration: How long the shake lasts (seconds).

    Returns:
        A CompositeVideoClip with the shake applied.
    """
    w, h = clip.size

    def shake_position(t):
        """Return (x, y) offset — random jitter during shake, centered after."""
        if t > duration:
            return ("center", "center")
        # Seed by quantised time so offset changes each frame
        rng = random.Random(int(t * 1000))
        dx = rng.randint(-intensity, intensity)
        dy = rng.randint(-intensity, intensity)
        return (w // 2 - clip.w // 2 + dx, h // 2 - clip.h // 2 + dy)

    shaken = clip.set_position(shake_position)

    return CompositeVideoClip([shaken], size=(w, h))


# ---------------------------------------------------------------------------
# 9. Glitch Effect
# ---------------------------------------------------------------------------
def glitch_effect(clip, duration=0.3):
    """
    RGB channel split + horizontal offset for a digital glitch look.

    During the glitch window, the red channel is shifted left and the blue
    channel is shifted right by a few pixels using numpy roll.

    Args:
        clip: A MoviePy VideoClip.
        duration: How long the glitch lasts (from t=0).

    Returns:
        A new VideoClip with the glitch effect.
    """
    def apply_glitch(get_frame, t):
        """Shift RGB channels horizontally during the glitch window."""
        frame = get_frame(t).copy()

        if t > duration:
            return frame

        # Offset varies slightly with time for a jittery look
        offset = int(8 + 12 * math.sin(t * 60))

        # Shift red channel left, blue channel right
        frame[:, :, 0] = np.roll(frame[:, :, 0], -offset, axis=1)  # Red left
        frame[:, :, 2] = np.roll(frame[:, :, 2], offset, axis=1)   # Blue right

        return frame

    return clip.fl(apply_glitch)


# ---------------------------------------------------------------------------
# 10. Speed Ramp
# ---------------------------------------------------------------------------
def speed_ramp(clip, slow_factor=0.5, slow_start=0.3, slow_duration=1.0):
    """
    Apply slow motion to a portion of the clip.

    Splits the clip into three parts: before the ramp, the slow section,
    and after the ramp. The slow section is played at slow_factor speed.

    Args:
        clip: A MoviePy VideoClip.
        slow_factor: Speed multiplier for the slow section (0.5 = half speed).
        slow_start: When the slow section begins (seconds from start).
        slow_duration: Duration of the slow section at original speed (seconds).

    Returns:
        A concatenated VideoClip with the speed ramp applied.
    """
    total = clip.duration

    # Clamp values to clip bounds
    slow_start = min(slow_start, total)
    slow_end = min(slow_start + slow_duration, total)

    parts = []

    # Part 1: before the slow section (normal speed)
    if slow_start > 0:
        parts.append(clip.subclip(0, slow_start))

    # Part 2: the slow section
    if slow_end > slow_start:
        slow_part = clip.subclip(slow_start, slow_end).speedx(slow_factor)
        parts.append(slow_part)

    # Part 3: after the slow section (normal speed)
    if slow_end < total:
        parts.append(clip.subclip(slow_end, total))

    if not parts:
        return clip

    return concatenate_videoclips(parts, method="compose")


# ---------------------------------------------------------------------------
# 11. Blur to Sharp
# ---------------------------------------------------------------------------
def blur_to_sharp(clip, blur_duration=0.5):
    """
    Clip starts blurry and progressively sharpens.

    Uses scipy gaussian_filter with a sigma that decreases linearly from a
    high value to 0 over blur_duration seconds.

    Args:
        clip: A MoviePy VideoClip.
        blur_duration: How long it takes to go from fully blurry to sharp.

    Returns:
        A new VideoClip with the blur-to-sharp effect.
    """
    max_sigma = 10.0  # Starting blur strength

    def apply_blur(get_frame, t):
        """Apply decreasing gaussian blur based on time."""
        frame = get_frame(t)

        if t >= blur_duration:
            return frame

        # Sigma decreases linearly: max_sigma at t=0, 0 at t=blur_duration
        progress = t / blur_duration
        sigma = max_sigma * (1.0 - progress)

        if sigma < 0.5:
            return frame

        # Apply gaussian blur to each channel
        blurred = gaussian_filter(frame.astype(np.float32), sigma=[sigma, sigma, 0])
        return np.clip(blurred, 0, 255).astype(np.uint8)

    return clip.fl(apply_blur)
