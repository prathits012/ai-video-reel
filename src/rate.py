"""
Rate: AI-powered video quality assessment.
Extracts frames, sends to vision model, returns structured rating for agent verification.
"""

import base64
import json
import tempfile
from pathlib import Path

from moviepy import VideoFileClip
from openai import OpenAI
from dotenv import load_dotenv

from src.scout import parse_script

load_dotenv()

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
TARGET_SIZE = (1080, 1920)  # vertical reel


def extract_frames(video_path: Path, script_path: Path, frames_dir: Path) -> list[Path]:
    """Extract one frame per segment (from middle of each segment). Returns frame paths."""
    segments = parse_script(script_path)
    clip = VideoFileClip(str(video_path))
    frame_paths = []
    t = 0.0

    for i, seg in enumerate(segments):
        mid = t + seg.duration_seconds / 2
        if mid >= clip.duration:
            mid = clip.duration - 0.1
        frame = clip.get_frame(mid)
        # Save as PNG (base64 for API)
        path = frames_dir / f"segment_{i:02d}.png"
        from PIL import Image
        import numpy as np
        Image.fromarray(frame).save(path)
        frame_paths.append(path)
        t += seg.duration_seconds

    clip.close()
    return frame_paths


def rate_video(
    video_path: Path,
    script_path: Path,
    output_path: Path | None = None,
    has_voiceover: bool = False,
) -> dict:
    """
    Rate the video using AI vision. Returns structured dict with scores and feedback.
    """
    client = OpenAI(api_key=__import__("os").getenv("OPENAI_API_KEY"))
    if not __import__("os").getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set in .env")

    segments = parse_script(script_path)
    with tempfile.TemporaryDirectory() as tmpdir:
        frames_dir = Path(tmpdir)
        frame_paths = extract_frames(video_path, script_path, frames_dir)

        # Build content for API: script context + images
        script_text = script_path.read_text()
        content = [
            {
                "type": "text",
                "text": f"""You are rating a short educational reel video. Here is the script:

{script_text}

You will see one frame from each segment (in order).

MANDATORY FIRST STEP - Text cutoff check: Look at EACH frame's overlay text. Scan the left and right edges. If ANY letter, character, or word is partially cut off or clipped at the frame edge, you MUST add "segment N has text cut off at left/right edge" to issues and set pass=false. This is a critical failure.

Then rate on these criteria:

1. **text_readability** (1-10): Clear, legible, fully visible? Score LOW (≤5) if text is cut off.
2. **visual_quality** (1-10): Sharp, well-lit, good colors? Watch for GRAY/WASHED OUT clips.
3. **footage_relevance** (1-10): Does footage match the segment topic?
4. **production_quality** (1-10): Technical issues including TEXT CUT OFF, letterboxing, film reel effect.
{f'5. **voiceover_caption_sync** (1-10): Video has voiceover. Does the caption text amount per segment seem appropriate for typical speaking pace? Flag if segments have too much text for their duration (voice would race ahead of caption) or vice versa. Add to issues if mismatch suspected.' if has_voiceover else ''}

Respond with ONLY valid JSON (no markdown, no extra text):
{{
  "overall_score": <1-10>,
  "pass": <true if overall_score>=6 and no critical issues, else false>,
  "scores": {{
    "text_readability": <1-10>,
    "visual_quality": <1-10>,
    "footage_relevance": <1-10>,
    "production_quality": <1-10>
    {', "voiceover_caption_sync": <1-10>' if has_voiceover else ''}
  }},
  "issues": ["list", "of", "specific", "problems", "e.g. segment 2 is gray/washed out", "segment 3 has film reel effect"],
  "suggestions": ["actionable", "improvements"]
}}"""
            }
        ]

        for i, path in enumerate(frame_paths):
            b64 = base64.standard_b64encode(path.read_bytes()).decode()
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"}
            })

        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            max_tokens=1024,
        )
        raw = resp.choices[0].message.content.strip()
        # Strip markdown code block if present
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
    parser.add_argument("--voiceover", action="store_true", help="Video has voiceover; rate caption sync")
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
    rating = rate_video(video_path, script_path, output_path, has_voiceover=args.voiceover)
    out = output_path or OUTPUT_DIR / f"{video_path.stem}_rating.json"

    print(f"Rating saved to: {out}")
    print(f"Overall: {rating['overall_score']}/10 | Pass: {rating['pass']}")
    if rating.get("issues"):
        print("Issues:", ", ".join(rating["issues"]))
    if rating.get("suggestions"):
        print("Suggestions:", ", ".join(rating["suggestions"]))


if __name__ == "__main__":
    main()
