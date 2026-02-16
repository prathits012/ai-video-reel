"""
Script Writer: AI generates educational reel scripts from a topic.
Uses OpenAI to create SEGMENT/TEXT/DURATION format for Scout and Director.
"""

import os
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

SCRIPT_FORMAT = """Each segment uses this format:
SEGMENT: <visual search query for stock footage, e.g. "Person studying at desk">
TEXT: <educational text to overlay on screen - short, punchy, 1-2 sentences max>
DURATION: <seconds, 4-8 typical>
---
"""


def generate_script(topic: str, num_segments: int = 5, total_duration: int = 30) -> str:
    """
    Generate an educational reel script for the given topic.
    Returns the script as a string in SEGMENT/TEXT/DURATION format.
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set in .env")

    prompt = f"""You are a script writer for short educational reels (like Instagram Reels or TikTok).

Create a script for a {total_duration}-second educational video about: {topic}

Requirements:
- Write exactly {num_segments} segments.
- Each segment needs SEGMENT (visual search query for stock footage), TEXT (overlay text for viewers), and DURATION (seconds).
- SEGMENT should be a short phrase that would find good stock video on Pexels (e.g. "Person writing in notebook", "Sunset over ocean").
- TEXT is the educational content - clear, engaging, one or two short sentences. This will appear as on-screen overlay.
- DURATION per segment: 4-8 seconds. Total should add up to ~{total_duration} seconds.
- Use the exact format below. Separate segments with ---
- DURATION must be a number only (e.g. DURATION: 5), not "5 seconds".

{SCRIPT_FORMAT}

Output only the script, no preamble."""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


def write_script(topic: str, output_path: Path | None = None, **kwargs) -> Path:
    """
    Generate a script and save it to a file.
    Returns the path to the written file.
    """
    script_text = generate_script(topic, **kwargs)
    output_path = output_path or SCRIPTS_DIR / f"{_slugify(topic)}.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(script_text)
    return output_path


def _slugify(s: str) -> str:
    """Convert topic to safe filename."""
    return "".join(c if c.isalnum() or c in " -" else "_" for c in s)[:50].strip().replace(" ", "_").lower() or "script"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="AI Script Writer: Generate educational reel scripts")
    parser.add_argument("topic", help="Topic for the educational reel (e.g. 'benefits of meditation')")
    parser.add_argument("-o", "--output", help="Output file path (default: scripts/<topic>.txt)")
    parser.add_argument("-n", "--segments", type=int, default=5, help="Number of segments (default: 5)")
    parser.add_argument("-d", "--duration", type=int, default=30, help="Target total duration in seconds (default: 30)")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else None
    path = write_script(
        args.topic,
        output_path=output_path,
        num_segments=args.segments,
        total_duration=args.duration,
    )
    print(f"Script written to: {path}")
    print()
    print(path.read_text())


if __name__ == "__main__":
    main()
