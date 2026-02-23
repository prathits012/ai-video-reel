"""
Scout: Search Pexels for stock footage and download 1080p clips.
Parses script files and fetches matching videos for each segment.

Candidate scoring: fetches 10 candidates per segment and picks the best one
using a weighted score of resolution, duration fit, and visual authenticity
(rated by GPT-4o vision on Pexels thumbnails — no video download required for scoring).
"""

import base64
import json
import re
from pathlib import Path
from dataclasses import dataclass

import requests
from dotenv import load_dotenv
import os

load_dotenv()

PEXELS_API_URL = "https://api.pexels.com/videos/search"
CLIPS_DIR = Path(__file__).resolve().parent.parent / "clips"

# Scoring weights (must sum to 1.0)
_W_RESOLUTION = 0.30
_W_DURATION = 0.30
_W_AUTHENTICITY = 0.40

# Reference resolution for scoring (1080p)
_REF_PIXELS = 1920 * 1080


@dataclass
class Segment:
    """A single script segment with search query, overlay text, and target duration."""
    query: str
    duration_seconds: int
    text: str = ""  # Educational text overlay (optional, from TEXT: field)


# ---------------------------------------------------------------------------
# Candidate scoring
# ---------------------------------------------------------------------------

def _score_resolution(video: dict) -> float:
    """0–1 score based on the best available video file resolution."""
    best_pixels = 0
    for f in video.get("video_files", []):
        w = f.get("width") or 0
        h = f.get("height") or 0
        best_pixels = max(best_pixels, w * h)
    return min(1.0, best_pixels / _REF_PIXELS)


def _score_duration(video: dict, segment_duration: int) -> float:
    """
    0–1 score for duration fitness.
    Prefers clips that are at least 2x the segment duration (gives Director headroom).
    Clips shorter than the segment still get partial credit scaled by how close they are.
    """
    clip_dur = video.get("duration") or 0
    target = segment_duration * 2
    if clip_dur >= target:
        return 1.0
    if clip_dur <= 0:
        return 0.0
    return clip_dur / target


def _score_authenticity_batch(videos: list[dict], openai_key: str) -> list[float]:
    """
    Rate how 'documentary/real' each video looks using GPT-4o vision on Pexels thumbnails.
    Sends all thumbnails in a single API call for efficiency.
    Returns a list of 0–1 scores (one per video).
    Falls back to 0.5 for any video whose thumbnail cannot be fetched.
    """
    from openai import OpenAI

    client = OpenAI(api_key=openai_key)
    n = len(videos)
    if n == 0:
        return []

    # Build content: text prompt + one image per thumbnail
    content: list[dict] = [
        {
            "type": "text",
            "text": (
                f"You will see {n} video thumbnails numbered 1 to {n}. "
                "For each thumbnail rate it from 1 to 10 on how authentic, cinematic, and "
                "documentary it looks — where 10 = real-world footage (natural lighting, "
                "genuine motion, feels like a news clip or nature documentary) and 1 = "
                "obvious generic stock clip (perfectly staged, plastic look, looping motion, "
                "overly corporate). "
                f"Reply ONLY with a JSON array of {n} integers, e.g. [7,3,8,...]. No other text."
            ),
        }
    ]

    fallback_indices: list[int] = []
    for idx, video in enumerate(videos):
        thumb_url = video.get("image", "")
        if not thumb_url:
            fallback_indices.append(idx)
            # Insert a placeholder so indices stay aligned
            content.append({"type": "text", "text": f"[Thumbnail {idx + 1}: unavailable]"})
            continue
        try:
            resp = requests.get(thumb_url, timeout=10)
            resp.raise_for_status()
            b64 = base64.b64encode(resp.content).decode()
            mime = resp.headers.get("content-type", "image/jpeg").split(";")[0]
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "low"},
            })
        except Exception:
            fallback_indices.append(idx)
            content.append({"type": "text", "text": f"[Thumbnail {idx + 1}: unavailable]"})

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            max_tokens=64,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if GPT wraps the response
        raw = re.sub(r"^```[a-z]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        # Extract the JSON array portion in case there is surrounding text
        array_match = re.search(r"\[[\d,\s]+\]", raw)
        if array_match:
            raw = array_match.group(0)
        scores_raw = json.loads(raw)
        scores = [max(1, min(10, int(s))) for s in scores_raw[:n]]
        # Pad if GPT returned fewer items than expected
        while len(scores) < n:
            scores.append(5)
    except Exception as e:
        print(f"  [scout] authenticity scoring failed ({e}), using neutral scores")
        scores = [5] * n

    # Normalize to 0–1
    return [s / 10.0 for s in scores]


def score_candidates(
    videos: list[dict],
    segment_duration: int,
    openai_key: str | None = None,
) -> dict:
    """
    Score a list of Pexels video candidates and return the best one.
    Scoring: resolution (30%) + duration fit (30%) + authenticity (40%).
    If openai_key is absent, authenticity is skipped and weights rebalanced (50/50).
    """
    if not videos:
        raise ValueError("No candidates to score")

    res_scores = [_score_resolution(v) for v in videos]
    dur_scores = [_score_duration(v, segment_duration) for v in videos]

    if openai_key:
        auth_scores = _score_authenticity_batch(videos, openai_key)
        w_res, w_dur, w_auth = _W_RESOLUTION, _W_DURATION, _W_AUTHENTICITY
    else:
        auth_scores = [0.5] * len(videos)
        w_res, w_dur, w_auth = 0.5, 0.5, 0.0

    combined = [
        w_res * r + w_dur * d + w_auth * a
        for r, d, a in zip(res_scores, dur_scores, auth_scores)
    ]

    best_idx = combined.index(max(combined))

    # Readable summary for the terminal
    print(f"  [scout] scored {len(videos)} candidates — picking #{best_idx + 1} "
          f"(res={res_scores[best_idx]:.2f} dur={dur_scores[best_idx]:.2f} "
          f"auth={auth_scores[best_idx]:.2f} total={combined[best_idx]:.2f})")

    return videos[best_idx]


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
        lines = block.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if stripped.upper().startswith("SEGMENT:"):
                query = stripped.split(":", 1)[1].strip()
            elif stripped.upper().startswith("TEXT:"):
                overlay_text = stripped.split(":", 1)[1].strip().strip('"\'')
                i += 1
                # Multi-line: append lines until next keyword
                while i < len(lines) and not re.match(
                    r"^\s*(SEGMENT|TEXT|LYRICS|DURATION)\s*:", lines[i], re.I
                ):
                    overlay_text += " " + lines[i].strip()
                    i += 1
                overlay_text = overlay_text.strip()
                continue
            elif stripped.upper().startswith("LYRICS:"):
                overlay_text = stripped.split(":", 1)[1].strip().strip('"\'')
                i += 1
                while i < len(lines) and not re.match(
                    r"^\s*(SEGMENT|TEXT|LYRICS|DURATION)\s*:", lines[i], re.I
                ):
                    overlay_text += " " + lines[i].strip()
                    i += 1
                overlay_text = overlay_text.strip()
                continue
            elif stripped.upper().startswith("DURATION:"):
                raw = stripped.split(":", 1)[1].strip()
                match = re.search(r"\d+", raw)
                duration = int(match.group()) if match else 5
            i += 1
        if query:
            segments.append(Segment(query=query, duration_seconds=duration, text=overlay_text))

    return segments


def search_pexels(
    query: str, api_key: str, per_page: int = 10, min_duration: int | None = None
) -> dict:
    """Search Pexels video API. Returns JSON response."""
    params = {"query": query, "per_page": per_page}
    if min_duration:
        params["min_duration"] = min_duration
    resp = requests.get(
        PEXELS_API_URL,
        headers={"Authorization": api_key},
        params=params,
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


def scout(
    script_path: Path,
    output_dir: Path | None = None,
    single_clip: bool = False,
    min_duration: int | None = None,
) -> list[tuple[Segment, Path]]:
    """
    Main Scout workflow:
    1. Parse script into segments
    2. Search Pexels for 10 candidates per segment
    3. Score each candidate (resolution + duration fit + GPT-4o authenticity on thumbnail)
    4. Download the winner to clips/

    Returns list of (Segment, local_file_path) for use by the Director.
    """
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        raise ValueError("PEXELS_API_KEY not set in .env")

    openai_key = os.getenv("OPENAI_API_KEY") or None

    out = output_dir or (CLIPS_DIR / script_path.stem)
    out.mkdir(parents=True, exist_ok=True)

    segments = parse_script(script_path)
    results: list[tuple[Segment, Path]] = []

    if single_clip:
        total_dur = sum(s.duration_seconds for s in segments)
        min_dur = min_duration if min_duration is not None else max(30, total_dur)
        query = segments[0].query if segments else "ambient background"
        data = search_pexels(query, api_key, per_page=10, min_duration=min_dur)
        videos = data.get("videos", [])
        if not videos:
            data = search_pexels(query, api_key, per_page=10)
            videos = data.get("videos", [])
        if not videos:
            raise RuntimeError(f"No Pexels results for query: {query}")
        best = score_candidates(videos, total_dur, openai_key=openai_key)
        video_files = best.get("video_files", [])
        url = pick_best_video_file(video_files)
        if not url:
            raise RuntimeError(f"No downloadable file for query: {query}")
        dest = out / "segment_00_single.mp4"
        download_video(url, dest)
        for seg in segments:
            results.append((seg, dest))
        return results

    for i, seg in enumerate(segments):
        data = search_pexels(seg.query, api_key, per_page=10)
        videos = data.get("videos", [])
        if not videos:
            raise RuntimeError(f"No Pexels results for query: {seg.query}")

        best = score_candidates(videos, seg.duration_seconds, openai_key=openai_key)
        video_files = best.get("video_files", [])
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
    parser.add_argument("--single-clip", action="store_true", help="Fetch one long clip (30+ sec) for entire video")
    args = parser.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"Error: script not found: {script_path}")
        return

    output_dir = Path(args.output) if args.output else None
    results = scout(script_path, output_dir=output_dir, single_clip=args.single_clip)

    print(f"Scout complete. Downloaded {len(results)} clips:")
    for seg, path in results:
        print(f"  {seg.query} -> {path.name}")


if __name__ == "__main__":
    main()
