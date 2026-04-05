"""Lightweight i18n — register translations, look up by key + lang."""
from __future__ import annotations

from typing import Any

SUPPORTED_LANGS = ("zh", "en", "ja")
DEFAULT_LANG = "en"

_REGISTRY: dict[str, dict[str, str]] = {}


def register(namespace: str, strings: dict[str, dict[str, str]]) -> None:
    """Register translations under a namespace prefix."""
    for key, langs in strings.items():
        _REGISTRY[f"{namespace}.{key}"] = dict(langs)


def t(key: str, lang: str = DEFAULT_LANG, **kwargs: Any) -> str:
    """Translate a key. Fallback: lang → zh → raw key."""
    entry = _REGISTRY.get(key, {})
    text = entry.get(lang) or entry.get("zh") or key
    return text.format_map(kwargs) if kwargs else text


# Auto-register shared labels on import
from src.core.i18n import shared as _shared  # noqa: F401, E402
