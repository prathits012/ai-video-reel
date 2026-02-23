"""Unit tests for src/scout.py"""

import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.scout import (
    Segment,
    _score_duration,
    _score_resolution,
    parse_script,
    pick_best_video_file,
    score_candidates,
)


# ---------------------------------------------------------------------------
# parse_script
# ---------------------------------------------------------------------------

def _write_script(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "script.txt"
    p.write_text(text)
    return p


class TestParseScript:
    def test_basic_segment(self, tmp_path):
        script = _write_script(tmp_path, textwrap.dedent("""\
            SEGMENT: person meditating
            TEXT: Meditation reduces stress
            DURATION: 6
        """))
        segs = parse_script(script)
        assert len(segs) == 1
        assert segs[0].query == "person meditating"
        assert segs[0].text == "Meditation reduces stress"
        assert segs[0].duration_seconds == 6

    def test_multiple_segments_separated_by_dashes(self, tmp_path):
        script = _write_script(tmp_path, textwrap.dedent("""\
            SEGMENT: sunrise over mountains
            TEXT: The day begins
            DURATION: 5
            ---
            SEGMENT: city traffic at night
            TEXT: Cities never sleep
            DURATION: 7
        """))
        segs = parse_script(script)
        assert len(segs) == 2
        assert segs[0].query == "sunrise over mountains"
        assert segs[1].query == "city traffic at night"
        assert segs[1].duration_seconds == 7

    def test_lyrics_field_parsed_as_text(self, tmp_path):
        script = _write_script(tmp_path, textwrap.dedent("""\
            SEGMENT: flowing river
            LYRICS: Water flows down to the sea
            DURATION: 8
        """))
        segs = parse_script(script)
        assert segs[0].text == "Water flows down to the sea"

    def test_missing_text_field_defaults_to_empty(self, tmp_path):
        script = _write_script(tmp_path, textwrap.dedent("""\
            SEGMENT: abstract background
            DURATION: 5
        """))
        segs = parse_script(script)
        assert segs[0].text == ""

    def test_missing_duration_defaults_to_5(self, tmp_path):
        script = _write_script(tmp_path, textwrap.dedent("""\
            SEGMENT: ocean waves
            TEXT: The sea is vast
        """))
        segs = parse_script(script)
        assert segs[0].duration_seconds == 5

    def test_duration_with_trailing_text_is_extracted(self, tmp_path):
        script = _write_script(tmp_path, textwrap.dedent("""\
            SEGMENT: forest walk
            TEXT: Nature heals
            DURATION: 6 seconds
        """))
        segs = parse_script(script)
        assert segs[0].duration_seconds == 6

    def test_empty_blocks_skipped(self, tmp_path):
        script = _write_script(tmp_path, textwrap.dedent("""\
            ---
            SEGMENT: clouds
            TEXT: Sky is blue
            DURATION: 4
            ---
        """))
        segs = parse_script(script)
        assert len(segs) == 1

    def test_empty_script_returns_empty_list(self, tmp_path):
        script = _write_script(tmp_path, "")
        segs = parse_script(script)
        assert segs == []

    def test_multiline_text_joined(self, tmp_path):
        script = _write_script(tmp_path, textwrap.dedent("""\
            SEGMENT: brain activity
            TEXT: The brain contains
            billions of neurons
            DURATION: 5
        """))
        segs = parse_script(script)
        assert "billions of neurons" in segs[0].text

    def test_case_insensitive_keywords(self, tmp_path):
        script = _write_script(tmp_path, textwrap.dedent("""\
            segment: ocean
            text: Blue water
            duration: 4
        """))
        segs = parse_script(script)
        assert len(segs) == 1
        assert segs[0].query == "ocean"

    def test_quoted_text_stripped(self, tmp_path):
        script = _write_script(tmp_path, textwrap.dedent("""\
            SEGMENT: rain
            TEXT: "Drops keep falling"
            DURATION: 5
        """))
        segs = parse_script(script)
        assert segs[0].text == "Drops keep falling"

    def test_segment_without_query_skipped(self, tmp_path):
        script = _write_script(tmp_path, textwrap.dedent("""\
            TEXT: No query here
            DURATION: 5
            ---
            SEGMENT: valid segment
            TEXT: Has a query
            DURATION: 4
        """))
        segs = parse_script(script)
        assert len(segs) == 1
        assert segs[0].query == "valid segment"


# ---------------------------------------------------------------------------
# pick_best_video_file
# ---------------------------------------------------------------------------

class TestPickBestVideoFile:
    def test_prefers_1080p(self):
        files = [
            {"width": 1280, "height": 720, "link": "hd.mp4"},
            {"width": 1920, "height": 1080, "link": "fhd.mp4"},
            {"width": 640, "height": 360, "link": "sd.mp4"},
        ]
        assert pick_best_video_file(files) == "fhd.mp4"

    def test_falls_back_to_highest_resolution(self):
        files = [
            {"width": 1280, "height": 720, "link": "hd.mp4"},
            {"width": 854, "height": 480, "link": "480p.mp4"},
        ]
        assert pick_best_video_file(files) == "hd.mp4"

    def test_empty_list_returns_none(self):
        assert pick_best_video_file([]) is None

    def test_missing_link_skipped(self):
        files = [
            {"width": 1920, "height": 1080, "link": None},
            {"width": 1280, "height": 720, "link": "hd.mp4"},
        ]
        result = pick_best_video_file(files)
        assert result == "hd.mp4"

    def test_none_dimensions_handled(self):
        files = [{"width": None, "height": None, "link": "unknown.mp4"}]
        result = pick_best_video_file(files)
        assert result == "unknown.mp4"


# ---------------------------------------------------------------------------
# _score_resolution
# ---------------------------------------------------------------------------

class TestScoreResolution:
    def test_full_hd_scores_1(self):
        video = {"video_files": [{"width": 1920, "height": 1080}]}
        assert _score_resolution(video) == pytest.approx(1.0)

    def test_4k_capped_at_1(self):
        video = {"video_files": [{"width": 3840, "height": 2160}]}
        assert _score_resolution(video) == pytest.approx(1.0)

    def test_sd_scores_less_than_half(self):
        video = {"video_files": [{"width": 640, "height": 360}]}
        score = _score_resolution(video)
        assert score < 0.5

    def test_no_video_files_scores_zero(self):
        video = {"video_files": []}
        assert _score_resolution(video) == pytest.approx(0.0)

    def test_picks_best_file_from_multiple(self):
        video = {
            "video_files": [
                {"width": 640, "height": 360},
                {"width": 1920, "height": 1080},
            ]
        }
        assert _score_resolution(video) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# _score_duration
# ---------------------------------------------------------------------------

class TestScoreDuration:
    def test_exactly_2x_scores_1(self):
        video = {"duration": 20}
        assert _score_duration(video, segment_duration=10) == pytest.approx(1.0)

    def test_more_than_2x_capped_at_1(self):
        video = {"duration": 60}
        assert _score_duration(video, segment_duration=10) == pytest.approx(1.0)

    def test_exactly_1x_scores_half(self):
        video = {"duration": 10}
        score = _score_duration(video, segment_duration=10)
        assert score == pytest.approx(0.5)

    def test_zero_duration_scores_zero(self):
        video = {"duration": 0}
        assert _score_duration(video, segment_duration=10) == pytest.approx(0.0)

    def test_none_duration_scores_zero(self):
        video = {"duration": None}
        assert _score_duration(video, segment_duration=10) == pytest.approx(0.0)

    def test_proportional_score(self):
        # clip is 1.5x segment duration → target is 2x → score = 1.5/2 = 0.75
        video = {"duration": 15}
        score = _score_duration(video, segment_duration=10)
        assert score == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# score_candidates
# ---------------------------------------------------------------------------

class TestScoreCandidates:
    def _make_video(self, width=1920, height=1080, duration=30, thumb="http://thumb.jpg"):
        return {
            "video_files": [{"width": width, "height": height, "link": "file.mp4"}],
            "duration": duration,
            "image": thumb,
        }

    def test_raises_on_empty_candidates(self):
        with pytest.raises(ValueError):
            score_candidates([], segment_duration=10)

    def test_single_candidate_always_wins(self):
        video = self._make_video()
        result = score_candidates([video], segment_duration=10, openai_key=None)
        assert result is video

    def test_prefers_longer_higher_res_without_openai(self):
        short_sd = self._make_video(width=640, height=360, duration=5)
        long_fhd = self._make_video(width=1920, height=1080, duration=40)
        result = score_candidates([short_sd, long_fhd], segment_duration=10, openai_key=None)
        assert result is long_fhd

    def test_authenticity_used_when_openai_key_provided(self):
        video_a = self._make_video()
        video_b = self._make_video()

        fake_scores = [3, 9]  # video_b is more authentic

        with patch("src.scout._score_authenticity_batch", return_value=[s / 10.0 for s in fake_scores]):
            result = score_candidates([video_a, video_b], segment_duration=10, openai_key="fake-key")
        assert result is video_b

    def test_falls_back_to_neutral_when_openai_fails(self):
        video_a = self._make_video(width=1920, height=1080, duration=40)
        video_b = self._make_video(width=640, height=360, duration=5)

        with patch("src.scout._score_authenticity_batch", side_effect=Exception("API error")):
            # With no openai_key, should use 50/50 weights
            result = score_candidates([video_a, video_b], segment_duration=10, openai_key=None)
        assert result is video_a


