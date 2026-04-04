"""Application context injected into every plugin."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class AppContext:
    db: Any        # Database
    llm: Any       # LLMService or test fake
    bot: Any       # BotAdapter or test fake
    scheduler: Any  # Scheduler or test fake
    config: dict[str, Any]
    tz: ZoneInfo
