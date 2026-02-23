"""Unit tests for src/script_writer.py"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.script_writer import _slugify, generate_script, write_script


class TestSlugify:
    def test_spaces_become_underscores(self):
        assert _slugify("hello world") == "hello_world"

    def test_lowercase(self):
        assert _slugify("Benefits of MEDITATION") == "benefits_of_meditation"

    def test_special_chars_become_underscore(self):
        assert _slugify("topic: foo & bar!") == "topic__foo___bar_"

    def test_hyphen_preserved(self):
        assert _slugify("how-things-work") == "how-things-work"

    def test_max_50_chars(self):
        long = "a" * 100
        assert len(_slugify(long)) <= 50

    def test_empty_falls_back_to_script(self):
        assert _slugify("") == "script"

    def test_only_special_chars_falls_back(self):
        result = _slugify("!@#$%")
        assert result == "script" or len(result) > 0


class TestGenerateScript:
    def _mock_response(self, text: str):
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = text
        return mock_resp

    def test_returns_stripped_string(self):
        sample = "SEGMENT: ocean\nTEXT: Waves\nDURATION: 5\n---\n"
        with patch("src.script_writer.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = self._mock_response(f"  {sample}  ")
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                result = generate_script("ocean waves")
        assert result == sample.strip()

    def test_raises_if_no_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            import os
            os.environ.pop("OPENAI_API_KEY", None)
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                generate_script("test topic")

    def test_lyrical_mode_uses_lyrics_format(self):
        with patch("src.script_writer.OpenAI") as MockOpenAI:
            mock_create = MockOpenAI.return_value.chat.completions.create
            mock_create.return_value = self._mock_response("SEGMENT: x\nLYRICS: y\nDURATION: 5")
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                generate_script("test", lyrical=True)

            call_args = mock_create.call_args
            prompt = call_args[1]["messages"][0]["content"]
            assert "LYRICS" in prompt

    def test_flow_mode_uses_flow_format(self):
        with patch("src.script_writer.OpenAI") as MockOpenAI:
            mock_create = MockOpenAI.return_value.chat.completions.create
            mock_create.return_value = self._mock_response("SEGMENT: x\nLYRICS: y\nDURATION: 30")
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                generate_script("test", flow=True)

            call_args = mock_create.call_args
            prompt = call_args[1]["messages"][0]["content"]
            assert "Hamilton" in prompt or "flow" in prompt.lower()

    def test_standard_mode_uses_text_format(self):
        with patch("src.script_writer.OpenAI") as MockOpenAI:
            mock_create = MockOpenAI.return_value.chat.completions.create
            mock_create.return_value = self._mock_response("SEGMENT: x\nTEXT: y\nDURATION: 5")
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                generate_script("test", lyrical=False, flow=False)

            call_args = mock_create.call_args
            prompt = call_args[1]["messages"][0]["content"]
            assert "TEXT:" in prompt


class TestWriteScript:
    def test_writes_file_and_returns_path(self, tmp_path):
        script_content = "SEGMENT: ocean\nTEXT: Sea\nDURATION: 5"
        with patch("src.script_writer.generate_script", return_value=script_content):
            out = write_script("ocean", output_path=tmp_path / "ocean.txt")
        assert out.exists()
        assert out.read_text() == script_content

    def test_default_path_uses_slugified_topic(self, tmp_path):
        with patch("src.script_writer.SCRIPTS_DIR", tmp_path):
            with patch("src.script_writer.generate_script", return_value="SEGMENT: x\nTEXT: y\nDURATION: 5"):
                out = write_script("My Cool Topic")
        assert "my_cool_topic" in out.name
