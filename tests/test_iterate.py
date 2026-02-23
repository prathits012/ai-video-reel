"""Unit tests for src/iterate.py"""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.iterate import iterate


def _make_script(tmp_path: Path) -> Path:
    script = tmp_path / "test_script.txt"
    script.write_text(textwrap.dedent("""\
        SEGMENT: ocean waves
        TEXT: Waves crash on shore
        DURATION: 5
    """))
    return script


def _make_draft(tmp_path: Path, script: Path) -> Path:
    draft = tmp_path / f"{script.stem}_draft.mp4"
    draft.write_bytes(b"fake video")
    return draft


class TestIterate:
    def _mock_polish_output(self, tmp_path, script):
        out = tmp_path / f"{script.stem}_final.mp4"
        out.write_bytes(b"fake final")
        return out

    def test_raises_if_draft_not_found(self, tmp_path):
        script = _make_script(tmp_path)
        # No draft file created
        with patch("src.iterate.OUTPUT_DIR", tmp_path):
            with pytest.raises(FileNotFoundError, match="Draft not found"):
                iterate(script)

    def test_runs_once_and_returns_rating(self, tmp_path):
        script = _make_script(tmp_path)
        _make_draft(tmp_path, script)
        final = self._mock_polish_output(tmp_path, script)

        mock_rating = {
            "overall_score": 9,
            "pass": True,
            "issues": [],
            "suggestions": [],
        }
        mock_safety = {
            "safe": True,
            "verdict": "approved",
            "scores": {},
            "flags": [],
            "details": "",
        }

        with patch("src.iterate.OUTPUT_DIR", tmp_path):
            with patch("src.iterate.polish", return_value=final) as mock_polish:
                with patch("src.iterate.rate_video", return_value=mock_rating) as mock_rate:
                    with patch("src.iterate.safety_check", return_value=mock_safety):
                        with patch("src.iterate.print_safety_result"):
                            result = iterate(script, max_iterations=1)

        mock_polish.assert_called_once()
        mock_rate.assert_called_once()
        assert result["overall_score"] == 9

    def test_stops_early_when_pass(self, tmp_path):
        script = _make_script(tmp_path)
        _make_draft(tmp_path, script)
        final = self._mock_polish_output(tmp_path, script)

        mock_rating = {"overall_score": 9, "pass": True, "issues": [], "suggestions": []}
        mock_safety = {"safe": True, "verdict": "approved", "scores": {}, "flags": [], "details": ""}

        with patch("src.iterate.OUTPUT_DIR", tmp_path):
            with patch("src.iterate.polish", return_value=final):
                with patch("src.iterate.rate_video", return_value=mock_rating):
                    with patch("src.iterate.safety_check", return_value=mock_safety):
                        with patch("src.iterate.print_safety_result"):
                            iterate(script, max_iterations=5, min_score=8)

        # Should stop after 1 since pass=True and score >= min_score

    def test_runs_max_iterations_when_never_passes(self, tmp_path):
        script = _make_script(tmp_path)
        _make_draft(tmp_path, script)
        final = self._mock_polish_output(tmp_path, script)

        mock_rating = {"overall_score": 5, "pass": False, "issues": ["blurry"], "suggestions": []}
        mock_safety = {"safe": True, "verdict": "approved", "scores": {}, "flags": [], "details": ""}

        with patch("src.iterate.OUTPUT_DIR", tmp_path):
            with patch("src.iterate.polish", return_value=final) as mock_polish:
                with patch("src.iterate.rate_video", return_value=mock_rating):
                    with patch("src.iterate.safety_check", return_value=mock_safety):
                        with patch("src.iterate.print_safety_result"):
                            iterate(script, max_iterations=3, min_score=8)

        assert mock_polish.call_count == 3

    def test_zero_max_iterations_does_not_raise(self, tmp_path):
        """Bug fix: out must not be unbound when max_iterations=0."""
        script = _make_script(tmp_path)
        _make_draft(tmp_path, script)

        mock_safety = {"safe": True, "verdict": "approved", "scores": {}, "flags": [], "details": ""}

        with patch("src.iterate.OUTPUT_DIR", tmp_path):
            with patch("src.iterate.polish") as mock_polish:
                with patch("src.iterate.rate_video") as mock_rate:
                    with patch("src.iterate.safety_check", return_value=mock_safety):
                        with patch("src.iterate.print_safety_result"):
                            # Should not raise NameError for unbound 'out'
                            result = iterate(script, max_iterations=0)

        mock_polish.assert_not_called()
        mock_rate.assert_not_called()
        assert result is None

    def test_safety_warning_printed_when_unsafe(self, tmp_path, capsys):
        script = _make_script(tmp_path)
        _make_draft(tmp_path, script)
        final = self._mock_polish_output(tmp_path, script)

        mock_rating = {"overall_score": 8, "pass": True, "issues": [], "suggestions": []}
        mock_safety = {
            "safe": False,
            "verdict": "needs_review",
            "scores": {},
            "flags": [],
            "details": "",
        }

        with patch("src.iterate.OUTPUT_DIR", tmp_path):
            with patch("src.iterate.polish", return_value=final):
                with patch("src.iterate.rate_video", return_value=mock_rating):
                    with patch("src.iterate.safety_check", return_value=mock_safety):
                        with patch("src.iterate.print_safety_result"):
                            iterate(script, max_iterations=1)

        captured = capsys.readouterr()
        assert "WARNING" in captured.out or "needs_review" in captured.out
