"""
transitions.py — Scene transition library for the YouTube automation pipeline.

Each transition function takes two clips (clip_out, clip_in) and a duration,
returning a single VideoClip that shows the transition between scenes.
Clips are resized to match when sizes differ.
"""

import random
import math
import numpy as np
from scipy.ndimage import gaussian_filter

from moviepy.editor import (
    CompositeVideoClip,
    ColorClip,
    concatenate_videoclips,
)
from .config import VIDEO_WIDTH, VIDEO_HEIGHT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _match_sizes(clip1, clip2):
    """
    Ensure clip2 matches clip1's dimensions.

    If sizes differ, clip2 is resized to clip1's size so compositing
    works correctly.

    Returns:
        (clip1, clip2) with matched sizes.
    """
    if clip1.size != clip2.size:
        clip2 = clip2.resize(clip1.size)
    return clip1, clip2


# ---------------------------------------------------------------------------
# 1. Crossfade
# ---------------------------------------------------------------------------
def crossfade_transition(clip1, clip2, duration=0.5):
    """
    Standard opacity dissolve between two clips.

    The end of clip1 fades out while the beginning of clip2 fades in,
    overlapping for `duration` seconds.

    Args:
        clip1: Outgoing clip.
        clip2: Incoming clip.
        duration: Length of the crossfade overlap in seconds.

    Returns:
        A single VideoClip with the crossfade applied.
    """
    clip1, clip2 = _match_sizes(clip1, clip2)

    # clip1 plays fully, with a fade-out at the end
    clip1_faded = clip1.crossfadeout(duration)

    # clip2 starts at (clip1.duration - duration), with a fade-in
    clip2_faded = (
        clip2
        .crossfadein(duration)
        .set_start(clip1.duration - duration)
    )

    return CompositeVideoClip(
        [clip1_faded, clip2_faded],
        size=clip1.size,
    ).set_duration(clip1.duration + clip2.duration - duration)


# ---------------------------------------------------------------------------
# 2. Slide Left
# ---------------------------------------------------------------------------
def slide_left_transition(clip1, clip2, duration=0.5):
    """
    clip2 slides in from the right, pushing clip1 out to the left.

    Both clips move simultaneously during the overlap window.

    Args:
        clip1: Outgoing clip.
        clip2: Incoming clip.
        duration: Length of the slide transition in seconds.

    Returns:
        A single VideoClip with the slide-left transition.
    """
    clip1, clip2 = _match_sizes(clip1, clip2)
    w, h = clip1.size

    transition_start = clip1.duration - duration

    def clip1_position(t):
        """clip1 slides from center to off-screen left."""
        if t < transition_start:
            return ("center", "center")
        progress = (t - transition_start) / duration
        x = int(-w * progress)
        return (x, 0)

    def clip2_position(t):
        """clip2 slides from off-screen right to center."""
        local_t = t - transition_start
        if local_t < 0:
            return (w, 0)  # Off-screen right
        progress = min(local_t / duration, 1.0)
        x = int(w * (1.0 - progress))
        return (x, 0)

    clip1_moving = clip1.set_position(clip1_position)
    clip2_moving = (
        clip2
        .set_position(clip2_position)
        .set_start(transition_start)
    )

    total_duration = clip1.duration + clip2.duration - duration

    return CompositeVideoClip(
        [clip1_moving, clip2_moving],
        size=(w, h),
    ).set_duration(total_duration)


# ---------------------------------------------------------------------------
# 3. Slide Up
# ---------------------------------------------------------------------------
def slide_up_transition(clip1, clip2, duration=0.5):
    """
    clip2 slides up from the bottom, covering clip1.

    Args:
        clip1: Outgoing clip.
        clip2: Incoming clip.
        duration: Length of the slide-up transition in seconds.

    Returns:
        A single VideoClip with the slide-up transition.
    """
    clip1, clip2 = _match_sizes(clip1, clip2)
    w, h = clip1.size

    transition_start = clip1.duration - duration

    def clip2_position(t):
        """clip2 rises from below the frame to center."""
        local_t = t - transition_start
        if local_t < 0:
            return (0, h)  # Off-screen below
        progress = min(local_t / duration, 1.0)
        y = int(h * (1.0 - progress))
        return (0, y)

    clip2_moving = (
        clip2
        .set_position(clip2_position)
        .set_start(transition_start)
    )

    total_duration = clip1.duration + clip2.duration - duration

    return CompositeVideoClip(
        [clip1, clip2_moving],
        size=(w, h),
    ).set_duration(total_duration)


# ---------------------------------------------------------------------------
# 4. Zoom Transition
# ---------------------------------------------------------------------------
def zoom_transition(clip1, clip2, duration=0.5):
    """
    clip2 zooms in from a tiny scale (0.1) to full size over clip1.

    Creates a dramatic "pop-in" reveal effect.

    Args:
        clip1: Outgoing clip (background).
        clip2: Incoming clip (zooms in on top).
        duration: Length of the zoom transition in seconds.

    Returns:
        A single VideoClip with the zoom transition.
    """
    clip1, clip2 = _match_sizes(clip1, clip2)
    w, h = clip1.size

    transition_start = clip1.duration - duration

    # Extract only the transition portion of clip2 for the zoom effect
    clip2_intro = clip2.subclip(0, duration)

    def zoom_factor(t):
        """Scale from 0.1 to 1.0 with ease-out."""
        progress = min(t / duration, 1.0)
        # Ease-out: decelerate into final size
        eased = 1.0 - (1.0 - progress) ** 2
        return 0.1 + 0.9 * eased

    clip2_zooming = (
        clip2_intro
        .resize(zoom_factor)
        .set_position("center")
        .set_start(transition_start)
    )

    # After the zoom, clip2 continues at full size
    clip2_rest = (
        clip2
        .subclip(duration)
        .set_start(clip1.duration)
    ) if clip2.duration > duration else None

    layers = [clip1, clip2_zooming]
    total_duration = clip1.duration + clip2.duration - duration

    if clip2_rest is not None:
        layers.append(clip2_rest)

    return CompositeVideoClip(layers, size=(w, h)).set_duration(total_duration)


# ---------------------------------------------------------------------------
# 5. Fade Through Black
# ---------------------------------------------------------------------------
def fade_through_black(clip1, clip2, duration=0.8):
    """
    clip1 fades to black, then clip2 fades in from black.

    The transition has two halves: fade-out and fade-in, each lasting
    duration/2 seconds.

    Args:
        clip1: Outgoing clip.
        clip2: Incoming clip.
        duration: Total transition duration in seconds.

    Returns:
        A single VideoClip with fade-through-black applied.
    """
    clip1, clip2 = _match_sizes(clip1, clip2)
    w, h = clip1.size
    half = duration / 2.0

    # clip1 fades out to black over the last half-duration
    clip1_faded = clip1.fadeout(half)

    # Black gap fills the middle
    black = (
        ColorClip(size=(w, h), color=(0, 0, 0))
        .set_duration(duration)
        .set_start(clip1.duration - half)
    )

    # clip2 fades in from black, starting after clip1 ends minus half
    clip2_faded = (
        clip2
        .fadein(half)
        .set_start(clip1.duration)
    )

    total_duration = clip1.duration + clip2.duration

    return CompositeVideoClip(
        [clip1_faded, black, clip2_faded],
        size=(w, h),
    ).set_duration(total_duration)


# ---------------------------------------------------------------------------
# 6. Blur Transition
# ---------------------------------------------------------------------------
def blur_transition(clip1, clip2, duration=0.6):
    """
    clip1 blurs out (increasing gaussian sigma), then clip2 blurs in
    (decreasing sigma).

    Uses scipy gaussian_filter for smooth, high-quality blur.

    Args:
        clip1: Outgoing clip.
        clip2: Incoming clip.
        duration: Total transition duration in seconds.

    Returns:
        A single VideoClip with the blur transition.
    """
    clip1, clip2 = _match_sizes(clip1, clip2)
    w, h = clip1.size
    half = duration / 2.0
    max_sigma = 12.0

    transition_start = clip1.duration - half

    # --- Blur OUT the end of clip1 ---
    def blur_out(get_frame, t):
        """Increasing blur during the last `half` seconds of clip1."""
        frame = get_frame(t)
        if t < transition_start:
            return frame
        progress = (t - transition_start) / half
        sigma = max_sigma * min(progress, 1.0)
        if sigma < 0.5:
            return frame
        blurred = gaussian_filter(frame.astype(np.float32), sigma=[sigma, sigma, 0])
        return np.clip(blurred, 0, 255).astype(np.uint8)

    clip1_blurred = clip1.fl(blur_out)

    # --- Blur IN the start of clip2 ---
    def blur_in(get_frame, t):
        """Decreasing blur during the first `half` seconds of clip2."""
        frame = get_frame(t)
        if t >= half:
            return frame
        progress = t / half
        sigma = max_sigma * (1.0 - min(progress, 1.0))
        if sigma < 0.5:
            return frame
        blurred = gaussian_filter(frame.astype(np.float32), sigma=[sigma, sigma, 0])
        return np.clip(blurred, 0, 255).astype(np.uint8)

    clip2_blurred = clip2.fl(blur_in).set_start(clip1.duration)

    total_duration = clip1.duration + clip2.duration

    return CompositeVideoClip(
        [clip1_blurred, clip2_blurred],
        size=(w, h),
    ).set_duration(total_duration)


# ---------------------------------------------------------------------------
# 7. White Flash
# ---------------------------------------------------------------------------
def white_flash_transition(clip1, clip2, duration=0.3):
    """
    Quick white flash between scenes.

    A white ColorClip appears between clip1 and clip2, fading in and out
    for a punchy, energetic transition.

    Args:
        clip1: Outgoing clip.
        clip2: Incoming clip.
        duration: Length of the white flash in seconds.

    Returns:
        A single VideoClip with the white flash transition.
    """
    clip1, clip2 = _match_sizes(clip1, clip2)
    w, h = clip1.size
    half = duration / 2.0

    # White flash clip — fades in then fades out
    flash = (
        ColorClip(size=(w, h), color=(255, 255, 255))
        .set_duration(duration)
        .set_start(clip1.duration - half)
        .fadein(half)
        .fadeout(half)
    )

    clip2_started = clip2.set_start(clip1.duration)

    total_duration = clip1.duration + clip2.duration

    return CompositeVideoClip(
        [clip1, flash, clip2_started],
        size=(w, h),
    ).set_duration(total_duration)


# ---------------------------------------------------------------------------
# 8. Random Transition Picker
# ---------------------------------------------------------------------------
def get_random_transition(clip1, clip2):
    """
    Randomly pick and apply one of the available transitions.

    Useful for variety when assembling many scenes automatically.

    Args:
        clip1: Outgoing clip.
        clip2: Incoming clip.

    Returns:
        A single VideoClip with a randomly chosen transition applied.
    """
    transitions = [
        crossfade_transition,
        slide_left_transition,
        slide_up_transition,
        zoom_transition,
        fade_through_black,
        blur_transition,
        white_flash_transition,
    ]

    chosen = random.choice(transitions)
    return chosen(clip1, clip2)
