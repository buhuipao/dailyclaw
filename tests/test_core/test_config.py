"""Tests for src/config.py — validates new llm.text/llm.vision config structure."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from src.config import load_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(tmp_path: Path, data: dict) -> str:
    """Write a YAML config dict to a temp file and return its path."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(data, allow_unicode=True))
    return str(config_file)


def _base_config() -> dict:
    """Return a minimal valid config dict (no env-var placeholders)."""
    return {
        "telegram": {
            "token": "test-telegram-token",
            "allowed_user_ids": [12345],
        },
        "llm": {
            "text": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-test-key",
                "model": "gpt-4o-mini",
            },
        },
        "timezone": "Asia/Shanghai",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoadConfigValid:
    def test_minimal_config_loads(self, tmp_path: Path) -> None:
        """New llm.text.api_key structure loads without error."""
        config_path = _write_config(tmp_path, _base_config())
        config = load_config(config_path)

        assert config["telegram"]["token"] == "test-telegram-token"
        assert config["llm"]["text"]["api_key"] == "sk-test-key"
        assert config["llm"]["text"]["model"] == "gpt-4o-mini"

    def test_config_with_vision_loads(self, tmp_path: Path) -> None:
        """Config with llm.vision section loads correctly."""
        data = _base_config()
        data["llm"]["vision"] = {
            "base_url": "https://vision.example.com/v1",
            "api_key": "vision-key",
            "model": "doubao-seed",
        }
        config_path = _write_config(tmp_path, data)
        config = load_config(config_path)

        assert config["llm"]["vision"]["api_key"] == "vision-key"
        assert config["llm"]["vision"]["base_url"] == "https://vision.example.com/v1"

    def test_plugins_section_preserved(self, tmp_path: Path) -> None:
        """Plugin-specific config is passed through unchanged."""
        data = _base_config()
        data["plugins"] = {
            "recorder": {"dedup_window": 10},
            "journal": {"evening_prompt_time": "21:30"},
        }
        config_path = _write_config(tmp_path, data)
        config = load_config(config_path)

        assert config["plugins"]["recorder"]["dedup_window"] == 10
        assert config["plugins"]["journal"]["evening_prompt_time"] == "21:30"

    def test_env_var_substitution(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """${ENV_VAR} placeholders are resolved from environment."""
        monkeypatch.setenv("TEST_BOT_TOKEN", "token-from-env")
        monkeypatch.setenv("TEST_LLM_KEY", "key-from-env")

        data = {
            "telegram": {"token": "${TEST_BOT_TOKEN}", "allowed_user_ids": [1]},
            "llm": {
                "text": {
                    "base_url": "https://api.openai.com/v1",
                    "api_key": "${TEST_LLM_KEY}",
                    "model": "gpt-4o-mini",
                }
            },
            "timezone": "UTC",
        }
        config_path = _write_config(tmp_path, data)
        config = load_config(config_path)

        assert config["telegram"]["token"] == "token-from-env"
        assert config["llm"]["text"]["api_key"] == "key-from-env"


class TestLoadConfigMissingRequired:
    def test_missing_telegram_token_raises(self, tmp_path: Path) -> None:
        """Missing telegram.token raises ValueError."""
        data = _base_config()
        data["telegram"]["token"] = ""
        config_path = _write_config(tmp_path, data)

        with pytest.raises(ValueError, match="telegram.token"):
            load_config(config_path)

    def test_missing_llm_text_api_key_raises(self, tmp_path: Path) -> None:
        """Missing llm.text.api_key raises ValueError with clear message."""
        data = _base_config()
        data["llm"]["text"]["api_key"] = ""
        config_path = _write_config(tmp_path, data)

        with pytest.raises(ValueError, match="llm.text.api_key"):
            load_config(config_path)

    def test_missing_llm_text_section_raises(self, tmp_path: Path) -> None:
        """Missing llm.text section entirely raises ValueError."""
        data = _base_config()
        del data["llm"]["text"]
        config_path = _write_config(tmp_path, data)

        with pytest.raises(ValueError, match="llm.text.api_key"):
            load_config(config_path)

    def test_missing_llm_section_raises(self, tmp_path: Path) -> None:
        """Missing llm section entirely raises ValueError."""
        data = _base_config()
        del data["llm"]
        config_path = _write_config(tmp_path, data)

        with pytest.raises(ValueError, match="llm.text.api_key"):
            load_config(config_path)

    def test_vision_missing_api_key_raises(self, tmp_path: Path) -> None:
        """llm.vision present but missing api_key raises ValueError."""
        data = _base_config()
        data["llm"]["vision"] = {
            "base_url": "https://vision.example.com/v1",
            "api_key": "",
            "model": "doubao-seed",
        }
        config_path = _write_config(tmp_path, data)

        with pytest.raises(ValueError, match="llm.vision.api_key"):
            load_config(config_path)

    def test_vision_missing_base_url_raises(self, tmp_path: Path) -> None:
        """llm.vision present but missing base_url raises ValueError."""
        data = _base_config()
        data["llm"]["vision"] = {
            "api_key": "vision-key",
            "model": "doubao-seed",
        }
        config_path = _write_config(tmp_path, data)

        with pytest.raises(ValueError, match="llm.vision.base_url"):
            load_config(config_path)

    def test_config_file_not_found_raises(self, tmp_path: Path) -> None:
        """Non-existent config path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config(str(tmp_path / "nonexistent.yaml"))
