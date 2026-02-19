"""
Iterate: Run polish → rate in a loop until pass or max iterations.
"""

from pathlib import Path

from src.polish import polish
from src.rate import rate_video

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def iterate(
    script_path: Path,
    max_iterations: int = 3,
    min_score: int = 8,
    voiceover: bool = False,
    music_path: Path | None = None,
    music_volume: float = 0.15,
    has_music: bool = False,
) -> dict:
    """
    Run polish → rate until pass and no critical issues, or max iterations.
    Returns the final rating dict.
    """
    script_path = Path(script_path)
    draft_path = OUTPUT_DIR / f"{script_path.stem}_draft.mp4"
    if not draft_path.exists():
        raise FileNotFoundError(f"Draft not found: {draft_path}. Run Director first.")

    rating = None
    for i in range(max_iterations):
        print(f"\n--- Iteration {i + 1}/{max_iterations} ---")
        print("Running polish...")
        out = polish(
            script_path,
            draft_path=draft_path,
            voiceover=voiceover,
            music_path=music_path,
            music_volume=music_volume,
        )
        print(f"Polish output: {out}")

        print("Running rate...")
        rating = rate_video(
            out,
            script_path,
            has_voiceover=voiceover,
            has_music=has_music or music_path is not None,
        )
        print(f"Rating: {rating['overall_score']}/10 | Pass: {rating['pass']}")
        if rating.get("issues"):
            print("Issues:", ", ".join(rating["issues"]))
        if rating.get("suggestions"):
            print("Suggestions:", ", ".join(rating["suggestions"]))

        if rating["pass"] and not rating.get("issues") and rating["overall_score"] >= min_score:
            print("\n✓ Target met. Done.")
            return rating

    print(f"\nStopped after {max_iterations} iterations.")
    return rating


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Iterate: polish → rate until pass or max iterations"
    )
    parser.add_argument(
        "script",
        nargs="?",
        default="scripts/benefits_of_morning_routine.txt",
        help="Script path",
    )
    parser.add_argument("-n", "--max-iterations", type=int, default=3)
    parser.add_argument("--min-score", type=int, default=8)
    parser.add_argument("--voiceover", action="store_true", help="Add TTS voiceover")
    parser.add_argument("-m", "--music", help="Path to background music")
    parser.add_argument("--music-volume", type=float, default=0.15, help="Music volume 0-1 (default 0.15)")
    args = parser.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"Error: script not found: {script_path}")
        return

    music_path = Path(args.music) if args.music else None
    iterate(
        script_path,
        max_iterations=args.max_iterations,
        min_score=args.min_score,
        voiceover=args.voiceover,
        music_path=music_path,
        music_volume=args.music_volume,
    )


if __name__ == "__main__":
    main()
