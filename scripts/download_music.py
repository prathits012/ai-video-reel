#!/usr/bin/env python3
"""
Music setup: Ensure assets/music/ exists and show manual download instructions.
Pixabay API does NOT support audio (only images/videos) - use manual download.
"""

from pathlib import Path

MUSIC_DIR = Path(__file__).resolve().parent.parent / "assets" / "music"

INSTRUCTIONS = """
Pixabay's API does not support audio (403 Forbidden). Download music manually:

1. Go to https://www.pexels.com/music/ or https://pixabay.com/music/
2. Search and download 5 tracks (calm, uplifting, motivational, meditation, ambient)
3. Save them in: {dir}
4. Rename to: calm.mp3, uplifting.mp3, motivational.mp3, meditation.mp3, neutral.mp3

Then use: python run.py "your topic" --voiceover -m auto
"""

def main():
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    print(INSTRUCTIONS.format(dir=MUSIC_DIR))
    existing = list(MUSIC_DIR.glob("*.mp3")) + list(MUSIC_DIR.glob("*.m4a"))
    if existing:
        print(f"Already have {len(existing)} track(s):")
        for p in existing:
            print(f"  - {p.name}")

if __name__ == "__main__":
    main()
