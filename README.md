# 🎬 AI YouTube Automation Engine & Web Studio

An end-to-end automated AI video generation pipeline and Flask web interface. Give it a single topic or prompt, and the system automatically writes the script, generates realistic voiceovers, fetches matching HD stock video footage, adds typography/captions, mixes background music with audio ducking, and renders a complete YouTube-ready `.mp4` video.

---

## ✨ Features

* 🤖 **AI Script Generation:** Writes structured, scene-by-scene video scripts complete with YouTube titles, descriptions, and tags via OpenRouter / OpenAI LLMs.
* 🎙️ **Neural Voiceovers:** Uses Microsoft Edge Neural TTS (`edge-tts`) for ultra-realistic, natural voice narration in multiple languages.
* 🎥 **Stock Footage Sourcing:** Automatically queries the Pexels API in parallel to download high-definition stock video clips for every scene.
* 🎵 **Smart Audio Ducking & SFX:** Automatically lowers background music volume when the voiceover speaks, inserting contextual sound effects (whooshes, impacts, risers).
* 🎨 **AI Director & Mood Presets:** Maps script moods (*Dramatic*, *Epic*, *Calm*, *Intense*, *Informative*) to cinematic camera movements (Zoom Punch, Speed Ramp, Ken Burns effect).
* 📝 **Automated Typography & Overlays:** Bakes Hook Cards, Title Cards, Outro Cards, Watermarks, and Lower-Third key term overlays into the final video.
* 🌐 **Web Studio Dashboard:** Includes a Flask web interface (`web/app.py`) for triggering and monitoring video production from a browser.

---

## 🛠️ Prerequisites & Installation

### 1. Requirements
* **Python 3.10+**
* **FFmpeg** (Required by MoviePy for video rendering)

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

---

## 🔐 Configuration (`.env`)

Create a `.env` file in the root directory and add your API keys:

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
PEXELS_API_KEY=your_pexels_api_key_here
```

* **OpenRouter API Key:** Get one at [openrouter.ai](https://openrouter.ai/) (Used for script generation).
* **Pexels API Key:** Get a free key at [pexels.com/api](https://www.pexels.com/api/) (Used for stock footage).

---

## 🚀 How to Run

### Option 1: Command Line Interface (CLI)
Run `main.py` with your topic, desired duration (minutes), and language:

```bash
# Usage: python main.py "<Topic>" [duration_minutes] [language]
python main.py "10 Mind-Blowing Facts About Space" 2 "English"
```

The system will execute the 7-step pipeline:
1. Generate Script & YouTube Metadata
2. Download Sound Effects & Background Music
3. Synthesize Voiceover & Mix Audio Ducking
4. Create Graphics & Typography Overlays
5. Fetch Matching Video Clips from Pexels (Parallel Threads)
6. Assemble & Render Final `.mp4` Video
7. Save Output to `output_workspace/<topic_name>/final_video.mp4`

---

### Option 2: Web Studio Dashboard (UI)
Launch the Flask web application:

```bash
python web/app.py
```
Open your browser and navigate to `http://localhost:5000` to control the video generator visually.

---

## 📂 Project Architecture

```
Yotube Automation Project/
├── main.py                   # Main CLI entry point
├── requirements.txt          # Dependencies
├── .env.example              # Sample environment configuration
├── src/                      # Core AI Pipeline
│   ├── ai_director.py        # Mood to visual/audio preset mapper
│   ├── script_generator.py   # LLM prompt & script parser
│   ├── audio_generator.py    # Edge-TTS voice synthesis
│   ├── visuals_manager.py    # Pexels API downloader
│   ├── video_editor.py       # MoviePy video compilation engine
│   ├── avatar_engine.py      # Presenter/Avatar overlay rendering
│   ├── sound_design.py       # Audio ducking & SFX alignment
│   ├── typography.py         # Subtitles & lower-third graphics
│   ├── effects.py            # Color grading & video filters
│   ├── transitions.py        # Scene transitions
│   └── overlays.py           # Watermarks & title cards
└── web/                      # Web Interface
    ├── app.py                # Flask server
    ├── templates/index.html  # Web UI
    └── static/style.css      # Styling
```

---

## 📄 License
This project is open-source under the MIT License. Feel free to use and customize for your own faceless video automation channels!
