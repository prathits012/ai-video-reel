# AI Reels Bot

Automatically generates short educational reels with text overlays. Two modes:

**Standard mode** – multi-segment script with stock footage and optional voiceover:
1. **AI generates the script** – Given a topic, creates SEGMENT/TEXT/DURATION format
2. **Scout** – Searches Pexels for matching stock footage
3. **Director** – Stitches clips together with MoviePy/FFmpeg
4. **Polish** – Adds educational text overlay (and optional TTS voiceover)

**Hamilton mode** – single-clip music video with ElevenLabs AI-generated song:
1. **AI generates a lyrical script** – SEGMENT/LYRICS/DURATION format, one verse per segment
2. **ElevenLabs Music API** – generates a full song (female voice, educational pop style)
3. **Scout** – fetches one long Pexels clip
4. **Director** – trims clip to song duration
5. **Polish** – lays the ElevenLabs track over the video; captions advance per segment
6. **Safety check** – automatic content safety report saved alongside the video

## Tech Stack

- **Python 3.12+**
- **MoviePy** – video editing
- **Pexels API** – stock footage
- **OpenAI** – script generation (GPT) + optional TTS voiceover
- **ElevenLabs** – AI music generation (Hamilton mode)

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
# Edit .env and add your API keys
```

Required keys in `.env`:

| Key | Required for |
|-----|-------------|
| `PEXELS_API_KEY` | All modes (stock footage) |
| `OPENAI_API_KEY` | Script generation + optional TTS voiceover |
| `ELEVENLABS_API_KEY` | Hamilton mode (AI music generation) |

### 5. Verify setup

```bash
python check_setup.py
```

## Project Structure

```
├── scripts/              # Scripts (AI-generated or manual)
├── clips/                # Downloaded Pexels footage
├── output/               # Final rendered videos + rating/safety JSON
├── src/                  # Source code
│   ├── script_writer.py      # AI script generation (standard + lyrical/Hamilton)
│   ├── scout.py              # Pexels search + download
│   ├── director.py           # Assemble clips into draft video
│   ├── polish.py             # Text overlay (tight per-line captions) + audio
│   ├── elevenlabs_client.py  # ElevenLabs Music API (Hamilton mode)
│   ├── rate.py               # AI quality rating – multi-frame, 5 criteria
│   ├── safety_rate.py        # AI content safety check – 6 criteria, auto-runs
│   ├── iterate.py            # Polish → rate → safety loop until pass
│   └── music_fetcher.py      # Pick local royalty-free music
├── assets/music/         # Local music tracks (used with -m auto)
└── check_setup.py        # Environment validation
```

## One-command pipeline

### Standard mode

Generate a reel from a topic (or use an existing script):

```bash
python run.py "benefits of meditation"
# From topic: generates script → scout → director → polish

python run.py scripts/benefits_of_morning_routine.txt
# From script: scout → director → polish

# Song-like with voiceover + music:
python run.py "benefits of meditation" --lyrical --voiceover -m path/to/music.mp3

# Auto-fetch music from Pixabay (matches topic, min duration):
python run.py "benefits of meditation" --lyrical --voiceover -m auto

# With AI rating loop (polish until pass):
python run.py "benefits of meditation" --iterate
```

Options: `--lyrical`, `--voiceover`, `-m/--music` (path or `auto`), `--iterate`, `--single-clip`, `-n` segments, `-d` duration

### Hamilton mode (ElevenLabs AI music)

Generates a full song from your topic using ElevenLabs Music API — female voice, clear educational pop style — over a single Pexels clip. Captions advance per verse, timed to each segment's duration. A content safety check runs automatically after every video.

```bash
# From topic (auto-generates lyrical script + song):
python run.py "how electricity works" --hamilton

# From an existing lyrical script:
python run.py scripts/how_refrigerators_work_lyrical.txt --hamilton
```

Requires `ELEVENLABS_API_KEY` in `.env`. Each run produces:
- `output/<topic>_final.mp4` – the finished reel
- `output/<topic>_safety.json` – content safety report

---

## Pipeline (step-by-step)

### 1. Script Writer (AI)

Generate a script from a topic:

```bash
python -m src.script_writer "benefits of meditation"
# Options: -n 5 (segments), -d 30 (total seconds), -o scripts/my_topic.txt

# Song-like reels (rhymed lyrics, verse/chorus structure):
python -m src.script_writer "benefits of meditation" --lyrical
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

### 4. Polish

Add text overlay, optional TTS voiceover, and optional background music:

```bash
python -m src.polish scripts/sample.txt
# Output: output/<script_stem>_final.mp4

# With voiceover (TTS reads lyrics):
python -m src.polish scripts/sample.txt --voiceover

# Song-like: voiceover + background music (music at 25% volume):
python -m src.polish scripts/sample.txt --voiceover -m path/to/music.mp3
```

### 5. Rate (AI quality check)

Samples multiple frames per segment and rates on 5 criteria (text readability, visual quality, footage relevance, temporal consistency, production quality). Saves a JSON report:

```bash
python -m src.rate output/video_final.mp4 scripts/script.txt
# Options: --voiceover, --music, --frames-per-segment 3
# Output: output/<video_stem>_rating.json
```

### 6. Safety check (AI content safety)

Runs OpenAI Moderation API on all text plus GPT-4o vision on sampled frames. Evaluates 6 criteria: text safety, visual safety, topic safety, factual plausibility, audience suitability, platform compliance. Runs automatically after every pipeline; can also be run standalone:

```bash
python -m src.safety_rate output/video_final.mp4 scripts/script.txt
# Output: output/<video_stem>_safety.json
# Verdict: approved / needs_review / rejected
```

### 7. Iterate (polish → rate loop)

Run polish → quality rate → safety check until pass or max iterations:

```bash
python -m src.iterate scripts/benefits_of_morning_routine.txt
# Options: -n 3 (max iterations), --min-score 8, --voiceover, -m path/to/music.mp3
```

## Script Format

```
SEGMENT: <visual search query for stock footage>
TEXT: <educational text to overlay on screen>
DURATION: <seconds>
---
```

For song-like reels, use `LYRICS:` instead of `TEXT:` (rhymed, metered lines).

### Music (local)

Place royalty-free `.mp3` files in `assets/music/` (e.g. calm.mp3, uplifting.mp3). Use `-m auto` to pick one, or `-m path/to/track.mp3` for a specific file. Pixabay API does not support audio; download manually from [Pexels Music](https://www.pexels.com/music/) or [Pixabay Music](https://pixabay.com/music/).

## Caption style

Captions use a **tight black background per line** — the dark box shrinks to fit each line of text rather than spanning the full video width. In Hamilton mode, captions advance verse-by-verse, each displayed for its script-specified duration.

## Roadmap

- [x] Phase 0: AI Script Writer
- [x] Phase 1: Project setup
- [x] Phase 2: Scout (Pexels search + download)
- [x] Phase 3: Director (assemble clips)
- [x] Phase 4: Polish (tight per-line captions + optional TTS)
- [x] Phase 5: Hamilton mode – ElevenLabs AI music (female voice, educational pop)
- [x] Phase 6: AI quality rater – multi-frame, 5 criteria
- [x] Phase 7: Content safety rater – 6 criteria, runs automatically
