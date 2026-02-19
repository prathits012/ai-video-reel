"""
Music: Pick from local assets/music/ folder.
Pixabay API does NOT support audio (only images/videos); use pre-downloaded tracks.
"""

import random
from pathlib import Path

MUSIC_DIR = Path(__file__).resolve().parent.parent / "assets" / "music"

# Mood → preferred filename (without ext)
MOOD_FILES = {
    "uplifting": "uplifting",
    "calm": "calm",
    "energetic": "uplifting",  # fallback
    "motivational": "motivational",
    "meditation": "meditation",
    "focus": "neutral",
    "default": "neutral",
}

AUDIO_EXTS = (".mp3", ".m4a", ".ogg", ".wav")


def _list_tracks() -> list[Path]:
    """Return all audio files in MUSIC_DIR."""
    if not MUSIC_DIR.exists():
        return []
    return [p for p in MUSIC_DIR.iterdir() if p.suffix.lower() in AUDIO_EXTS]


def pick_local_music(mood: str = "default") -> Path | None:
    """
    Pick a music track from assets/music/.
    Prefers mood-named file (e.g. calm.mp3), else picks any available track.

    Returns:
        Path to track, or None if no tracks in folder.
    """
    tracks = _list_tracks()
    if not tracks:
        return None

    preferred = MOOD_FILES.get(mood, "neutral")
    for t in tracks:
        if t.stem.lower() == preferred:
            return t

    return random.choice(tracks)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Pick background music from assets/music/")
    parser.add_argument("-m", "--mood", default="default", choices=list(MOOD_FILES.keys()))
    args = parser.parse_args()

    path = pick_local_music(mood=args.mood)
    if path:
        print(path)
    else:
        print("No tracks in assets/music/. Add .mp3 files (calm, uplifting, etc.)", file=__import__("sys").stderr)
        exit(1)


if __name__ == "__main__":
    main()
