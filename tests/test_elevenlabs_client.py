"""Unit tests for src/elevenlabs_client.py"""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.elevenlabs_client import (
    MAX_SECTION_MS,
    MIN_SECTION_MS,
    POSITIVE_GLOBAL_STYLES,
    _build_composition_plan,
    _split_lyrics_to_lines,
    generate_song,
)
from src.scout import Segment


# ---------------------------------------------------------------------------
# _build_composition_plan
# ---------------------------------------------------------------------------

class TestBuildCompositionPlan:
    def _make_seg(self, text="Hello world", duration=8):
        return Segment(query="ocean", duration_seconds=duration, text=text)

    def test_returns_dict_with_required_keys(self):
        plan = _build_composition_plan([self._make_seg()])
        assert "positive_global_styles" in plan
        assert "sections" in plan

    def test_global_styles_match_constants(self):
        plan = _build_composition_plan([self._make_seg()])
        assert plan["positive_global_styles"] == POSITIVE_GLOBAL_STYLES

    def test_one_section_per_segment(self):
        segs = [self._make_seg() for _ in range(3)]
        plan = _build_composition_plan(segs)
        assert len(plan["sections"]) == 3

    def test_section_names_are_verse_n(self):
        segs = [self._make_seg() for _ in range(3)]
        plan = _build_composition_plan(segs)
        assert plan["sections"][0]["section_name"] == "Verse 1"
        assert plan["sections"][2]["section_name"] == "Verse 3"

    def test_section_name_falls_back_after_26(self):
        segs = [self._make_seg() for _ in range(27)]
        plan = _build_composition_plan(segs)
        assert plan["sections"][26]["section_name"] == "Section 27"

    def test_duration_clamped_to_min(self):
        seg = self._make_seg(duration=1)  # 1s = 1000ms < MIN_SECTION_MS
        plan = _build_composition_plan([seg])
        assert plan["sections"][0]["duration_ms"] == MIN_SECTION_MS

    def test_duration_clamped_to_max(self):
        seg = self._make_seg(duration=200)  # 200s = 200000ms > MAX_SECTION_MS
        plan = _build_composition_plan([seg])
        assert plan["sections"][0]["duration_ms"] == MAX_SECTION_MS

    def test_normal_duration_converted_correctly(self):
        seg = self._make_seg(duration=10)
        plan = _build_composition_plan([seg])
        assert plan["sections"][0]["duration_ms"] == 10000

    def test_uses_query_when_text_is_empty(self):
        seg = Segment(query="volcano erupting", duration_seconds=5, text="")
        plan = _build_composition_plan([seg])
        lines = plan["sections"][0]["lines"]
        assert any("volcano" in line.lower() for line in lines)

    def test_lines_field_is_non_empty_list(self):
        plan = _build_composition_plan([self._make_seg()])
        assert isinstance(plan["sections"][0]["lines"], list)
        assert len(plan["sections"][0]["lines"]) > 0


# ---------------------------------------------------------------------------
# generate_song
# ---------------------------------------------------------------------------

class TestGenerateSong:
    def _make_seg(self, text="Electrons flow", duration=8):
        return Segment(query="electricity", duration_seconds=duration, text=text)

    def test_raises_without_api_key(self, tmp_path):
        with patch.dict("os.environ", {}, clear=True):
            import os
            os.environ.pop("ELEVENLABS_API_KEY", None)
            with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
                generate_song([self._make_seg()], title="test", output_path=tmp_path / "out.mp3")

    def test_raises_with_empty_segments(self, tmp_path):
        with patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test-key"}):
            with pytest.raises(ValueError, match="No segments"):
                generate_song([], title="test", output_path=tmp_path / "out.mp3")

    def test_returns_path_and_duration_on_success(self, tmp_path):
        fake_audio = b"ID3" + b"\x00" * 100  # Fake MP3 bytes
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_audio
        mock_response.raise_for_status = MagicMock()

        out_path = tmp_path / "song.mp3"
        segs = [self._make_seg(duration=10), self._make_seg(duration=8)]

        with patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test-key"}):
            with patch("requests.post", return_value=mock_response):
                path, duration = generate_song(segs, title="test", output_path=out_path)

        assert path == out_path
        assert out_path.read_bytes() == fake_audio
        # Total duration = sum of clamped section durations (10000 + 8000 ms = 18s)
        assert duration == pytest.approx(18.0)

    def test_raises_on_http_error(self, tmp_path):
        import requests as req

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req.HTTPError("403")
        mock_response.response = None

        with patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test-key"}):
            with patch("requests.post", return_value=mock_response):
                with pytest.raises(RuntimeError, match="ElevenLabs music generation failed"):
                    generate_song(
                        [self._make_seg()],
                        title="test",
                        output_path=tmp_path / "song.mp3",
                    )

    def test_default_output_path_uses_title(self, tmp_path):
        fake_audio = b"ID3" + b"\x00" * 100
        mock_response = MagicMock()
        mock_response.content = fake_audio
        mock_response.raise_for_status = MagicMock()

        with patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test-key"}):
            with patch("src.elevenlabs_client.OUTPUT_DIR", tmp_path):
                with patch("requests.post", return_value=mock_response):
                    path, _ = generate_song([self._make_seg()], title="My Song")

        assert "my_song" in path.name.lower() or "elevenlabs" in path.name.lower()
