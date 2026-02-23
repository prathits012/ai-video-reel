"""Unit tests for src/music_fetcher.py"""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.music_fetcher import pick_local_music


class TestPickLocalMusic:
    def test_returns_none_when_no_music_dir(self, tmp_path):
        with patch("src.music_fetcher.MUSIC_DIR", tmp_path / "nonexistent"):
            result = pick_local_music()
        assert result is None

    def test_returns_none_when_dir_is_empty(self, tmp_path):
        with patch("src.music_fetcher.MUSIC_DIR", tmp_path):
            result = pick_local_music()
        assert result is None

    def test_returns_mood_matched_track(self, tmp_path):
        (tmp_path / "calm.mp3").touch()
        (tmp_path / "uplifting.mp3").touch()
        with patch("src.music_fetcher.MUSIC_DIR", tmp_path):
            result = pick_local_music(mood="calm")
        assert result is not None
        assert result.stem == "calm"

    def test_falls_back_to_any_track_for_unknown_mood(self, tmp_path):
        (tmp_path / "energetic.mp3").touch()
        with patch("src.music_fetcher.MUSIC_DIR", tmp_path):
            result = pick_local_music(mood="unknown_mood")
        assert result is not None

    def test_ignores_non_audio_files(self, tmp_path):
        (tmp_path / "notes.txt").touch()
        (tmp_path / "image.png").touch()
        with patch("src.music_fetcher.MUSIC_DIR", tmp_path):
            result = pick_local_music()
        assert result is None

    def test_recognizes_m4a_extension(self, tmp_path):
        (tmp_path / "calm.m4a").touch()
        with patch("src.music_fetcher.MUSIC_DIR", tmp_path):
            result = pick_local_music(mood="calm")
        assert result is not None

    def test_energetic_mood_falls_back_to_uplifting(self, tmp_path):
        # "energetic" maps to "uplifting" in MOOD_FILES
        (tmp_path / "uplifting.mp3").touch()
        with patch("src.music_fetcher.MUSIC_DIR", tmp_path):
            result = pick_local_music(mood="energetic")
        assert result is not None
        assert result.stem == "uplifting"
