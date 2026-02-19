"""
ElevenLabs Music Client: Generate songs from lyrics via ElevenLabs Music API.
Produces female voice, clear educational pop style with enunciated words.
"""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/music"

# Style prompt for female voice, clear educational pop
POSITIVE_GLOBAL_STYLES = [
    "Female lead vocal",
    "Educational pop",
    "Clear enunciation",
    "Upbeat and engaging",
]
NEGATIVE_GLOBAL_STYLES: list[str] = []
MAX_LINE_CHARS = 200
MIN_SECTION_MS = 3000
MAX_SECTION_MS = 120000


def _split_lyrics_to_lines(lyrics: str) -> list[str]:
    """Split lyrics into lines, each max 200 chars."""
    lines: list[str] = []
    # First split by newlines and commas
    for part in lyrics.replace(",", "\n").split("\n"):
        part = part.strip()
        if not part:
            continue
        # Further split if any part exceeds max
        while len(part) > MAX_LINE_CHARS:
            # Break at word boundary
            chunk = part[:MAX_LINE_CHARS]
            last_space = chunk.rfind(" ")
            if last_space > MAX_LINE_CHARS // 2:
                lines.append(chunk[: last_space + 1].strip())
                part = part[last_space + 1 :].strip()
            else:
                lines.append(chunk.strip())
                part = part[MAX_LINE_CHARS:].strip()
        if part:
            lines.append(part)
    return lines if lines else [lyrics[:MAX_LINE_CHARS] or " "]


def _build_composition_plan(segments: list) -> dict:
    """Build ElevenLabs composition_plan from script segments."""
    sections = []
    for i, seg in enumerate(segments):
        lyrics = seg.text or seg.query or ""
        lines = _split_lyrics_to_lines(lyrics)
        duration_ms = int(seg.duration_seconds * 1000)
        duration_ms = max(MIN_SECTION_MS, min(MAX_SECTION_MS, duration_ms))
        section_name = f"Verse {i + 1}" if i < 26 else f"Section {i + 1}"
        sections.append(
            {
                "section_name": section_name,
                "positive_local_styles": ["Clear vocals", "Melodic"],
                "negative_local_styles": [],
                "duration_ms": duration_ms,
                "lines": lines,
            }
        )
    return {
        "positive_global_styles": POSITIVE_GLOBAL_STYLES,
        "negative_global_styles": NEGATIVE_GLOBAL_STYLES,
        "sections": sections,
    }


def generate_song(
    segments: list,
    title: str,
    output_path: Path | None = None,
) -> tuple[Path, float]:
    """
    Generate a song via ElevenLabs Music API using composition plan.
    Returns (path to saved MP3, total duration in seconds).
    """
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY not set in .env. Get your key from elevenlabs.io."
        )

    if not segments:
        raise ValueError("No segments provided for song generation.")

    out = output_path or (
        OUTPUT_DIR / f"{title.replace(' ', '_')[:40]}_elevenlabs.mp3"
    )
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    composition_plan = _build_composition_plan(segments)
    total_duration = sum(
        s["duration_ms"] for s in composition_plan["sections"]
    ) / 1000.0

    url = f"{ELEVENLABS_API_URL}?output_format=mp3_44100_128"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {"composition_plan": composition_plan, "model_id": "music_v1"}

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=180)
        r.raise_for_status()
    except requests.RequestException as e:
        msg = str(e)
        if hasattr(e, "response") and e.response is not None:
            try:
                body = e.response.json()
                msg = body.get("detail", {}).get("message", msg)
            except Exception:
                pass
        raise RuntimeError(f"ElevenLabs music generation failed: {msg}") from e

    with open(out, "wb") as f:
        f.write(r.content)

    return (out, total_duration)
