"""
AI Director Module
===================
Maps mood values to visual-effect presets and preferred sound-effect
categories.  This is a lightweight configuration layer — no heavy logic,
just clean lookups with sensible defaults.
"""

# ---------------------------------------------------------------------------
# Mood → Visual Effects mapping
# ---------------------------------------------------------------------------

MOOD_PRESETS: dict[str, list[str]] = {
    "dramatic":    ["zoom_punch", "speed_ramp", "warm_grade"],
    "epic":        ["light_leak", "letterbox", "cool_grade"],
    "calm":        ["blur_reveal", "cool_grade", "slow_zoom"],
    "intense":     ["screen_shake", "glitch", "warm_grade", "zoom_punch"],
    "informative": ["ken_burns", "standard_grade"],
    "default":     ["ken_burns", "standard_grade"],
}

# ---------------------------------------------------------------------------
# Mood → Preferred SFX category
# ---------------------------------------------------------------------------

import random

def _random_sfx(choices):
    # This is a bit of a hack since SFX_MAP was a dict of strings.
    # We will redefine get_sfx_type_for_mood below to handle lists.
    pass

SFX_MAP: dict[str, list[str]] = {
    "dramatic":    ["impact", "riser"],
    "epic":        ["riser", "impact", "whoosh"],
    "calm":        ["whoosh"],
    "intense":     ["impact", "riser"],
    "informative": ["whoosh", "impact"],
    "default":     ["whoosh", "impact", "riser"],
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_effects_for_mood(mood: str) -> list[str]:
    """Return the list of effect names for *mood*.

    Parameters
    ----------
    mood : str
        A mood key such as ``'dramatic'``, ``'epic'``, ``'calm'``, etc.

    Returns
    -------
    list[str]
        Effect names from :data:`MOOD_PRESETS`.  Falls back to the
        ``'default'`` preset when *mood* is not recognised.

    Example
    -------
    >>> get_effects_for_mood('epic')
    ['light_leak', 'letterbox', 'cool_grade']
    """
    return MOOD_PRESETS.get(mood.lower().strip(), MOOD_PRESETS["default"])


def get_sfx_type_for_mood(mood: str) -> str:
    """Return the preferred SFX category for *mood*.

    Parameters
    ----------
    mood : str
        A mood key such as ``'dramatic'``, ``'intense'``, etc.

    Returns
    -------
    str
        One of ``'whoosh'``, ``'impact'``, or ``'riser'``.
        Falls back to a random choice if *mood* is not recognised.

    Example
    -------
    >>> get_sfx_type_for_mood('intense')
    'impact'
    """
    import random
    choices = SFX_MAP.get(mood.lower().strip(), SFX_MAP["default"])
    return random.choice(choices)
