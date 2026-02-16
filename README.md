# AI Reels Bot

Automatically generates short educational reels with text overlays by:
1. **AI generates the script** – Given a topic, creates SEGMENT/TEXT/DURATION format
2. **Scout** – Searches Pexels for matching stock footage
3. **Director** – Stitches clips together with MoviePy/FFmpeg
4. **Polish** – Adds educational text overlay (and optional TTS voiceover)

## Tech Stack

- **Python 3.12+**
- **MoviePy** – video editing
- **Pexels API** – stock footage
- **OpenAI** – script generation (GPT) + TTS voiceover

## Setup

### 1. Install FFmpeg (required for MoviePy)

```bash
brew install ffmpeg
```

### 2. Create virtual environment

```bash
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API keys

```bash
cp .env.example .env
# Edit .env and add your Pexels + OpenAI API keys
```

### 5. Verify setup

```bash
python check_setup.py
```

## Project Structure

```
├── scripts/         # Scripts (AI-generated or manual)
├── clips/           # Downloaded Pexels footage
├── output/          # Final rendered videos
├── src/             # Source code
│   ├── script_writer.py  # AI script generation
│   ├── scout.py          # Pexels search + download
│   ├── director.py       # Assemble clips into draft video
│   └── ...               # Text overlay, optional TTS
└── check_setup.py       # Environment validation
```

## Pipeline

### 1. Script Writer (AI)

Generate a script from a topic:

```bash
python -m src.script_writer "benefits of meditation"
# Options: -n 5 (segments), -d 30 (total seconds), -o scripts/my_topic.txt
```

### 2. Scout

Fetch Pexels footage for a script (saves to `clips/<script_stem>/`):

```bash
python -m src.scout scripts/sample.txt
# Or: python -m src.scout path/to/your_script.txt -o clips/custom/
```

### 3. Director

Assemble clips into a draft video:

```bash
python -m src.director scripts/sample.txt
# Output: output/<script_stem>_draft.mp4
```

## Script Format

```
SEGMENT: <visual search query for stock footage>
TEXT: <educational text to overlay on screen>
DURATION: <seconds>
---
```

## Roadmap

- [x] Phase 1: Project setup
- [x] Phase 0: AI Script Writer
- [x] Phase 2: Scout (Pexels search + download)
- [x] Phase 3: Director (assemble clips)
- [ ] Phase 4: Polish (text overlay + optional TTS)
