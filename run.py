#!/usr/bin/env python3
"""
Run: Single command to generate a reel from topic or script.

  python run.py "benefits of meditation"
  python run.py "benefits of meditation" --lyrical --voiceover -m music.mp3
  python run.py scripts/benefits_of_morning_routine.txt
"""

import sys
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.script_writer import write_script
from src.scout import scout, parse_script
from src.director import director
from src.polish import polish
from src.iterate import iterate
from src.music_fetcher import pick_local_music
from src.rate import rate_video
from src.safety_rate import safety_check, print_safety_result
from src.elevenlabs_client import generate_song

SCRIPTS_DIR = PROJECT_ROOT / "scripts"
OUTPUT_DIR = PROJECT_ROOT / "output"


def _slugify(s: str) -> str:
    return "".join(c if c.isalnum() or c in " -" else "_" for c in s)[:50].strip().replace(" ", "_").lower() or "script"


def run_hamilton(
    topic_or_script: str,
    *,
    duration: int = 30,
) -> Path:
    """
    Hamilton-style pipeline: flow script → ElevenLabs music → scout (1 clip) → director → polish.
    Single clip only. Uses female voice, clear educational pop style.
    """
    import math

    script_path = Path(topic_or_script)
    if script_path.exists():
        script_path = script_path.resolve()
        print(f"Using script: {script_path}")
    else:
        script_path = SCRIPTS_DIR / f"{_slugify(topic_or_script)}.txt"
        print(f"Generating flow script for: {topic_or_script}")
        write_script(
            topic_or_script,
            output_path=script_path,
            flow=True,
            total_duration=duration,
        )
        print(f"Script written: {script_path}\n")

    segments = parse_script(script_path)
    if not segments:
        raise ValueError("Flow script has no segments.")
    if not any((s.text or s.query or "").strip() for s in segments):
        raise ValueError("Flow script has no LYRICS.")
    title = script_path.stem.replace("_", " ").title()

    print("ElevenLabs: generating song...")
    audio_path, song_duration = generate_song(
        segments=segments,
        title=title,
        output_path=OUTPUT_DIR / f"{script_path.stem}_elevenlabs.mp3",
    )
    print(f"ElevenLabs: {audio_path} ({song_duration:.1f}s)\n")

    min_dur = math.ceil(song_duration)

    print("Scout: fetching Pexels footage...")
    scout(script_path, single_clip=True, min_duration=min_dur)
    print()

    print("Director: assembling clip...")
    draft_path = director(
        script_path,
        single_clip=True,
        target_duration=song_duration,
    )
    print(f"Draft: {draft_path}\n")

    print("Polish: adding music audio and captions...")
    out = polish(
        script_path,
        draft_path=draft_path,
        music_audio_path=audio_path,
    )
    print(f"\n✓ Done: {out}")

    print("\nSafety: running content safety check...")
    safety = safety_check(out, script_path)
    print_safety_result(safety)
    if not safety["safe"]:
        print(
            f"\nWARNING: Safety verdict is '{safety['verdict']}'. "
            "Review the safety report before publishing."
        )

    return out


def run(
    topic_or_script: str,
    *,
    lyrical: bool = False,
    voiceover: bool = False,
    music_path: Path | None = None,
    iterate_rate: bool = False,
    rate: bool = False,
    music_volume: float = 0.15,
    single_clip: bool = False,
    segments: int = 5,
    duration: int = 30,
    max_iterations: int = 3,
) -> Path:
    """
    Run the full pipeline: script (if topic) → scout → director → polish.
    Optionally run iterate (polish → rate loop).
    """
    # Resolve script path
    script_path = Path(topic_or_script)
    if script_path.exists():
        # User passed a script path – use it
        script_path = script_path.resolve()
        print(f"Using script: {script_path}")
    else:
        # Treat as topic – generate script
        script_path = SCRIPTS_DIR / f"{_slugify(topic_or_script)}.txt"
        print(f"Generating script for: {topic_or_script}")
        write_script(
            topic_or_script,
            output_path=script_path,
            lyrical=lyrical,
            num_segments=segments,
            total_duration=duration,
        )
        print(f"Script written: {script_path}\n")

    # Scout
    print("Scout: fetching Pexels footage...")
    scout(script_path, single_clip=single_clip)
    print()

    # Director
    print("Director: assembling clips...")
    draft_path = director(script_path, single_clip=single_clip)
    print(f"Draft: {draft_path}\n")

    # Pick local music if -m auto
    if music_path and str(music_path).lower() == "auto":
        music_path = pick_local_music(mood="default")
        if music_path:
            print(f"Music: {music_path}\n")
        else:
            print("Music: no tracks in assets/music/ (add calm.mp3, uplifting.mp3, etc.)\n")
            music_path = None

    if iterate_rate:
        # Polish → rate loop
        print("Iterate: polish + rate until pass...")
        iterate(
            script_path,
            voiceover=voiceover,
            music_path=music_path,
            music_volume=music_volume,
            max_iterations=max_iterations,
            has_music=music_path is not None,
        )
        return OUTPUT_DIR / f"{script_path.stem}_final.mp4"

    # Polish (single pass)
    print("Polish: adding text overlay...")
    out = polish(
        script_path,
        draft_path=draft_path,
        voiceover=voiceover,
        music_path=music_path,
        music_volume=music_volume,
    )
    print(f"\n✓ Done: {out}")

    # Safety check always runs
    print("\nSafety: running content safety check...")
    safety = safety_check(out, script_path)
    print_safety_result(safety)
    if not safety["safe"]:
        print(
            f"\nWARNING: Safety verdict is '{safety['verdict']}'. "
            "Review the safety report before publishing."
        )

    # Optional: run AI quality rating once and save JSON
    if rate:
        print("Rate: AI rating...")
        rating = rate_video(
            out,
            script_path,
            has_voiceover=voiceover,
            has_music=music_path is not None,
        )
        print(f"Rating: {rating['overall_score']}/10 | Pass: {rating['pass']}")
        if rating.get("issues"):
            print("Issues:", ", ".join(rating["issues"]))
        print(f"Saved: {OUTPUT_DIR / out.stem}_rating.json")

    return out


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run full reel pipeline: script → scout → director → polish"
    )
    parser.add_argument(
        "topic_or_script",
        help="Topic (e.g. 'benefits of meditation') or path to existing script",
    )
    parser.add_argument("--lyrical", action="store_true", help="Generate rhymed lyrics (song-like)")
    parser.add_argument("--voiceover", action="store_true", help="Add TTS voiceover")
    parser.add_argument("-m", "--music", help="Path to music, or 'auto' to pick from assets/music/")
    parser.add_argument("--iterate", action="store_true", help="Run polish→rate loop until pass")
    parser.add_argument("--rate", action="store_true", help="Run AI rating once and save JSON")
    parser.add_argument("--music-volume", type=float, default=0.15, help="Music volume 0-1 (default 0.15)")
    parser.add_argument("--single-clip", action="store_true", help="Use one long clip (30+ sec) for entire video; better for voiceover flow")
    parser.add_argument("-n", "--segments", type=int, default=5, help="Segments (default: 5)")
    parser.add_argument("-d", "--duration", type=int, default=30, help="Target duration in seconds (default: 30)")
    parser.add_argument("--max-iterations", type=int, default=3, help="Max iterate loops (default: 3)")
    parser.add_argument("--hamilton", action="store_true", help="Hamilton-style: flow script + ElevenLabs music, single-clip, female voice, educational pop")
    args = parser.parse_args()

    music_path = Path(args.music) if args.music else None

    if args.hamilton:
        try:
            run_hamilton(
                args.topic_or_script,
                duration=args.duration,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    try:
        run(
            args.topic_or_script,
            lyrical=args.lyrical,
            voiceover=args.voiceover,
            music_path=music_path,
            iterate_rate=args.iterate,
            rate=args.rate,
            music_volume=args.music_volume,
            single_clip=args.single_clip,
            segments=args.segments,
            duration=args.duration,
            max_iterations=args.max_iterations,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
