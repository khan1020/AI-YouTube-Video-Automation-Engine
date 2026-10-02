import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# Video Settings — default to 1080p, overridden at runtime by set_resolution()
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 24

RESOLUTIONS = {
    "480p":  (854,  480),
    "720p":  (1280, 720),
    "1080p": (1920, 1080),
}

def set_resolution(label):
    """Set the global VIDEO_WIDTH and VIDEO_HEIGHT from a resolution label like '720p'."""
    global VIDEO_WIDTH, VIDEO_HEIGHT
    VIDEO_WIDTH, VIDEO_HEIGHT = RESOLUTIONS.get(label, (1920, 1080))

# Voice mapping for different languages
VOICE_MAP = {
    "english": "en-US-GuyNeural",
    "hindi": "hi-IN-MadhurNeural",
    "urdu": "ur-PK-AsadNeural",
    "roman urdu": "en-IN-PrabhatNeural", # Indian English voice reads Roman Urdu best
    "spanish": "es-ES-AlvaroNeural",
    "french": "fr-FR-HenriNeural",
    "default": "en-US-GuyNeural"
}
