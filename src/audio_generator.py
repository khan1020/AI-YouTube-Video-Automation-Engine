import asyncio
import os
import edge_tts
from .config import VOICE_MAP

async def _generate_audio_async(text, output_file, language="English"):
    # Edge TTS can sometimes fail on empty text
    if not text or not text.strip():
        text = " " # Space to avoid crash
        
    voice = VOICE_MAP.get(language.lower(), VOICE_MAP["default"])
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

def generate_audio(text, output_file, language="English", retries=3):
    """
    Synchronous wrapper to generate audio using edge-tts.
    Includes retry logic to prevent corrupted/empty mp3 files.
    """
    print(f"Generating audio for segment to {output_file}...")
    for attempt in range(retries):
        try:
            asyncio.run(_generate_audio_async(text, output_file, language))
            # Check if file was created and is not empty
            if os.path.exists(output_file) and os.path.getsize(output_file) > 100:
                return # Success
            print(f"  Attempt {attempt+1} failed: File empty or too small. Retrying...")
        except Exception as e:
            print(f"  Attempt {attempt+1} failed with error: {e}. Retrying...")
            
        # Optional short wait before retry
        import time
        time.sleep(1)
        
    raise IOError(f"Failed to generate valid audio file {output_file} after {retries} retries.")

if __name__ == "__main__":
    generate_audio("Hello, this is a test of the text to speech system.", "test.mp3")
