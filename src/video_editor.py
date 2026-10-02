"""
FFmpeg-native video assembly engine.
Replaces MoviePy with raw FFmpeg filter chains for 10-50x faster rendering.
All pixel-level processing (color grading, grain, vignette, transitions) is
handled by FFmpeg's optimized C code instead of Python/numpy.
"""
import os
import re
import random
import shutil
import subprocess
import imageio_ffmpeg
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS
from .ai_director import get_effects_for_mood, get_sfx_type_for_mood
from .sound_design import get_random_sfx

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# Cinematic transitions available in FFmpeg xfade filter
XFADE_TRANSITIONS = [
    "fade", "wipeleft", "wiperight", "fadeblack", "fadewhite",
    "circleopen", "circleclose", "dissolve", "slideleft", "slideright",
    "smoothleft", "smoothright", "radial",
]


# ─────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────

def _get_media_duration(path):
    """Get duration of a media file by parsing ffmpeg stderr output."""
    result = subprocess.run(
        [FFMPEG, "-i", path],
        stderr=subprocess.PIPE, stdout=subprocess.PIPE
    )
    stderr = result.stderr.decode(errors="ignore")
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", stderr)
    if match:
        h, m, s, cs = (
            int(match.group(1)), int(match.group(2)),
            int(match.group(3)), int(match.group(4))
        )
        return h * 3600 + m * 60 + s + cs / 100.0
    return 0


def _run_ffmpeg(cmd, label=""):
    """Run an FFmpeg command. Returns True on success, False on failure."""
    print(f"  [FFmpeg] {label}...", flush=True)
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        err = proc.stderr.decode(errors="ignore")
        print(f"  [FFmpeg Error] {label}: ...{err[-500:]}")
        return False
    print(f"  [FFmpeg] {label} ✓", flush=True)
    return True


# ─────────────────────────────────────────────
# Pass 1: Process individual segments
# ─────────────────────────────────────────────

def _process_segment(args):
    """
    Process a single video segment with FFmpeg filters.
    Applies: scale, color grading, film grain, vignette, subtitle overlay.
    Runs as a thread pool task — each spawns its own FFmpeg subprocess.
    """
    video_path = args["video_path"]
    output_path = args["output_path"]
    duration = args["duration"]
    subtitle_path = args.get("subtitle_path")
    w, h, fps = args["width"], args["height"], args["fps"]
    idx = args["idx"]

    # Check if source video needs looping (shorter than segment duration)
    src_duration = _get_media_duration(video_path)

    cmd = [FFMPEG, "-y"]

    # Loop input if it's shorter than the required segment duration
    if src_duration > 0 and src_duration < duration:
        loops = int(duration / src_duration) + 1
        cmd.extend(["-stream_loop", str(loops)])

    cmd.extend(["-i", video_path])

    # Build video filter chain
    vfilters = [
        # 1. Scale to target resolution (pad with black bars if aspect ratio differs)
        f"scale={w}:{h}:force_original_aspect_ratio=decrease",
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
        # 2. Set frame rate
        f"fps={fps}",
        # 3. Cinematic teal/orange color grading
        "colorbalance=rs=-0.12:gs=0.05:bs=0.12:rh=0.12:gh=0:bh=-0.12",
        # 4. Subtle film grain (luma-only, temporal)
        "noise=c0s=8:c0f=t+u",
        # 5. Vignette (edge darkening)
        "vignette=angle=PI/5",
        # 6. Ensure pixel format compatibility for H.264
        "format=yuv420p",
    ]

    has_subtitle = subtitle_path and os.path.exists(subtitle_path)

    if has_subtitle:
        cmd.extend(["-i", subtitle_path])
        # Chain: process video → overlay subtitle PNG on top
        sub_end = min(3.5, duration - 0.3)
        vfilter_str = (
            f"[0:v]{','.join(vfilters)}[base];"
            f"[1:v]format=rgba[ovr];"
            f"[base][ovr]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2"
            f":enable='between(t,0.5,{sub_end:.1f})'[out]"
        )
        cmd.extend(["-filter_complex", vfilter_str, "-map", "[out]"])
    else:
        cmd.extend(["-vf", ",".join(vfilters)])

    cmd.extend([
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-an",           # No audio — we mix audio separately
        output_path,
    ])

    success = _run_ffmpeg(cmd, f"Segment {idx + 1}")
    return {
        "idx": idx,
        "success": success,
        "output_path": output_path,
        "duration": duration,
    }


# ─────────────────────────────────────────────
# Pass 2: Concatenation & Transitions
# ─────────────────────────────────────────────

def _concatenate_with_transitions(segment_paths, segment_durations, output_path, td=0.3):
    """
    Concatenate video segments with random xfade transitions.
    td = transition duration in seconds.
    Falls back to simple concat if xfade fails.
    """
    n = len(segment_paths)
    if n == 0:
        return False
    if n == 1:
        shutil.copy2(segment_paths[0], output_path)
        return True

    cmd = [FFMPEG, "-y"]

    # Add all segment files as inputs
    for path in segment_paths:
        cmd.extend(["-i", path])

    # Build the xfade filter chain
    # For N clips, we need N-1 xfade operations chained together.
    # offset for xfade_i = sum(durations[0..i]) - (i+1) * td
    filter_parts = []
    cumulative = 0.0

    for i in range(n - 1):
        transition = random.choice(XFADE_TRANSITIONS)
        cumulative += segment_durations[i]
        offset = cumulative - (i + 1) * td
        offset = max(0.1, offset)  # Safety: never negative

        in1 = "[0:v]" if i == 0 else f"[v{i-1}]"
        in2 = f"[{i+1}:v]"
        out = "[vout]" if i == n - 2 else f"[v{i}]"

        filter_parts.append(
            f"{in1}{in2}xfade=transition={transition}:duration={td}:offset={offset:.3f}{out}"
        )

    filter_str = ";".join(filter_parts)

    cmd.extend([
        "-filter_complex", filter_str,
        "-map", "[vout]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-an",
        output_path,
    ])

    return _run_ffmpeg(cmd, f"xfade transitions ({n} clips)")


def _concatenate_simple(file_paths, output_path):
    """Fast lossless concat using demuxer (requires identical format)."""
    workspace = os.path.dirname(output_path) or "."
    list_path = os.path.join(workspace, "_concat_list.txt")

    with open(list_path, "w") as f:
        for p in file_paths:
            abs_path = os.path.abspath(p).replace("\\", "/")
            f.write(f"file '{abs_path}'\n")

    cmd = [
        FFMPEG, "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        output_path,
    ]

    success = _run_ffmpeg(cmd, "Simple concat")
    try:
        os.remove(list_path)
    except OSError:
        pass
    return success


# ─────────────────────────────────────────────
# Pass 3: Intro/Outro card videos
# ─────────────────────────────────────────────

def _create_card_video(image_path, output_path, duration, w, h, fps):
    """Convert a static PNG card image into a short video clip with fade in/out."""
    cmd = [
        FFMPEG, "-y",
        "-loop", "1",
        "-i", image_path,
        "-vf", (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,"
            f"fps={fps},"
            f"fade=t=in:d=0.5,fade=t=out:st={max(0, duration - 0.5):.2f}:d=0.5,"
            f"format=yuv420p"
        ),
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-an",
        output_path,
    ]
    return _run_ffmpeg(cmd, f"Card: {os.path.basename(image_path)}")


# ─────────────────────────────────────────────
# Pass 4: Audio mixing
# ─────────────────────────────────────────────

def _mix_final_audio(voiceover_path, sfx_list, output_path, intro_delay=0.0):
    """
    Mix voiceover (with optional intro delay) + SFX into a single audio file.
    sfx_list = list of (sfx_file_path, start_time_seconds) tuples.
    """
    cmd = [FFMPEG, "-y", "-i", voiceover_path]

    # Add SFX inputs
    for sfx_path, _ in sfx_list:
        cmd.extend(["-i", sfx_path])

    n_inputs = 1 + len(sfx_list)
    filter_parts = []

    # Voiceover — delay by intro duration if needed
    delay_ms = int(intro_delay * 1000)
    if delay_ms > 0:
        filter_parts.append(f"[0:a]adelay={delay_ms}|{delay_ms},volume=1.0[vo]")
    else:
        filter_parts.append("[0:a]volume=1.0[vo]")

    # Each SFX at its timestamp, at 20% volume
    sfx_labels = []
    for i, (_, start_time) in enumerate(sfx_list):
        label = f"sfx{i}"
        d = int(start_time * 1000)
        filter_parts.append(
            f"[{i+1}:a]volume=0.20,adelay={d}|{d}[{label}]"
        )
        sfx_labels.append(f"[{label}]")

    # Mix everything together
    all_labels = "[vo]" + "".join(sfx_labels)
    filter_parts.append(
        f"{all_labels}amix=inputs={n_inputs}:duration=longest:normalize=0[aout]"
    )

    cmd.extend([
        "-filter_complex", ";".join(filter_parts),
        "-map", "[aout]",
        "-c:a", "aac",
        "-b:a", "192k",
        output_path,
    ])

    return _run_ffmpeg(cmd, "Audio mix")


# ─────────────────────────────────────────────
# Main entry point (drop-in replacement)
# ─────────────────────────────────────────────

def assemble_video(
    segments_data,
    full_audio_path,
    sfx_library,
    output_path,
    hook_card_path=None,
    title_card_path=None,
    outro_card_path=None,
    watermark_path=None,
    use_avatar=False,
    avatar_closed="assets/avatar/default_closed.png",
    avatar_open="assets/avatar/default_open.png",
    progress_callback=None,
):
    """
    Assemble the final video using native FFmpeg filter chains.
    Drop-in replacement for the old MoviePy-based version.
    
    Pipeline:
      1. Process each segment in parallel (scale + color grade + grain + vignette)
      2. Join segments with xfade transitions
      3. Prepend intro cards, append outro card
      4. Mix voiceover + SFX audio
      5. Final mux: video + audio + watermark overlay
    """
    w, h, fps = VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS

    def log(step, msg, sub="", pct=None):
        if progress_callback:
            progress_callback(step, msg, sub, pct)
        else:
            print(f"  [{msg}] {sub}")

    workspace = os.path.dirname(output_path) or "."

    # ── Calculate segment durations from voiceover lengths ──
    log(7, "Preparing Timeline", "Calculating segment durations...")

    audio_duration = _get_media_duration(full_audio_path)
    if audio_duration <= 0:
        raise RuntimeError(f"Could not determine audio duration for {full_audio_path}")

    total_chars = sum(len(seg["voiceover"]) for seg in segments_data)

    intro_duration = 0.0
    if hook_card_path and os.path.exists(hook_card_path):
        intro_duration += 1.5
    if title_card_path and os.path.exists(title_card_path):
        intro_duration += 3.0

    # Distribute audio duration proportionally by character count
    segment_durations = []
    for seg in segments_data:
        dur = audio_duration * (len(seg["voiceover"]) / total_chars)
        segment_durations.append(max(dur, 1.5))

    # Fix last segment to absorb rounding errors
    if segment_durations:
        used = sum(segment_durations[:-1])
        segment_durations[-1] = max(1.5, audio_duration - used)

    # ── PASS 1: Process all segments in parallel ──
    log(7, "Assembling Video",
        f"Processing {len(segments_data)} clips with FFmpeg filters (parallel)...")

    tasks = []
    for idx, seg in enumerate(segments_data):
        tasks.append({
            "idx": idx,
            "video_path": seg["video_path"],
            "output_path": os.path.join(workspace, f"_seg_{idx}.mp4"),
            "duration": segment_durations[idx],
            "subtitle_path": seg.get("subtitle_path"),
            "mood": seg.get("mood", "informative"),
            "width": w, "height": h, "fps": fps,
        })

    results = []
    done_count = 0
    max_workers = min(6, len(tasks))  # Up to 6 parallel FFmpeg processes

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_segment, t): t for t in tasks}
        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            done_count += 1
            pct = 60 + (done_count / len(tasks)) * 15
            log(7, "Assembling Video",
                f"Segment {done_count}/{len(tasks)} done", pct)

    results.sort(key=lambda x: x["idx"])
    valid = [r for r in results if r["success"]]
    if not valid:
        raise RuntimeError("All video segments failed to process!")

    valid_paths = [r["output_path"] for r in valid]
    valid_durations = [r["duration"] for r in valid]

    # ── PASS 2: Concatenate with transitions ──
    log(8, "Transitions",
        f"Joining {len(valid_paths)} clips with cinematic transitions...")

    content_path = os.path.join(workspace, "_content.mp4")

    if len(valid_paths) > 1:
        ok = _concatenate_with_transitions(
            valid_paths, valid_durations, content_path, td=0.3
        )
        if not ok:
            print("  [Fallback] xfade failed, falling back to simple concat.")
            ok = _concatenate_simple(valid_paths, content_path)
        if not ok:
            raise RuntimeError("Segment concatenation failed!")
    else:
        shutil.copy2(valid_paths[0], content_path)

    log(8, "Transitions", "Clips joined ✓", 80)

    # ── PASS 3: Add intro/outro cards ──
    log(8, "Cards", "Adding intro and outro cards...")

    parts = []  # ordered list of video files to concat

    if hook_card_path and os.path.exists(hook_card_path):
        p = os.path.join(workspace, "_hook.mp4")
        if _create_card_video(hook_card_path, p, 1.5, w, h, fps):
            parts.append(p)

    if title_card_path and os.path.exists(title_card_path):
        p = os.path.join(workspace, "_title.mp4")
        if _create_card_video(title_card_path, p, 3.0, w, h, fps):
            parts.append(p)

    parts.append(content_path)

    if outro_card_path and os.path.exists(outro_card_path):
        p = os.path.join(workspace, "_outro.mp4")
        if _create_card_video(outro_card_path, p, 4.0, w, h, fps):
            parts.append(p)

    if len(parts) > 1:
        full_video = os.path.join(workspace, "_full_video.mp4")
        _concatenate_simple(parts, full_video)
    else:
        full_video = content_path

    log(8, "Cards", "Cards added ✓", 85)

    # ── PASS 4: Mix audio (voiceover + SFX) ──
    log(9, "Mixing Audio", "Combining voiceover with sound effects...")

    sfx_list = []
    current_time = intro_duration
    for idx, seg in enumerate(segments_data):
        if idx > 0 and sfx_library:
            mood = seg.get("mood", "informative")
            sfx_type = get_sfx_type_for_mood(mood)
            sfx_path = get_random_sfx(sfx_library, sfx_type)
            if sfx_path and os.path.exists(sfx_path):
                sfx_list.append((sfx_path, current_time))
        if idx < len(segment_durations):
            current_time += segment_durations[idx]

    mixed_audio = os.path.join(workspace, "_mixed_audio.m4a")

    if sfx_list:
        ok = _mix_final_audio(
            full_audio_path, sfx_list, mixed_audio,
            intro_delay=intro_duration
        )
        if not ok:
            # Fallback: just use raw voiceover
            shutil.copy2(full_audio_path, mixed_audio)
    else:
        # No SFX, but still need to delay voiceover by intro duration
        if intro_duration > 0:
            delay_ms = int(intro_duration * 1000)
            cmd = [
                FFMPEG, "-y", "-i", full_audio_path,
                "-af", f"adelay={delay_ms}|{delay_ms}",
                "-c:a", "aac", "-b:a", "192k",
                mixed_audio,
            ]
            if not _run_ffmpeg(cmd, "Delay voiceover"):
                shutil.copy2(full_audio_path, mixed_audio)
        else:
            shutil.copy2(full_audio_path, mixed_audio)

    log(9, "Mixing Audio", "Audio mixed ✓", 90)

    # ── PASS 5: Final composite (video + audio + watermark) ──
    log(10, "Final Render", "Muxing video + audio + overlays...")

    cmd = [FFMPEG, "-y", "-i", full_video, "-i", mixed_audio]

    has_overlay = False

    if watermark_path and os.path.exists(watermark_path):
        cmd.extend(["-i", watermark_path])
        cmd.extend([
            "-filter_complex",
            "[0:v][2:v]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2,"
            "format=yuv420p[vout]",
            "-map", "[vout]",
            "-map", "1:a",
        ])
        has_overlay = True

    if not has_overlay:
        cmd.extend(["-map", "0:v", "-map", "1:a"])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",  # Web-optimized MP4
        output_path,
    ])

    ok = _run_ffmpeg(cmd, "Final render")
    if not ok:
        raise RuntimeError("Final render failed!")

    # ── Cleanup temporary files ──
    temp_patterns = ["_seg_", "_content", "_hook", "_title", "_outro",
                     "_full_video", "_mixed_audio", "_concat_list"]
    for fname in os.listdir(workspace):
        if any(fname.startswith(p) for p in temp_patterns):
            try:
                os.remove(os.path.join(workspace, fname))
            except OSError:
                pass

    log(10, "Final Render", f"✅ Video saved to {output_path}", 100)
