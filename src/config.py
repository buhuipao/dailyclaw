"""Configuration loading for DailyClaw."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Load .env file — override=True so .env values win over shell env vars
# (e.g. correcting a stale HTTPS_PROXY inherited from the shell profile).
load_dotenv(override=True)


def _resolve_env_vars(value: str) -> str:
    """Replace ${ENV_VAR} patterns with environment variable values."""
    def replace(match: re.Match) -> str:
        var_name = match.group(1)
        result = os.environ.get(var_name, "")
        if not result:
            raise ValueError(f"Environment variable {var_name} is not set")
        return result
    return re.sub(r"\$\{(\w+)}", replace, value)


def _resolve_config(obj: Any) -> Any:
    """Recursively resolve environment variables in config values."""
    if isinstance(obj, str):
        return _resolve_env_vars(obj)
    if isinstance(obj, dict):
        return {k: _resolve_config(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_config(item) for item in obj]
    return obj


def load_config(path: str | None = None) -> dict[str, Any]:
    """Load and validate configuration from YAML file."""
    config_path = path or os.environ.get("CONFIG_PATH", "config.yaml")
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file) as f:
        raw = yaml.safe_load(f)

    config = _resolve_config(raw)

    # Validate required fields
    if not config.get("telegram", {}).get("token"):
        raise ValueError("telegram.token is required")
    llm = config.get("llm", {})
    if not llm.get("text", {}).get("api_key"):
        raise ValueError("llm.text.api_key is required")

    # Vision config is optional — only validate if present
    vision = llm.get("vision")
    if vision:
        if not vision.get("api_key"):
            raise ValueError("llm.vision.api_key is required when vision is configured")
        if not vision.get("base_url"):
            raise ValueError("llm.vision.base_url is required when vision is configured")

    return config
