"""
Polish: Add educational text overlay and optional TTS voiceover to draft videos.
"""

import os
from pathlib import Path

from moviepy import (
    VideoFileClip,
    TextClip,
    CompositeVideoClip,
    AudioFileClip,
    CompositeAudioClip,
    concatenate_audioclips,
)
from moviepy.audio.fx import MultiplyVolume
from moviepy.video.fx.MultiplySpeed import MultiplySpeed
from dotenv import load_dotenv

from dataclasses import replace

from src.scout import parse_script

load_dotenv()

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _wrap_text_at_words(text: str, max_chars: int = 25) -> str:
    """Wrap text at word boundaries to avoid mid-word breaks (e.g. 'm ore')."""
    words = text.split()
    lines = []
    current = []
    current_len = 0
    for w in words:
        if current_len + len(w) + (1 if current else 0) <= max_chars:
            current.append(w)
            current_len += len(w) + (1 if current_len else 0)
        else:
            if current:
                lines.append(" ".join(current))
            current = [w]
            current_len = len(w)
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


def _find_font() -> str | None:
    """Find a bold font for Instagram-style text (prefer Arial Bold/Black)."""
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    return None


def add_text_overlay(
    video: VideoFileClip,
    segments: list,
    font: str | None = None,
) -> CompositeVideoClip:
    """
    Composite text overlays in Instagram Reels style:
    - Bold font, white text
    - Dark semi-transparent bar behind text
    - Centered, lower-third position
    """
    font = font or _find_font()
    text_clips = []
    t = 0.0

    # Instagram-style: bold font, sized to stay well within frame
    font_size = min(72, max(44, video.w // 16))
    # Aggressive margins - 15% buffer each side to prevent cutoff on any segment
    h_margin = int(video.w * 0.15)
    v_margin = int(video.h * 0.035)
    bar_padding = (h_margin, v_margin)
    content_width = video.w - 2 * h_margin

    for seg in segments:
        if not seg.text:
            t += seg.duration_seconds
            continue

        wrapped = _wrap_text_at_words(seg.text)
        txt = TextClip(
            text=wrapped,
            font=font,
            font_size=font_size,
            color="white",
            stroke_color=None,
            stroke_width=0,
            bg_color=(30, 30, 30),
            method="label",
            size=(content_width, None),
            text_align="center",
            margin=bar_padding,
            duration=seg.duration_seconds,
        )
        # Lower third: center horizontally, bottom 25% of frame
        txt = (
            txt.with_position(("center", 0.68), relative=True)
            .with_start(t)
            .with_layer_index(1)
        )
        text_clips.append(txt)
        t += seg.duration_seconds

    if not text_clips:
        return video

    return CompositeVideoClip([video] + text_clips, use_bgclip=True)


def generate_tts_audio(segments: list, output_path: Path) -> Path:
    """Generate TTS for each segment's text and concatenate into one audio file."""
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set in .env")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_path.parent / "_tts_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    audio_paths = []
    try:
        for i, seg in enumerate(segments):
            text = seg.text or seg.query
            if not text.strip():
                continue
            seg_path = temp_dir / f"seg_{i}.mp3"
            response = client.audio.speech.create(
                model="tts-1-hd",
                voice="nova",
                input=text,
            )
            response.write_to_file(str(seg_path))
            audio_paths.append((seg_path, seg.duration_seconds))

        if not audio_paths:
            return None

        # Time-stretch each TTS clip to match segment duration (align voice with captions)
        clips = []
        for (p, target_dur) in audio_paths:
            clip = AudioFileClip(str(p))
            if abs(clip.duration - target_dur) > 0.3:
                ratio = clip.duration / target_dur
                clip = clip.with_effects([MultiplySpeed(final_duration=target_dur)])
                if ratio < 0.7 or ratio > 1.5:
                    import sys
                    print(f"  (TTS stretch {ratio:.2f}x for segment)", file=sys.stderr)
            clips.append(clip)
        total = concatenate_audioclips(clips)
        total.write_audiofile(str(output_path), codec="mp3")
        return output_path
    finally:
        for p in temp_dir.glob("seg_*.mp3"):
            p.unlink(missing_ok=True)
        if temp_dir.exists():
            temp_dir.rmdir()


def _prepare_music(music_path: Path, duration: float, volume: float = 0.15) -> AudioFileClip:
    """Load music, loop if needed, trim to duration, set background volume (default 15%)."""
    music = AudioFileClip(str(music_path))
    if music.duration < duration:
        n = int(duration / music.duration) + 1
        clips = [music] * n
        music = concatenate_audioclips(clips)
    music = music.subclipped(0, duration)
    return music.with_effects([MultiplyVolume(volume)])


def polish(
    script_path: Path,
    draft_path: Path | None = None,
    output_path: Path | None = None,
    voiceover: bool = False,
    music_path: Path | None = None,
    music_volume: float = 0.15,
    music_audio_path: Path | None = None,
    caption_first_line_only: bool = False,
) -> Path:
    """
    Add text overlay, optional TTS voiceover, optional background music, or generated music.
    When music_audio_path is set, use it as primary audio (no TTS).
    """
    draft_path = draft_path or (OUTPUT_DIR / f"{script_path.stem}_draft.mp4")
    if not draft_path.exists():
        raise FileNotFoundError(f"Draft video not found: {draft_path}")
    if music_path and not music_path.exists():
        raise FileNotFoundError(f"Music file not found: {music_path}")
    if music_audio_path and not music_audio_path.exists():
        raise FileNotFoundError(f"Music audio not found: {music_audio_path}")

    segments = parse_script(script_path)
    video = VideoFileClip(str(draft_path))
    dur = video.duration

    # For music single-segment: use video duration for segment, optionally first-line caption
    if music_audio_path and segments:
        seg = segments[0]
        text = seg.text
        if caption_first_line_only:
            first_line = text.split("\n")[0].strip()
            text = first_line if first_line else text
        segments = [replace(seg, duration_seconds=int(dur), text=text)]

    # Text overlay
    result = add_text_overlay(video, segments)

    # Build final audio
    audio_clips = []

    if music_audio_path:
        music_audio = AudioFileClip(str(music_audio_path))
        if music_audio.duration > dur:
            music_audio = music_audio.subclipped(0, dur)
        audio_clips.append(music_audio.with_effects([MultiplyVolume(1.0)]))
    elif music_path:
        music = _prepare_music(music_path, dur, volume=music_volume)
        audio_clips.append(music)

    if voiceover and not music_audio_path:
        tts_path = OUTPUT_DIR / "_tts_voiceover.mp3"
        if generate_tts_audio(segments, tts_path):
            tts_audio = AudioFileClip(str(tts_path))
            if tts_audio.duration > dur:
                tts_audio = tts_audio.subclipped(0, dur)
            audio_clips.append(tts_audio.with_effects([MultiplyVolume(1.0)]))

    if audio_clips:
        final_audio = CompositeAudioClip(audio_clips).with_duration(dur)
        result = result.without_audio().with_audio(final_audio)

    out = output_path or (OUTPUT_DIR / f"{script_path.stem}_final.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    result.write_videofile(str(out), codec="libx264", audio_codec="aac")
    result.close()
    video.close()

    return out


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Polish: Add text overlay and optional voiceover to draft video"
    )
    parser.add_argument(
        "script",
        nargs="?",
        default="scripts/sample.txt",
        help="Path to script file",
    )
    parser.add_argument(
        "-i", "--input",
        default=None,
        help="Draft video path (default: output/<script_stem>_draft.mp4)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output video path (default: output/<script_stem>_final.mp4)",
    )
    parser.add_argument(
        "--voiceover",
        action="store_true",
        help="Add TTS voiceover (OpenAI)",
    )
    parser.add_argument(
        "-m", "--music",
        default=None,
        help="Path to background music file (MP3, etc)",
    )
    parser.add_argument(
        "--music-volume",
        type=float,
        default=0.15,
        help="Music volume 0–1 (default 0.15 = 15%%, voiceover stays at 100%%)",
    )
    args = parser.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"Error: script not found: {script_path}")
        return

    draft_path = Path(args.input) if args.input else None
    output_path = Path(args.output) if args.output else None
    music_path = Path(args.music) if args.music else None

    out = polish(
        script_path,
        draft_path=draft_path,
        output_path=output_path,
        voiceover=args.voiceover,
        music_path=music_path,
        music_volume=args.music_volume,
    )
    print(f"Output: {out}")


if __name__ == "__main__":
    main()
