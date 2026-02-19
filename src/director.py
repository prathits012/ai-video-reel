"""
Director: Assemble video clips into a single reel.
Trims each clip to target duration and concatenates with MoviePy.
"""

from pathlib import Path

from moviepy import VideoFileClip, concatenate_videoclips
from moviepy.video.fx.Crop import Crop
from moviepy.video.fx.Resize import Resize

from src.scout import parse_script, Segment

CLIPS_DIR = Path(__file__).resolve().parent.parent / "clips"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
TARGET_SIZE = (1080, 1920)  # vertical reel: width x height


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


def _resize_to_fill(clip: VideoFileClip) -> VideoFileClip:
    """
    Resize and center-crop clip to TARGET_SIZE so it fills the frame.
    Prevents film reel effect, letterboxing, and scrolling from mismatched aspect ratios.
    """
    w, h = clip.size
    tw, th = TARGET_SIZE
    scale = max(tw / w, th / h)
    new_w, new_h = int(w * scale), int(h * scale)
    scaled = clip.with_effects([Resize(new_size=(new_w, new_h))])
    x_center, y_center = new_w / 2, new_h / 2
    cropped = scaled.with_effects([
        Crop(x_center=x_center, y_center=y_center, width=tw, height=th)
    ])
    return cropped


def director(
    script_path: Path,
    clips_dir: Path | None = None,
    output_path: Path | None = None,
    single_clip: bool = False,
    target_duration: float | None = None,
) -> Path:
    """
    Assemble clips into a single video.
    1. Parse script for segment durations
    2. Load clips, trim each to target duration (or use one clip for full duration)
    3. Concatenate and write to output
    """
    clips_dir = clips_dir or (CLIPS_DIR / script_path.stem)
    output_dir = output_path.parent if output_path else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    segments = parse_script(script_path)
    total_duration = target_duration if target_duration is not None else sum(s.duration_seconds for s in segments)
    clip_paths = get_clips_in_order(clips_dir)

    if single_clip:
        if not clip_paths:
            raise ValueError("No clips found. Run Scout with --single-clip first.")
        clip_path = clip_paths[0]
        clip = VideoFileClip(str(clip_path))
        duration = min(total_duration, clip.duration)
        trimmed = clip.subclipped(0, duration)
        normalized = _resize_to_fill(trimmed)
        if normalized.duration < total_duration:
            n = int(total_duration / normalized.duration) + 1
            normalized = concatenate_videoclips([normalized] * n, method="chain")
        final = normalized.subclipped(0, total_duration)
    else:
        if len(clip_paths) < len(segments):
            raise ValueError(
                f"Not enough clips: found {len(clip_paths)}, need {len(segments)}. "
                "Run Scout first: python -m src.scout <script>"
            )
        clip_paths = clip_paths[: len(segments)]
        trimmed_clips = []
        source_clips = []

        for seg, cp in zip(segments, clip_paths, strict=True):
            clip = VideoFileClip(str(cp))
            source_clips.append(clip)
            duration = min(seg.duration_seconds, clip.duration)
            trimmed = clip.subclipped(0, duration)
            normalized = _resize_to_fill(trimmed)
            trimmed_clips.append(normalized)

        final = concatenate_videoclips(trimmed_clips, method="chain")
    out = output_path or output_dir / f"{script_path.stem}_draft.mp4"
    final.write_videofile(str(out), codec="libx264", audio_codec="aac")
    final.close()
    if not single_clip:
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
    parser.add_argument("--single-clip", action="store_true", help="Use one clip for entire video (loop/trim to fit)")
    args = parser.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"Error: script not found: {script_path}")
        return

    clips_dir = Path(args.clips) if args.clips else None
    output_path = Path(args.output) if args.output else None

    out = director(script_path, clips_dir=clips_dir, output_path=output_path, single_clip=args.single_clip)
    print(f"Output: {out}")


if __name__ == "__main__":
    main()
