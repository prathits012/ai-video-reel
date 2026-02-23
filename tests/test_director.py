"""Unit tests for src/director.py"""

from pathlib import Path

import pytest

from src.director import _segment_sort_key, get_clips_in_order


class TestSegmentSortKey:
    def test_standard_segment_00(self):
        p = Path("clips/segment_00_ocean.mp4")
        assert _segment_sort_key(p) == (0, "segment_00_ocean")

    def test_standard_segment_03(self):
        p = Path("clips/segment_03_lava.mp4")
        assert _segment_sort_key(p) == (3, "segment_03_lava")

    def test_single_clip_format(self):
        p = Path("clips/segment_00_single.mp4")
        assert _segment_sort_key(p)[0] == 0

    def test_non_standard_name_gets_high_index(self):
        p = Path("clips/some_other_file.mp4")
        assert _segment_sort_key(p)[0] == 999

    def test_two_digit_index_sorted_correctly(self):
        p10 = Path("clips/segment_10_thing.mp4")
        p2 = Path("clips/segment_02_thing.mp4")
        assert _segment_sort_key(p2) < _segment_sort_key(p10)


class TestGetClipsInOrder:
    def test_returns_sorted_clips(self, tmp_path):
        # Create clips in reverse order
        (tmp_path / "segment_02_ocean.mp4").touch()
        (tmp_path / "segment_00_sunset.mp4").touch()
        (tmp_path / "segment_01_lava.mp4").touch()

        clips = get_clips_in_order(tmp_path)
        names = [c.name for c in clips]
        assert names == [
            "segment_00_sunset.mp4",
            "segment_01_lava.mp4",
            "segment_02_ocean.mp4",
        ]

    def test_returns_empty_list_for_empty_dir(self, tmp_path):
        clips = get_clips_in_order(tmp_path)
        assert clips == []

    def test_ignores_non_mp4_files(self, tmp_path):
        (tmp_path / "segment_00_thing.mp4").touch()
        (tmp_path / "segment_01_notes.txt").touch()

        clips = get_clips_in_order(tmp_path)
        assert len(clips) == 1
        assert clips[0].suffix == ".mp4"
