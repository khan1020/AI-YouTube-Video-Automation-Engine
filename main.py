import os
import sys
import json
from src.script_generator import generate_script
from src.audio_generator import generate_audio
from src.visuals_manager import download_video
from src.video_editor import assemble_video
from src.typography import create_lower_third, create_chapter_card, create_watermark
from src.cards import create_title_card, create_hook_card, create_outro_card
from src.sound_design import download_sfx_library, download_background_music, create_ducked_audio, get_random_sfx
from src.ai_director import get_effects_for_mood, get_sfx_type_for_mood

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py \"<Your Video Topic>\" [duration_minutes] [language]")
        print("Example: python main.py \"Space Facts\" 5 \"Hindi\"")
        print("\nTo run the Web UI Dashboard instead, run: python web/app.py")
        sys.exit(1)
        
    topic = sys.argv[1]
    
    duration_minutes = 2
    if len(sys.argv) >= 3:
        try:
            duration_minutes = int(sys.argv[2])
        except ValueError:
            print("Error: duration_minutes must be an integer (e.g. 5)")
            sys.exit(1)
            
    language = "English"
    if len(sys.argv) >= 4:
        language = sys.argv[3]
            
    print(f"--- Starting YouTube Automation Pipeline (Phase 3) ---")
    print(f"Topic: {topic}")
    print(f"Target Duration: ~{duration_minutes} minutes")
    print(f"Language: {language}")
    
    import re
    import time
    safe_topic = re.sub(r'[^a-zA-Z0-9_\- ]', '', topic).strip().replace(' ', '_').lower()
    if not safe_topic:
        safe_topic = f"video_{int(time.time())}"
        
    workspace_dir = os.path.join("output_workspace", safe_topic)
    os.makedirs(workspace_dir, exist_ok=True)
    
    print("\n[1/7] Generating Script...")
    try:
        script_data = generate_script(topic, duration_minutes, language)
    except Exception as e:
        print(f"Failed to generate script: {e}")
        print("Did you set your OPENROUTER_API_KEY in the .env file?")
        sys.exit(1)
        
    metadata_path = os.path.join(workspace_dir, "youtube_metadata.txt")
    with open(metadata_path, "w", encoding="utf-8") as f:
        f.write(f"TITLE: {script_data.get('title', '')}\n\n")
        f.write(f"DESCRIPTION: {script_data.get('description', '')}\n\n")
        f.write(f"TAGS: {', '.join(script_data.get('tags', []))}\n")
    print(f"Metadata saved to {metadata_path}")
    
    segments = script_data.get("segments", [])
    if not segments:
        print("Error: No segments generated in the script.")
        sys.exit(1)
        
    print("\n[2/7] Fetching Sound Design Assets...")
    print("Downloading SFX...")
    sfx_library = download_sfx_library(workspace_dir)
    print("Downloading Background Music...")
    music_path = download_background_music(workspace_dir)
    
    print("\n[3/7] Generating Continuous Voiceover & Mixing Audio...")
    full_script_text = " ".join([seg["voiceover"] for seg in segments])
    full_audio_path = os.path.join(workspace_dir, "full_voiceover.mp3")
    generate_audio(full_script_text, full_audio_path, language)
    
    if music_path:
        print("Applying audio ducking to background music...")
        final_audio_path = os.path.join(workspace_dir, "mixed_audio.mp3")
        create_ducked_audio(full_audio_path, music_path, final_audio_path)
    else:
        final_audio_path = full_audio_path
        
    print("\n[4/7] Generating Graphics (Cards, Overlays, Typography)...")
    hook_text = segments[0]["voiceover"] if segments else topic
    hook_path = os.path.join(workspace_dir, "hook_card.png")
    title_path = os.path.join(workspace_dir, "title_card.png")
    outro_path = os.path.join(workspace_dir, "outro_card.png")
    watermark_path = os.path.join(workspace_dir, "watermark.png")
    
    create_hook_card(hook_text, hook_path)
    create_title_card(script_data.get("title", topic), title_path)
    create_outro_card("AI Studio", outro_path)
    create_watermark("AI Studio", watermark_path)
    
    print("\n[5/7] Downloading Video Clips (Parallel)...")
    segments_data = [None] * len(segments)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def download_segment(idx, seg):
        video_path = os.path.join(workspace_dir, f"video_{idx}.mp4")
        subtitle_path = os.path.join(workspace_dir, f"lower_third_{idx}.png")
        
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
            print(f"--- Downloaded Segment {completed_downloads}/{len(segments)} ---")
            
    segments_data = [s for s in segments_data if s is not None]
        
    if not segments_data:
        print("Error: No segments were successfully generated.")
        sys.exit(1)
        
    print("\n[6/7] Assembling Final Video (Applying Cinematic Effects & Transitions)...")
    final_output_path = os.path.join(workspace_dir, "final_video.mp4")
    assemble_video(
        segments_data=segments_data,
        full_audio_path=final_audio_path,
        sfx_library=sfx_library,
        output_path=final_output_path,
        hook_card_path=hook_path,
        title_card_path=title_path,
        outro_card_path=outro_path,
        watermark_path=watermark_path
    )
    
    print("\n[7/7] Cleaning up temporary assets...")
    for seg in segments_data:
        try: os.remove(seg.get("subtitle_path", ""))
        except: pass
        try: os.remove(seg.get("video_path", ""))
        except: pass
    for f in [full_audio_path, final_audio_path, hook_path, title_path, outro_path, watermark_path]:
        try: os.remove(f)
        except: pass
    
    print("\n--- Pipeline Complete! ---")
    print(f"Final Video: {final_output_path}")

if __name__ == "__main__":
    main()
