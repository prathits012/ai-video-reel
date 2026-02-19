"""
Safety Rater: Multi-criteria content safety check for generated reels.

Runs automatically after every pipeline (standard and Hamilton). Uses:
  - OpenAI Moderation API (text) for fast, zero-cost hate/violence/sexual/self-harm flags
  - GPT-4o vision on sampled frames for visual safety + contextual analysis

Criteria:
  1. text_safety         – overlay text free from hate, violence, adult content, profanity
  2. visual_safety       – frames free from graphic, violent, or adult imagery
  3. topic_safety        – educational topic is appropriate and not harmful
  4. factual_plausibility – no obvious dangerous misinformation (e.g. medical/legal/financial)
  5. audience_suitability – safe for all ages / general social media audiences
  6. platform_compliance  – would pass Instagram/TikTok/YouTube community guidelines

Verdict:
  "approved"     – safe to publish (all scores >= 7, no flags)
  "needs_review" – borderline; human review recommended (any score 4–6)
  "rejected"     – unsafe; do not publish (any score <= 3, or hard flag triggered)
"""

import base64
import json
import os
import tempfile
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

from src.scout import parse_script
from src.rate import extract_frames

load_dotenv()

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

# Sample fewer frames than quality rater – safety needs coverage, not density
SAFETY_FRAMES_PER_SEGMENT = 2
SAFETY_MAX_FRAMES = 12

# Hard moderation categories that instantly trigger "rejected"
HARD_FLAG_CATEGORIES = {
    "sexual",
    "sexual/minors",
    "violence/graphic",
    "hate/threatening",
    "self-harm/intent",
    "self-harm/instructions",
}


def _run_text_moderation(client: OpenAI, texts: list[str]) -> dict:
    """
    Run OpenAI Moderation API on all text content from the script.
    Returns aggregated result with per-category max scores.
    """
    combined = "\n".join(t for t in texts if t.strip())
    if not combined.strip():
        return {"flagged": False, "categories": {}, "category_scores": {}}

    # Moderation API accepts up to ~10k chars; chunk if needed
    MAX_CHARS = 8000
    chunks = [combined[i : i + MAX_CHARS] for i in range(0, len(combined), MAX_CHARS)]

    flagged = False
    all_scores: dict[str, float] = {}
    hard_flags: list[str] = []

    for chunk in chunks:
        resp = client.moderations.create(input=chunk, model="omni-moderation-latest")
        for result in resp.results:
            if result.flagged:
                flagged = True
            for cat, score in result.category_scores.__dict__.items():
                if score is not None:
                    all_scores[cat] = max(all_scores.get(cat, 0.0), float(score))
            for cat, triggered in result.categories.__dict__.items():
                if triggered and cat.replace("_", "/") in HARD_FLAG_CATEGORIES:
                    hard_flags.append(cat)

    return {
        "flagged": flagged,
        "hard_flags": hard_flags,
        "category_scores": all_scores,
    }


def safety_check(
    video_path: Path,
    script_path: Path,
    output_path: Path | None = None,
) -> dict:
    """
    Run full content safety check on a finished reel.

    Returns a dict with:
      safe (bool), verdict (str), scores (dict), flags (list), details (str)
    Saves result to output/<video_stem>_safety.json.
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set in .env")

    segments = parse_script(script_path)
    script_text = script_path.read_text()

    # --- Step 1: Text moderation via Moderation API ---
    all_texts = [script_text]
    for seg in segments:
        if seg.text:
            all_texts.append(seg.text)
    moderation = _run_text_moderation(client, all_texts)

    # --- Step 2: Visual + contextual safety via GPT-4o vision ---
    with tempfile.TemporaryDirectory() as tmpdir:
        frames_dir = Path(tmpdir)
        frame_tuples = extract_frames(
            video_path,
            script_path,
            frames_dir,
            frames_per_segment=SAFETY_FRAMES_PER_SEGMENT,
            max_frames=SAFETY_MAX_FRAMES,
        )

        frame_index_lines = []
        for idx, (seg_i, ts, _) in enumerate(frame_tuples):
            seg = segments[seg_i]
            label = (seg.text or seg.query or "")[:60].replace("\n", " ")
            frame_index_lines.append(
                f"  Frame {idx + 1}: segment {seg_i + 1} at {ts:.1f}s — \"{label}\""
            )
        frame_index = "\n".join(frame_index_lines)

        # Moderation context to include in prompt
        mod_context = ""
        if moderation["flagged"]:
            flagged_cats = [
                cat for cat, score in moderation["category_scores"].items()
                if score > 0.2
            ]
            mod_context = (
                f"\n\nNOTE: The OpenAI Moderation API flagged this script text. "
                f"Elevated scores in: {', '.join(flagged_cats)}. "
                f"Weight your evaluation accordingly."
            )

        content: list[dict] = [
            {
                "type": "text",
                "text": f"""You are a content safety reviewer for short-form educational social media reels.
Your job is to evaluate whether this reel is safe and appropriate to publish publicly.

SCRIPT:
{script_text}
{mod_context}

You will see {len(frame_tuples)} frames sampled from the video:
{frame_index}

Evaluate on the following SAFETY criteria. Each is scored 1–10 where:
  10 = completely safe, no concerns
   7 = minor/borderline concern, likely fine
   4 = moderate concern, needs human review
   1 = serious safety violation, must not publish

CRITERIA:

1. **text_safety** (1-10)
   - Is the overlay text free from: hate speech, slurs, threats, violent language,
     sexual content, profanity, or content that could incite harm?
   - Flag if text could be misread as harmful out of context.

2. **visual_safety** (1-10)
   - Are the video frames free from: graphic violence, blood/gore, sexual or
     suggestive imagery, disturbing/shocking content?
   - Flag if footage is inappropriate for a general audience including minors.

3. **topic_safety** (1-10)
   - Is the educational topic itself safe? Topics that normalise self-harm,
     illegal activity, substance abuse, weapons, or dangerous pseudoscience score LOW.
   - Legitimate educational topics (science, wellness, history, etc.) score HIGH.

4. **factual_plausibility** (1-10)
   - Does the script contain dangerous misinformation?
   - Red flags: unverified medical/health claims, dangerous DIY instructions,
     anti-vaccine content, denial of established science.
   - Score LOW if claims could cause real-world harm if believed.

5. **audience_suitability** (1-10)
   - Is the content appropriate for all ages (13+)?
   - Consider text complexity, emotional tone, and imagery together.
   - Content that is frightening, manipulative, or exploitative scores LOW.

6. **platform_compliance** (1-10)
   - Would this pass Instagram, TikTok, and YouTube Shorts community guidelines?
   - Consider: copyright risk from visible logos/brands, political sensitivity,
     controversial framing, misleading thumbnails/captions.

VERDICT RULES:
  "approved"     — all scores >= 7 AND no hard flags
  "needs_review" — any score between 4 and 6 (inclusive), OR moderation API flagged
  "rejected"     — any score <= 3, OR script contains dangerous misinformation,
                   OR OpenAI Moderation hard-flagged (sexual/minors, graphic violence, etc.)

Respond with ONLY valid JSON (no markdown, no extra text):
{{
  "safe": <true if verdict is "approved", else false>,
  "verdict": "approved" | "needs_review" | "rejected",
  "scores": {{
    "text_safety": <1-10>,
    "visual_safety": <1-10>,
    "topic_safety": <1-10>,
    "factual_plausibility": <1-10>,
    "audience_suitability": <1-10>,
    "platform_compliance": <1-10>
  }},
  "flags": ["specific concern e.g. 'overlay text contains the word X'", "..."],
  "details": "one paragraph summary of your safety assessment"
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
        result = json.loads(raw)

    # Merge moderation hard flags into result
    if moderation.get("hard_flags"):
        result["flags"] = result.get("flags", []) + [
            f"OpenAI Moderation hard flag: {f}" for f in moderation["hard_flags"]
        ]
        result["verdict"] = "rejected"
        result["safe"] = False

    result["moderation_api"] = {
        "flagged": moderation["flagged"],
        "top_scores": {
            k: round(v, 4)
            for k, v in sorted(
                moderation["category_scores"].items(), key=lambda x: -x[1]
            )[:5]
        },
    }

    out = output_path or (OUTPUT_DIR / f"{video_path.stem}_safety.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    return result


def print_safety_result(result: dict) -> None:
    """Pretty-print a safety check result to stdout."""
    verdict = result.get("verdict", "unknown").upper()
    safe = result.get("safe", False)
    icon = "✓" if safe else "✗"
    print(f"Safety: {icon} {verdict}")

    scores = result.get("scores", {})
    if scores:
        for criterion, score in scores.items():
            bar = "█" * score + "░" * (10 - score)
            print(f"  {criterion:<25} {bar} {score}/10")

    flags = result.get("flags", [])
    if flags:
        print("Flags:")
        for f in flags:
            print(f"  • {f}")

    details = result.get("details", "")
    if details:
        print(f"Summary: {details}")

    mod = result.get("moderation_api", {})
    if mod.get("flagged"):
        print("Moderation API: FLAGGED")
        for cat, score in mod.get("top_scores", {}).items():
            if score > 0.01:
                print(f"  {cat}: {score:.3f}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Safety check a generated reel video"
    )
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("script", help="Path to script file")
    parser.add_argument("-o", "--output", help="Output JSON path")
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
    result = safety_check(video_path, script_path, output_path)
    out = output_path or OUTPUT_DIR / f"{video_path.stem}_safety.json"
    print(f"Safety report saved to: {out}\n")
    print_safety_result(result)


if __name__ == "__main__":
    main()
