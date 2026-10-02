import os
import math
import numpy as np
from PIL import Image
from pydub import AudioSegment
from moviepy.editor import ImageClip, VideoClip
from .config import VIDEO_WIDTH, VIDEO_HEIGHT

def remove_white_background(img_array, tolerance=240):
    """
    Converts a solid white/light background to transparent.
    """
    img = Image.fromarray(img_array).convert("RGBA")
    data = np.array(img)
    
    # White background condition: R, G, B all > tolerance
    red, green, blue, alpha = data.T
    white_areas = (red >= tolerance) & (green >= tolerance) & (blue >= tolerance)
    data[..., 3][white_areas.T] = 0 # Set alpha to 0 for white areas
    
    return data

def generate_avatar_clip(audio_path, closed_img_path, open_img_path, duration, threshold_db=-35):
    """
    Creates an audio-reactive PNGTuber style talking avatar.
    
    Args:
        audio_path: Path to the voiceover mp3/wav
        closed_img_path: Path to the avatar image when mouth is closed
        open_img_path: Path to the avatar image when mouth is open
        duration: Total duration of the clip to generate
        threshold_db: Volume threshold to trigger "open mouth" state
        
    Returns:
        A MoviePy VideoClip with the animated avatar (transparent background).
    """
    if not os.path.exists(closed_img_path) or not os.path.exists(open_img_path):
        print("Avatar images not found. Skipping avatar.")
        return None
        
    print("Analyzing audio for lip-sync avatar...")
    
    # 1. Load audio and chunk it to calculate volume over time
    try:
        audio = AudioSegment.from_file(audio_path)
    except Exception as e:
        print(f"Failed to load audio for avatar: {e}")
        return None
        
    chunk_ms = 33 # roughly 30 fps
    
    # Pre-calculate volume for every chunk to make frame generation extremely fast
    volumes = []
    for i in range(0, len(audio), chunk_ms):
        chunk = audio[i:i+chunk_ms]
        volumes.append(chunk.dBFS)
        
    def get_volume_at_time(t):
        idx = int((t * 1000) / chunk_ms)
        if idx >= len(volumes):
            return -100 # silence
        return volumes[idx]

    # 2. Load and process images
    # We load via MoviePy but immediately convert white to transparent
    base_closed = ImageClip(closed_img_path)
    base_open = ImageClip(open_img_path)
    
    # Resize avatar to be appropriate size for corner (e.g., 400x400)
    target_height = int(VIDEO_HEIGHT * 0.35)
    base_closed = base_closed.resize(height=target_height)
    base_open = base_open.resize(height=target_height)
    
    # Convert white bg to transparent
    frame_closed = remove_white_background(base_closed.get_frame(0))
    frame_open = remove_white_background(base_open.get_frame(0))
    
    width = base_closed.w
    height = base_closed.h
    
    # Position in bottom right
    padding = 50
    pos_x = VIDEO_WIDTH - width - padding
    pos_y = VIDEO_HEIGHT - height - padding

    # 3. Create the generator function for the VideoClip
    def make_frame(t):
        vol = get_volume_at_time(t)
        is_speaking = vol > threshold_db
        frame = frame_open if is_speaking else frame_closed
        return frame[:, :, :3]  # Return only RGB channels (H, W, 3)
        
    def make_mask(t):
        vol = get_volume_at_time(t)
        is_speaking = vol > threshold_db
        frame = frame_open if is_speaking else frame_closed
        # Return Alpha channel as mask (values 0.0 to 1.0)
        return frame[:, :, 3] / 255.0

    # Create the raw clip and its mask
    avatar_clip = VideoClip(make_frame, duration=duration)
    mask_clip = VideoClip(make_mask, duration=duration, ismask=True)
    avatar_clip = avatar_clip.set_mask(mask_clip)
    
    # Set the dynamic position with the bounce
    def get_position(t):
        vol = get_volume_at_time(t)
        is_speaking = vol > threshold_db
        bounce_offset = 0
        if is_speaking:
            bounce_offset = int(abs(math.sin(t * 15)) * 15)
        return (pos_x, pos_y - bounce_offset)
        
    avatar_clip = avatar_clip.set_position(get_position)
    
    return avatar_clip

if __name__ == "__main__":
    # Test
    pass
