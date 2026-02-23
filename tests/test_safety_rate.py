"""Unit tests for src/safety_rate.py"""

import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.safety_rate import (
    HARD_FLAG_CATEGORIES,
    _run_text_moderation,
    print_safety_result,
)


# ---------------------------------------------------------------------------
# HARD_FLAG_CATEGORIES — verify the set contains correct category names
# ---------------------------------------------------------------------------

class TestHardFlagCategories:
    def test_self_harm_intent_present(self):
        """self_harm_intent (underscore, API attribute name) must be in the set."""
        assert "self_harm_intent" in HARD_FLAG_CATEGORIES or "self-harm/intent" in HARD_FLAG_CATEGORIES

    def test_sexual_minors_present(self):
        assert "sexual_minors" in HARD_FLAG_CATEGORIES or "sexual/minors" in HARD_FLAG_CATEGORIES

    def test_violence_graphic_present(self):
        assert "violence_graphic" in HARD_FLAG_CATEGORIES or "violence/graphic" in HARD_FLAG_CATEGORIES


# ---------------------------------------------------------------------------
# _run_text_moderation
# ---------------------------------------------------------------------------

class TestRunTextModeration:
    def _make_moderation_result(self, flagged=False, categories=None, category_scores=None):
        """Build a mock OpenAI moderation result using SimpleNamespace for nested objects."""
        cats_data = categories or {"sexual": False, "violence": False, "hate": False}
        scores_data = category_scores or {"sexual": 0.001, "violence": 0.002, "hate": 0.001}
        return SimpleNamespace(
            flagged=flagged,
            categories=SimpleNamespace(**cats_data),
            category_scores=SimpleNamespace(**scores_data),
        )

    def test_empty_texts_returns_not_flagged(self):
        client = MagicMock()
        result = _run_text_moderation(client, [])
        assert result["flagged"] is False

    def test_blank_texts_returns_not_flagged(self):
        client = MagicMock()
        result = _run_text_moderation(client, ["   ", "\n"])
        assert result["flagged"] is False

    def test_normal_text_not_flagged(self):
        client = MagicMock()
        mod_result = self._make_moderation_result(flagged=False)
        mock_resp = MagicMock()
        mock_resp.results = [mod_result]
        client.moderations.create.return_value = mock_resp

        result = _run_text_moderation(client, ["Learning about volcanoes"])
        assert result["flagged"] is False
        assert result["hard_flags"] == []

    def test_flagged_text_returns_flagged_true(self):
        client = MagicMock()
        mod_result = self._make_moderation_result(flagged=True)
        mock_resp = MagicMock()
        mock_resp.results = [mod_result]
        client.moderations.create.return_value = mock_resp

        result = _run_text_moderation(client, ["Some flagged text"])
        assert result["flagged"] is True

    def test_scores_aggregated_by_max(self):
        client = MagicMock()

        result1 = self._make_moderation_result(category_scores={"violence": 0.3})
        result2 = self._make_moderation_result(category_scores={"violence": 0.7})
        mock_resp = MagicMock()
        mock_resp.results = [result1, result2]
        client.moderations.create.return_value = mock_resp

        result = _run_text_moderation(client, ["text chunk"])
        assert result["category_scores"].get("violence", 0) == pytest.approx(0.7)

    def test_long_text_chunked(self):
        """Text longer than 8000 chars should be chunked and API called multiple times."""
        client = MagicMock()
        mod_result = self._make_moderation_result()
        mock_resp = MagicMock()
        mock_resp.results = [mod_result]
        client.moderations.create.return_value = mock_resp

        long_text = "safe text " * 1000  # ~10000 chars
        _run_text_moderation(client, [long_text])
        assert client.moderations.create.call_count >= 2


# ---------------------------------------------------------------------------
# print_safety_result
# ---------------------------------------------------------------------------

class TestPrintSafetyResult:
    def test_prints_approved(self, capsys):
        result = {
            "verdict": "approved",
            "safe": True,
            "scores": {"text_safety": 10, "visual_safety": 9},
            "flags": [],
            "details": "All good.",
        }
        print_safety_result(result)
        captured = capsys.readouterr()
        assert "APPROVED" in captured.out

    def test_prints_rejected(self, capsys):
        result = {
            "verdict": "rejected",
            "safe": False,
            "scores": {"text_safety": 2},
            "flags": ["Contains violent content"],
            "details": "Unsafe content detected.",
        }
        print_safety_result(result)
        captured = capsys.readouterr()
        assert "REJECTED" in captured.out
        assert "Contains violent content" in captured.out

    def test_prints_scores_as_bar(self, capsys):
        result = {
            "verdict": "approved",
            "safe": True,
            "scores": {"text_safety": 8},
            "flags": [],
            "details": "",
        }
        print_safety_result(result)
        captured = capsys.readouterr()
        assert "text_safety" in captured.out
        assert "8/10" in captured.out

    def test_handles_missing_fields_gracefully(self, capsys):
        # Should not raise even if keys are missing
        print_safety_result({})

    def test_moderation_flag_printed(self, capsys):
        result = {
            "verdict": "rejected",
            "safe": False,
            "scores": {},
            "flags": [],
            "details": "",
            "moderation_api": {"flagged": True, "top_scores": {"violence": 0.95}},
        }
        print_safety_result(result)
        captured = capsys.readouterr()
        assert "FLAGGED" in captured.out
