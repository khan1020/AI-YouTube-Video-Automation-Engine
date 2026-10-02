"""
Sound Design Module
====================
Downloads free sound effects and background music from Google Actions Sounds
library (all public domain), provides random SFX selection, and mixes
voiceover with background music using audio ducking.

Replaces the old sfx_manager.py.
"""

import os
import random
import requests


# ---------------------------------------------------------------------------
# Google Actions Sounds URLs — all public-domain, direct HTTP downloads
# ---------------------------------------------------------------------------

_WHOOSH_URLS = [
    "https://actions.google.com/sounds/v1/foley/swoosh.ogg",
    "https://actions.google.com/sounds/v1/foley/swoosh_fast.ogg",
    "https://actions.google.com/sounds/v1/foley/paper_slide.ogg",
]

_IMPACT_URLS = [
    "https://actions.google.com/sounds/v1/impacts/wood_pieces_falling.ogg",
    "https://actions.google.com/sounds/v1/impacts/punch_body.ogg",
]

_RISER_URLS = [
    "https://actions.google.com/sounds/v1/science_fiction/robot_power_up.ogg",
]

_MUSIC_URLS = [
    "https://actions.google.com/sounds/v1/ambiences/forest_with_birds.ogg",
    "https://actions.google.com/sounds/v1/ambiences/ocean_waves.ogg",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _download_file(url: str, dest_path: str) -> bool:
    """Download a single file from *url* to *dest_path*.

    Returns True on success, False on any failure (network, disk, etc.).
    Already-cached files are skipped automatically.
    """
    # Skip if already downloaded
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        return True

    try:
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        with open(dest_path, "wb") as fh:
            for chunk in response.iter_content(chunk_size=8192):
                fh.write(chunk)

        return True
    except Exception as exc:
        print(f"[sound_design] Failed to download {url}: {exc}")
        # Clean up partial downloads
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except OSError:
                pass
        return False


def _filename_from_url(url: str) -> str:
    """Extract the filename portion from a URL."""
    return url.rsplit("/", 1)[-1]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def download_sfx_library(workspace_dir: str) -> dict:
    """Download multiple sound effects from Google Actions Sounds.

    Parameters
    ----------
    workspace_dir : str
        Root directory of the project.  SFX files are stored under
        ``<workspace_dir>/assets/sfx/``.

    Returns
    -------
    dict
        Mapping of SFX category to list of local file paths, e.g.::

            {
                'whoosh': ['path1.ogg', 'path2.ogg'],
                'impact': ['path3.ogg'],
                'riser':  ['path4.ogg'],
            }

        Categories with zero successful downloads are still present as
        empty lists.
    """
    sfx_dir = os.path.join(workspace_dir, "assets", "sfx")
    os.makedirs(sfx_dir, exist_ok=True)

    # Category name → list of URLs
    categories = {
        "whoosh": _WHOOSH_URLS,
        "impact": _IMPACT_URLS,
        "riser": _RISER_URLS,
    }

    library: dict[str, list[str]] = {cat: [] for cat in categories}

    for category, urls in categories.items():
        for url in urls:
            filename = _filename_from_url(url)
            dest = os.path.join(sfx_dir, filename)

            if _download_file(url, dest):
                library[category].append(dest)

    downloaded_total = sum(len(v) for v in library.values())
    print(f"[sound_design] SFX library ready — {downloaded_total} files across "
          f"{len(library)} categories.")
    return library


def download_background_music(workspace_dir: str) -> str | None:
    """Download a free ambient music track for background use.

    Tries the primary URL first, then a fallback.  Returns the local
    path on success, or ``None`` if both URLs fail.

    Parameters
    ----------
    workspace_dir : str
        Root directory of the project.  Music is stored under
        ``<workspace_dir>/assets/music/``.
    """
    music_dir = os.path.join(workspace_dir, "assets", "music")
    os.makedirs(music_dir, exist_ok=True)

    for url in _MUSIC_URLS:
        filename = _filename_from_url(url)
        dest = os.path.join(music_dir, filename)

        if _download_file(url, dest):
            print(f"[sound_design] Background music ready: {filename}")
            return dest

    print("[sound_design] WARNING — could not download any background music.")
    return None


def get_random_sfx(sfx_library: dict, sfx_type: str = "whoosh") -> str | None:
    """Return a random sound-effect path from *sfx_library*.

    Parameters
    ----------
    sfx_library : dict
        The dictionary returned by :func:`download_sfx_library`.
    sfx_type : str
        Category key, e.g. ``'whoosh'``, ``'impact'``, ``'riser'``.

    Returns
    -------
    str or None
        Path to a randomly chosen ``.ogg`` file, or ``None`` if the
        category doesn't exist or is empty.
    """
    paths = sfx_library.get(sfx_type, [])
    if not paths:
        return None
    return random.choice(paths)


def create_ducked_audio(
    voiceover_path: str,
    music_path: str,
    output_path: str,
    music_volume: float = 0.12,
) -> str:
    """Mix voiceover with background music, applying audio ducking.

    The music is automatically looped/trimmed to match the voiceover
    length, reduced to *music_volume* (linear gain), and further ducked
    by 12 dB wherever the voiceover is active (dBFS > -35).

    Parameters
    ----------
    voiceover_path : str
        Path to the voiceover audio file (any format pydub supports).
    music_path : str
        Path to the background music file.
    output_path : str
        Destination path for the mixed MP3 output.
    music_volume : float
        Linear volume multiplier applied to the music *before* ducking.
        Default ``0.12`` keeps music quiet beneath narration.

    Returns
    -------
    str
        *output_path* on success, or *voiceover_path* as a graceful
        fallback if anything goes wrong.
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        print("[sound_design] pydub not installed — skipping audio ducking.")
        return voiceover_path

    try:
        # ------------------------------------------------------------------
        # 1. Load audio
        # ------------------------------------------------------------------
        voiceover = AudioSegment.from_file(voiceover_path)
        music = AudioSegment.from_file(music_path)

        vo_len = len(voiceover)  # milliseconds

        # ------------------------------------------------------------------
        # 2. Adjust music volume (linear → dB conversion)
        # ------------------------------------------------------------------
        import math
        if music_volume > 0:
            gain_db = 20 * math.log10(music_volume)
            music = music + gain_db  # pydub overloads + for dB gain
        else:
            music = music - 60  # effectively silent

        # ------------------------------------------------------------------
        # 3. Loop or trim music to match voiceover length
        # ------------------------------------------------------------------
        if len(music) < vo_len:
            # Loop music until it's long enough
            loops_needed = (vo_len // len(music)) + 1
            music = music * loops_needed

        music = music[:vo_len]  # trim to exact voiceover length

        # ------------------------------------------------------------------
        # 4. Audio ducking — reduce music where voice is active
        # ------------------------------------------------------------------
        chunk_ms = 100  # analyse in 100 ms chunks
        ducked_music = AudioSegment.empty()

        for start_ms in range(0, vo_len, chunk_ms):
            end_ms = min(start_ms + chunk_ms, vo_len)

            vo_chunk = voiceover[start_ms:end_ms]
            music_chunk = music[start_ms:end_ms]

            # If the voiceover chunk is loud enough, duck the music
            if vo_chunk.dBFS > -35:
                music_chunk = music_chunk - 12  # reduce by 12 dB

            ducked_music += music_chunk

        # ------------------------------------------------------------------
        # 5. Fade in / fade out on music
        # ------------------------------------------------------------------
        fade_in_ms = min(3000, vo_len // 2)   # 3 s fade-in
        fade_out_ms = min(4000, vo_len // 2)  # 4 s fade-out

        ducked_music = ducked_music.fade_in(fade_in_ms).fade_out(fade_out_ms)

        # ------------------------------------------------------------------
        # 6. Overlay voiceover on ducked music and export
        # ------------------------------------------------------------------
        final_mix = ducked_music.overlay(voiceover)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        final_mix.export(output_path, format="mp3")

        print(f"[sound_design] Ducked audio exported → {output_path}")
        return output_path

    except Exception as exc:
        print(f"[sound_design] Audio ducking failed: {exc}")
        return voiceover_path
