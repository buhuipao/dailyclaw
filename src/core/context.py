"""Application context injected into every plugin."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
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
    wiki_nudge: Callable[[int, str, str], Awaitable[str | None]] | None = field(default=None)
