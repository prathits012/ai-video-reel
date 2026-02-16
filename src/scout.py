"""
Scout: Search Pexels for stock footage and download 1080p clips.
Parses script files and fetches matching videos for each segment.
"""

import re
from pathlib import Path
from dataclasses import dataclass

import requests
from dotenv import load_dotenv
import os

load_dotenv()

PEXELS_API_URL = "https://api.pexels.com/videos/search"
CLIPS_DIR = Path(__file__).resolve().parent.parent / "clips"


@dataclass
class Segment:
    """A single script segment with search query, overlay text, and target duration."""
    query: str
    duration_seconds: int
    text: str = ""  # Educational text overlay (optional, from TEXT: field)


def parse_script(script_path: Path) -> list[Segment]:
    """
    Parse a script file in SEGMENT/TEXT/DURATION format.
    TEXT is optional (for backward compatibility). Returns a list of Segment objects.
    """
    text = script_path.read_text()
    segments: list[Segment] = []
    blocks = text.strip().split("---")

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        query = ""
        overlay_text = ""
        duration = 5  # default
        for line in block.splitlines():
            line = line.strip()
            if line.upper().startswith("SEGMENT:"):
                query = line.split(":", 1)[1].strip()
            elif line.upper().startswith("TEXT:"):
                overlay_text = line.split(":", 1)[1].strip().strip('"\'')
            elif line.upper().startswith("DURATION:"):
                raw = line.split(":", 1)[1].strip()
                # Extract first number (handles "5", "5 seconds", "5s")
                match = re.search(r"\d+", raw)
                duration = int(match.group()) if match else 5
        if query:
            segments.append(Segment(query=query, duration_seconds=duration, text=overlay_text))

    return segments


def search_pexels(query: str, api_key: str, per_page: int = 5) -> dict:
    """Search Pexels video API. Returns JSON response."""
    resp = requests.get(
        PEXELS_API_URL,
        headers={"Authorization": api_key},
        params={"query": query, "per_page": per_page},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def pick_best_video_file(video_files: list[dict]) -> str | None:
    """
    Select the best quality video file, preferring 1080p (1920 width).
    Falls back to highest available resolution.
    """
    if not video_files:
        return None

    def score(f: dict) -> tuple[int, int]:
        width = f.get("width", 0) or 0
        height = f.get("height", 0) or 0
        # Prefer 1080p, then highest resolution
        is_1080 = 1 if width >= 1920 or height >= 1080 else 0
        return (is_1080, width * height)

    sorted_files = sorted(video_files, key=score, reverse=True)
    link = sorted_files[0].get("link")
    return link if link else None


def download_video(url: str, dest_path: Path) -> None:
    """Download video from URL to dest_path."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)


def scout(script_path: Path, output_dir: Path | None = None) -> list[tuple[Segment, Path]]:
    """
    Main Scout workflow:
    1. Parse script into segments
    2. Search Pexels for each segment
    3. Download best 1080p video to clips/

    Returns list of (Segment, local_file_path) for use by the Director.
    """
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        raise ValueError("PEXELS_API_KEY not set in .env")

    out = output_dir or (CLIPS_DIR / script_path.stem)
    out.mkdir(parents=True, exist_ok=True)

    segments = parse_script(script_path)
    results: list[tuple[Segment, Path]] = []

    for i, seg in enumerate(segments):
        data = search_pexels(seg.query, api_key)
        videos = data.get("videos", [])
        if not videos:
            raise RuntimeError(f"No Pexels results for query: {seg.query}")

        video_files = videos[0].get("video_files", [])
        url = pick_best_video_file(video_files)
        if not url:
            raise RuntimeError(f"No downloadable file for query: {seg.query}")

        safe_name = "".join(c if c.isalnum() or c in " -" else "_" for c in seg.query)[:50]
        dest = out / f"segment_{i:02d}_{safe_name.strip().replace(' ', '_')}.mp4"
        download_video(url, dest)
        results.append((seg, dest))

    return results


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Scout: Fetch Pexels footage for a script")
    parser.add_argument(
        "script",
        nargs="?",
        default="scripts/sample.txt",
        help="Path to script file (default: scripts/sample.txt)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory for clips (default: clips/<script_stem>/)",
    )
    args = parser.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"Error: script not found: {script_path}")
        return

    output_dir = Path(args.output) if args.output else None
    results = scout(script_path, output_dir)

    print(f"Scout complete. Downloaded {len(results)} clips:")
    for seg, path in results:
        print(f"  {seg.query} -> {path.name}")


if __name__ == "__main__":
    main()
