"""Unit tests for src/polish.py"""

import pytest

from src.polish import _wrap_text_at_words


class TestWrapTextAtWords:
    def test_short_text_not_wrapped(self):
        result = _wrap_text_at_words("Hello world", max_chars=25)
        assert result == "Hello world"
        assert "\n" not in result

    def test_long_text_wrapped_at_word_boundary(self):
        text = "The quick brown fox jumps over the lazy dog and keeps running"
        result = _wrap_text_at_words(text, max_chars=20)
        lines = result.split("\n")
        for line in lines:
            assert len(line) <= 20

    def test_single_very_long_word_not_broken(self):
        # A single word longer than max_chars goes on its own line
        text = "supercalifragilisticexpialidocious"
        result = _wrap_text_at_words(text, max_chars=10)
        assert "supercalifragilisticexpialidocious" in result

    def test_empty_string(self):
        result = _wrap_text_at_words("", max_chars=20)
        assert result == ""

    def test_exact_boundary(self):
        # 10 chars exactly fits max_chars=10
        result = _wrap_text_at_words("1234567890", max_chars=10)
        assert result == "1234567890"
        assert "\n" not in result

    def test_multiple_lines_produced(self):
        text = "word " * 20  # 100 chars
        result = _wrap_text_at_words(text.strip(), max_chars=15)
        lines = result.split("\n")
        assert len(lines) > 1

    def test_preserves_all_words(self):
        text = "alpha beta gamma delta epsilon"
        result = _wrap_text_at_words(text, max_chars=12)
        # All words should be present in the result
        for word in text.split():
            assert word in result
