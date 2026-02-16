"""
Director: Assemble video clips into a single reel.
Trims each clip to target duration and concatenates with MoviePy.
"""

from pathlib import Path

from moviepy import VideoFileClip, concatenate_videoclips

from src.scout import parse_script, Segment

CLIPS_DIR = Path(__file__).resolve().parent.parent / "clips"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def get_clips_in_order(clips_dir: Path) -> list[Path]:
    """Return clip paths sorted by segment number (segment_00, segment_01, ...)."""
    clips = sorted(clips_dir.glob("segment_*.mp4"), key=_segment_sort_key)
    return clips


def _segment_sort_key(p: Path) -> tuple[int, str]:
    """Extract segment index for sorting."""
    name = p.stem
    parts = name.split("_", 2)
    if len(parts) >= 2 and parts[1].isdigit():
        return (int(parts[1]), name)
    return (999, name)


def director(
    script_path: Path,
    clips_dir: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    """
    Assemble clips into a single video.
    1. Parse script for segment durations
    2. Load clips, trim each to target duration
    3. Concatenate and write to output
    """
    clips_dir = clips_dir or (CLIPS_DIR / script_path.stem)
    output_dir = output_path.parent if output_path else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    segments = parse_script(script_path)
    clip_paths = get_clips_in_order(clips_dir)

    if len(clip_paths) < len(segments):
        raise ValueError(
            f"Not enough clips: found {len(clip_paths)}, need {len(segments)}. "
            "Run Scout first: python -m src.scout <script>"
        )

    clip_paths = clip_paths[: len(segments)]
    trimmed_clips = []
    source_clips = []

    for seg, clip_path in zip(segments, clip_paths, strict=True):
        clip = VideoFileClip(str(clip_path))
        source_clips.append(clip)
        duration = min(seg.duration_seconds, clip.duration)
        trimmed = clip.subclipped(0, duration)
        trimmed_clips.append(trimmed)

    final = concatenate_videoclips(trimmed_clips, method="chain")
    out = output_path or output_dir / f"{script_path.stem}_draft.mp4"
    final.write_videofile(str(out), codec="libx264", audio_codec="aac")
    final.close()
    for c in source_clips:
        c.close()

    return out


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Director: Assemble clips into a reel")
    parser.add_argument(
        "script",
        nargs="?",
        default="scripts/sample.txt",
        help="Path to script file (default: scripts/sample.txt)",
    )
    parser.add_argument("-c", "--clips", default=None, help="Clips directory (default: clips/<script_stem>/)")
    parser.add_argument("-o", "--output", default=None, help="Output video path (default: output/<script>_draft.mp4)")
    args = parser.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"Error: script not found: {script_path}")
        return

    clips_dir = Path(args.clips) if args.clips else None
    output_path = Path(args.output) if args.output else None

    out = director(script_path, clips_dir=clips_dir, output_path=output_path)
    print(f"Output: {out}")


if __name__ == "__main__":
    main()
