import os
import sys
import json
import time
import threading
from flask import Flask, render_template, request, jsonify, send_file

# Add parent directory to path so we can import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)

# Shared progress state
progress = {
    "status": "idle",         # idle, running, complete, error
    "current_step": "",
    "step_number": 0,
    "total_steps": 10,
    "sub_progress": "",       # e.g., "Segment 3/15"
    "percentage": 0,
    "log": [],                # List of log messages
    "video_path": None,
    "error": None,
    "start_time": None,
    "elapsed": "0s"
}

STEPS = [
    "Generating Script",
    "Downloading Sound Effects",
    "Downloading Background Music",
    "Generating Voiceover",
    "Downloading Video Clips",
    "Generating Graphics",
    "Applying Visual Effects",
    "Assembling Video",
    "Mixing Audio",
    "Final Render"
]

def update_progress(step_number, step_name, sub="", percentage=None):
    """Update the shared progress state."""
    progress["step_number"] = step_number
    progress["current_step"] = step_name
    progress["sub_progress"] = sub
    if percentage is not None:
        progress["percentage"] = percentage
    else:
        progress["percentage"] = int((step_number / progress["total_steps"]) * 100)
    
    if progress["start_time"]:
        elapsed = time.time() - progress["start_time"]
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        progress["elapsed"] = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
    
    log_msg = f"[Step {step_number}/{progress['total_steps']}] {step_name}"
    if sub:
        log_msg += f" — {sub}"
    progress["log"].append(log_msg)
    print(log_msg)

def run_pipeline(topic, duration, language, custom_script=None, use_avatar=False, resolution="1080p"):
    """Run the full video generation pipeline in a background thread."""
    # Set resolution BEFORE importing modules so they pick up the right values
    from src.config import set_resolution, VIDEO_WIDTH, VIDEO_HEIGHT
    set_resolution(resolution)
    
    # Now import all modules (they cache VIDEO_WIDTH/VIDEO_HEIGHT at import time)
    from src.script_generator import generate_script
    from src.audio_generator import generate_audio
    from src.visuals_manager import download_video
    from src.typography import create_lower_third, create_chapter_card, create_watermark
    from src.cards import create_title_card, create_hook_card, create_outro_card
    from src.sound_design import download_sfx_library, download_background_music, create_ducked_audio, get_random_sfx
    from src.ai_director import get_effects_for_mood, get_sfx_type_for_mood
    from src.video_editor import assemble_video
    
    # Propagate the resolution to all already-imported modules
    # (because `from .config import VIDEO_WIDTH` caches the value at import time)
    import src.config as _cfg
    w, h = _cfg.VIDEO_WIDTH, _cfg.VIDEO_HEIGHT
    import src.video_editor, src.typography, src.cards, src.overlays, src.effects, src.transitions, src.avatar_engine
    for mod in [src.video_editor, src.typography, src.cards, src.overlays, src.effects, src.transitions, src.avatar_engine]:
        if hasattr(mod, 'VIDEO_WIDTH'):
            mod.VIDEO_WIDTH = w
        if hasattr(mod, 'VIDEO_HEIGHT'):
            mod.VIDEO_HEIGHT = h
    
    progress["status"] = "running"
    progress["start_time"] = time.time()
    progress["log"] = []
    progress["error"] = None
    progress["video_path"] = None
    
    import re
    safe_topic = re.sub(r'[^a-zA-Z0-9_\- ]', '', topic).strip().replace(' ', '_').lower()
    if not safe_topic:
        safe_topic = f"video_{int(time.time())}"
        
    workspace_dir = os.path.join("output_workspace", safe_topic)
    os.makedirs(workspace_dir, exist_ok=True)
    
    try:
        # Step 1: Generate Script
        if custom_script:
            update_progress(1, "Generating Script", "Using custom provided script")
            import json
            script_data = json.loads(custom_script)
            if not topic:
                topic = script_data.get("title", "Custom Video")
        else:
            update_progress(1, "Generating Script", f"Topic: {topic}, Duration: {duration}min, Language: {language}")
            script_data = generate_script(topic, duration, language)
        
        # Save metadata
        metadata_path = os.path.join(workspace_dir, "youtube_metadata.txt")
        with open(metadata_path, "w", encoding="utf-8") as f:
            f.write(f"TITLE: {script_data.get('title', '')}\n\n")
            f.write(f"DESCRIPTION: {script_data.get('description', '')}\n\n")
            f.write(f"TAGS: {', '.join(script_data.get('tags', []))}\n")
        
        segments = script_data.get("segments", [])
        if not segments:
            raise ValueError("No segments generated in the script.")
        update_progress(1, "Generating Script", f"Generated {len(segments)} segments", 10)
        
        # Step 2: Download SFX Library
        update_progress(2, "Downloading Sound Effects", "Fetching whoosh, impact, and riser sounds...")
        sfx_library = download_sfx_library(workspace_dir)
        update_progress(2, "Downloading Sound Effects", "SFX library ready", 20)
        
        # Step 3: Download Background Music
        update_progress(3, "Downloading Background Music", "Fetching ambient music track...")
        music_path = download_background_music(workspace_dir)
        update_progress(3, "Downloading Background Music", "Music ready" if music_path else "No music (continuing without)", 25)
        
        # Step 4: Generate Voiceover
        update_progress(4, "Generating Voiceover", "Creating continuous narration...")
        full_script_text = " ".join([seg["voiceover"] for seg in segments])
        full_audio_path = os.path.join(workspace_dir, "full_voiceover.mp3")
        generate_audio(full_script_text, full_audio_path, language)
        
        # Mix with background music (ducking)
        if music_path:
            update_progress(4, "Generating Voiceover", "Applying audio ducking to background music...")
            mixed_audio_path = os.path.join(workspace_dir, "mixed_audio.mp3")
            create_ducked_audio(full_audio_path, music_path, mixed_audio_path)
            final_audio_path = mixed_audio_path
        else:
            final_audio_path = full_audio_path
        # Step 5: Downloading Video Clips
        update_progress(5, "Downloading Video Clips", "Fetching stock footage in parallel...")
        segments_data = [None] * len(segments)
        
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def download_segment(idx, seg):
            video_path = os.path.join(workspace_dir, f"video_{idx}.mp4")
            subtitle_path = os.path.join(workspace_dir, f"lower_third_{idx}.png")
            
            from src.typography import create_lower_third
            create_lower_third(seg.get("key_term", ""), subtitle_path)
            
            try:
                download_video(seg["search_query"], seg["voiceover"], video_path)
            except Exception as e:
                print(f"Failed to download video: {e}")
                try:
                    download_video("nature", seg["voiceover"], video_path)
                except Exception:
                    pass
            
            return idx, {
                "voiceover": seg["voiceover"],
                "video_path": video_path,
                "subtitle_path": subtitle_path,
                "key_term": seg.get("key_term", ""),
                "mood": seg.get("mood", "informative")
            }
            
        completed_downloads = 0
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_idx = {executor.submit(download_segment, idx, seg): idx for idx, seg in enumerate(segments)}
            for future in as_completed(future_to_idx):
                idx, data = future.result()
                segments_data[idx] = data
                completed_downloads += 1
                pct = 40 + (completed_downloads / len(segments)) * 30
                update_progress(5, f"Downloading Video Clips ({completed_downloads}/{len(segments)})", f"Downloaded video for: {segments[idx]['search_query']}", pct)
                
        # Filter out failed downloads
        segments_data = [s for s in segments_data if s is not None]
        update_progress(5, "Downloading Video Clips", f"All {len(segments_data)} clips ready", 55)
        
        # Step 6: Generate Graphics
        update_progress(6, "Generating Graphics", "Creating lower thirds, cards, overlays...")
        
        # Generate cards
        hook_text = segments[0]["voiceover"] if segments else topic
        hook_path = os.path.join(workspace_dir, "hook_card.png")
        title_path = os.path.join(workspace_dir, "title_card.png")
        outro_path = os.path.join(workspace_dir, "outro_card.png")
        watermark_path = os.path.join(workspace_dir, "watermark.png")
        
        create_hook_card(hook_text, hook_path)
        create_title_card(script_data.get("title", topic), title_path)
        create_outro_card("AI Studio", outro_path)
        create_watermark("AI Studio", watermark_path)
        update_progress(6, "Generating Graphics", "All graphics ready", 65)
        
        # Steps 7-10: Assemble Video (the editor handles these internally)
        update_progress(7, "Assembling Video", "Applying effects, transitions, and rendering...")
        
        final_output_path = os.path.join(workspace_dir, "final_video.mp4")
        assemble_video(
            segments_data=segments_data,
            full_audio_path=final_audio_path,
            sfx_library=sfx_library,
            output_path=final_output_path,
            hook_card_path=hook_path,
            title_card_path=title_path,
            outro_card_path=outro_path,
            watermark_path=watermark_path,
            use_avatar=use_avatar,
            progress_callback=update_progress
        )
        
        # Cleanup temp files
        update_progress(10, "Final Render", "Cleaning up temporary files...")
        for seg in segments_data:
            for key in ["subtitle_path", "video_path"]:
                try: os.remove(seg.get(key, ""))
                except: pass
        for f in [full_audio_path, final_audio_path, hook_path, title_path, outro_path, watermark_path]:
            try: os.remove(f)
            except: pass
        
        progress["status"] = "complete"
        progress["video_path"] = os.path.abspath(final_output_path)
        progress["percentage"] = 100
        update_progress(10, "Final Render", "✅ Video complete!")
        
    except Exception as e:
        progress["status"] = "error"
        progress["error"] = str(e)
        progress["log"].append(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.json
    topic = data.get("topic", "")
    duration = int(data.get("duration", 2))
    language = data.get("language", "English")
    custom_script = data.get("custom_script", "")
    use_avatar = data.get("use_avatar", False)
    resolution = data.get("resolution", "1080p")
    
    if not topic and not custom_script:
        return jsonify({"error": "Topic or Custom Script is required"}), 400
    
    if progress["status"] == "running":
        return jsonify({"error": "A video is already being generated"}), 409
    
    # Reset progress
    progress["status"] = "running"
    progress["percentage"] = 0
    
    # Run pipeline in background thread
    thread = threading.Thread(target=run_pipeline, args=(topic, duration, language, custom_script, use_avatar, resolution), daemon=True)
    thread.start()
    
    return jsonify({"message": "Pipeline started"})

@app.route("/api/progress")
def get_progress():
    return jsonify(progress)

@app.route("/api/download")
def download_video_file():
    if progress["video_path"] and os.path.exists(progress["video_path"]):
        return send_file(progress["video_path"], as_attachment=True, download_name="final_video.mp4")
    return jsonify({"error": "No video available"}), 404

if __name__ == "__main__":
    print("\n🎬 YouTube Automation Studio")
    print("=" * 40)
    print("Open your browser to: http://127.0.0.1:5000")
    print("=" * 40 + "\n")
    app.run(debug=False, port=5000)
