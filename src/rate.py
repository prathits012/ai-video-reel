"""
Rate: AI-powered video quality assessment.
Extracts multiple frames per segment and sends to vision model for structured feedback.
"""

import base64
import json
import os
import tempfile
from pathlib import Path

from moviepy import VideoFileClip
from openai import OpenAI
from dotenv import load_dotenv

from src.scout import parse_script

load_dotenv()

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

# Sampling config: up to FRAMES_PER_SEGMENT frames per segment, total capped at MAX_FRAMES
FRAMES_PER_SEGMENT = 3
MAX_FRAMES = 18


def extract_frames(
    video_path: Path,
    script_path: Path,
    frames_dir: Path,
    frames_per_segment: int = FRAMES_PER_SEGMENT,
    max_frames: int = MAX_FRAMES,
) -> list[tuple[int, float, Path]]:
    """
    Extract multiple evenly-spaced frames per segment.
    Returns list of (segment_index, timestamp, path) tuples.
    Caps total at max_frames to stay within vision model limits.
    """
    from PIL import Image

    segments = parse_script(script_path)
    clip = VideoFileClip(str(video_path))
    results: list[tuple[int, float, Path]] = []
    t = 0.0

    # Determine how many frames to sample per segment given the cap
    total_segs = len(segments)
    if total_segs * frames_per_segment > max_frames:
        frames_per_segment = max(1, max_frames // total_segs)

    for i, seg in enumerate(segments):
        seg_dur = min(seg.duration_seconds, clip.duration - t)
        if seg_dur <= 0:
            break
        # Sample evenly-spaced timestamps within the segment
        if frames_per_segment == 1:
            timestamps = [t + seg_dur / 2]
        else:
            # Start slightly inside, end slightly inside (avoid black frames at cuts)
            margin = seg_dur * 0.1
            step = (seg_dur - 2 * margin) / (frames_per_segment - 1)
            timestamps = [t + margin + step * j for j in range(frames_per_segment)]

        for j, ts in enumerate(timestamps):
            ts = min(ts, clip.duration - 0.05)
            frame = clip.get_frame(ts)
            path = frames_dir / f"seg{i:02d}_frame{j}.png"
            Image.fromarray(frame).save(path)
            results.append((i, ts, path))

        t += seg.duration_seconds

    clip.close()
    return results


def rate_video(
    video_path: Path,
    script_path: Path,
    output_path: Path | None = None,
    has_voiceover: bool = False,
    has_music: bool = False,
) -> dict:
    """
    Rate the video using AI vision. Samples multiple frames per segment for more
    thorough evaluation of text overlays, footage quality, and temporal consistency.
    Returns structured dict with scores and feedback.
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set in .env")

    segments = parse_script(script_path)
    script_text = script_path.read_text()

    with tempfile.TemporaryDirectory() as tmpdir:
        frames_dir = Path(tmpdir)
        frame_tuples = extract_frames(video_path, script_path, frames_dir)

        # Build a frame index string so the model knows which frames belong to which segment
        frame_index_lines = []
        for idx, (seg_i, ts, _) in enumerate(frame_tuples):
            seg = segments[seg_i]
            label = seg.text[:60].replace("\n", " ") if seg.text else seg.query[:60]
            frame_index_lines.append(
                f"  Frame {idx + 1}: segment {seg_i + 1} at {ts:.1f}s — \"{label}\""
            )
        frame_index = "\n".join(frame_index_lines)

        audio_context = []
        if has_voiceover:
            audio_context.append("voiceover (TTS reads the caption text aloud)")
        if has_music:
            audio_context.append("background music")
        audio_desc = " and ".join(audio_context) if audio_context else "no audio"

        content: list[dict] = [
            {
                "type": "text",
                "text": f"""You are a professional video editor rating a short vertical educational reel (1080×1920).

SCRIPT:
{script_text}

AUDIO: This video has {audio_desc}.

You will see {len(frame_tuples)} frames sampled from {len(segments)} segments ({FRAMES_PER_SEGMENT} frames per segment where possible):
{frame_index}

Multiple frames per segment let you evaluate temporal consistency within each segment (e.g., clip changes mid-segment, flicker, inconsistent text).

--- EVALUATION INSTRUCTIONS ---

STEP 1 — CRITICAL TEXT CHECK (check every frame):
  • Scan left and right edges of every frame for clipped/cut-off text characters.
  • If ANY text is cut off at the edge → add to issues, set pass=false.
  • Check text is readable against the background (contrast, font size).

STEP 2 — VISUAL QUALITY (check every frame):
  • Flag gray/washed-out or overexposed clips.
  • Flag letterboxing or film-reel black bars.
  • Flag abrupt, jarring clip changes within a segment (compare frames of same segment).

STEP 3 — FOOTAGE RELEVANCE:
  • Does each segment's footage match the script topic for that segment?
  • Be specific: "segment 3 shows generic office but script describes ocean waves".

STEP 4 — TEMPORAL CONSISTENCY:
  • If multiple frames from the same segment look very different (different scene), flag it.
  • Flag if text disappears or changes unexpectedly within a segment.

STEP 5 — AUDIO SYNC (if voiceover or music present):
  • Estimate if caption length per segment is appropriate for the audio pacing.
  • Very long captions on short segments → likely rushed speech.
{"  • Music: note if footage energy seems to match or clash with an educational pop vibe." if has_music else ""}

--- SCORING CRITERIA ---
1. **text_readability** (1-10): Legible, fully visible, well-contrasted, not cut off.
2. **visual_quality** (1-10): Sharp, well-lit, correctly exposed, no technical artifacts.
3. **footage_relevance** (1-10): How well footage matches the script topic per segment.
4. **temporal_consistency** (1-10): Smooth within segments, no jarring changes.
5. **production_quality** (1-10): Overall polish — layout, pacing, no letterboxing/reel effects.
{"6. **audio_sync** (1-10): Caption length matches audio pacing; music suits the tone." if (has_voiceover or has_music) else ""}

Pass threshold: overall_score ≥ 7 AND no critical issues.

Respond with ONLY valid JSON (no markdown, no extra text):
{{
  "overall_score": <1-10>,
  "pass": <true if overall_score>=7 and no critical issues>,
  "scores": {{
    "text_readability": <1-10>,
    "visual_quality": <1-10>,
    "footage_relevance": <1-10>,
    "temporal_consistency": <1-10>,
    "production_quality": <1-10>{"," if has_voiceover or has_music else ""}
    {"\"audio_sync\": <1-10>" if (has_voiceover or has_music) else ""}
  }},
  "issues": ["specific problem e.g. 'segment 2 frame 2 shows gray washed-out clip'", "..."],
  "suggestions": ["actionable improvement e.g. 'replace segment 3 footage with closer match'", "..."]
}}""",
            }
        ]

        for _, _, path in frame_tuples:
            b64 = base64.standard_b64encode(path.read_bytes()).decode()
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "low"},
                }
            )

        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            max_tokens=1024,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        rating = json.loads(raw)

    out = output_path or (OUTPUT_DIR / f"{video_path.stem}_rating.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rating, indent=2))
    return rating


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Rate a video with AI vision")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("script", help="Path to script file")
    parser.add_argument("-o", "--output", help="Output JSON path")
    parser.add_argument("--voiceover", action="store_true", help="Video has voiceover; rate audio sync")
    parser.add_argument("--music", action="store_true", help="Video has background music; rate audio sync")
    parser.add_argument(
        "--frames-per-segment",
        type=int,
        default=FRAMES_PER_SEGMENT,
        help=f"Frames to sample per segment (default: {FRAMES_PER_SEGMENT})",
    )
    args = parser.parse_args()

    video_path = Path(args.video)
    script_path = Path(args.script)
    if not video_path.exists():
        print(f"Error: video not found: {video_path}")
        return
    if not script_path.exists():
        print(f"Error: script not found: {script_path}")
        return

    output_path = Path(args.output) if args.output else None
    rating = rate_video(
        video_path,
        script_path,
        output_path,
        has_voiceover=args.voiceover,
        has_music=args.music,
    )
    out = output_path or OUTPUT_DIR / f"{video_path.stem}_rating.json"

    print(f"Rating saved to: {out}")
    print(f"Overall: {rating['overall_score']}/10 | Pass: {rating['pass']}")
    if rating.get("issues"):
        print("Issues:", ", ".join(rating["issues"]))
    if rating.get("suggestions"):
        print("Suggestions:", ", ".join(rating["suggestions"]))


if __name__ == "__main__":
    main()
