"""Data models for DailyClaw storage."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    TEXT = "text"
    PHOTO = "photo"
    VOICE = "voice"
    LINK = "link"


class JournalCategory(str, Enum):
    """曾国藩式日记分类"""
    MORNING = "morning"       # 晨起
    READING = "reading"       # 读书/所阅
    SOCIAL = "social"         # 待人接物
    REFLECTION = "reflection" # 反省


CATEGORY_LABELS: dict[JournalCategory, str] = {
    JournalCategory.MORNING: "晨起",
    JournalCategory.READING: "所阅",
    JournalCategory.SOCIAL: "待人接物",
    JournalCategory.REFLECTION: "反省",
}


@dataclass(frozen=True)
class Message:
    """A raw message sent to the bot."""
    id: int
    user_id: int
    msg_type: MessageType
    content: str
    category: JournalCategory | None
    created_at: datetime
    metadata: str = ""  # JSON string for extra data (file_id, url, etc.)


@dataclass(frozen=True)
class JournalEntry:
    """A structured daily journal entry."""
    id: int
    user_id: int
    date: str  # YYYY-MM-DD
    category: JournalCategory
    content: str
    created_at: datetime


@dataclass(frozen=True)
class PlanCheckIn:
    """A check-in record for a plan."""
    id: int
    user_id: int
    tag: str  # matches config plan tag
    date: str  # YYYY-MM-DD
    note: str
    duration_minutes: int
    created_at: datetime


@dataclass(frozen=True)
class Summary:
    """Generated summary (weekly/monthly/quarterly/yearly)."""
    id: int
    user_id: int
    period_type: str  # week, month, quarter, year
    period_start: str  # YYYY-MM-DD
    period_end: str    # YYYY-MM-DD
    content: str
    created_at: datetime
