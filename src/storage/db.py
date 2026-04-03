"""SQLite database operations for DailyClaw."""
from __future__ import annotations

import json
from datetime import datetime

import aiosqlite

from .models import (
    JournalCategory,
    JournalEntry,
    Message,
    MessageType,
    PlanCheckIn,
    Summary,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    msg_type TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT,
    metadata TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS plan_checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    date TEXT NOT NULL,
    note TEXT DEFAULT '',
    duration_minutes INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    period_type TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_user_date ON messages(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_journal_user_date ON journal_entries(user_id, date);
CREATE INDEX IF NOT EXISTS idx_checkins_user_tag_date ON plan_checkins(user_id, tag, date);
"""


class Database:
    def __init__(self, db_path: str = "data/dailyclaw.db"):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    @property
    def _conn(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Database.connect() has not been awaited")
        return self._db

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    # --- Messages ---

    async def save_message(
        self,
        user_id: int,
        msg_type: MessageType,
        content: str,
        category: JournalCategory | None = None,
        metadata: str = "",
    ) -> int:
        cursor = await self._conn.execute(
            "INSERT INTO messages (user_id, msg_type, content, category, metadata) VALUES (?, ?, ?, ?, ?)",
            (user_id, msg_type.value, content, category.value if category else None, metadata),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_today_messages(self, user_id: int, today: str) -> list[Message]:
        cursor = await self._conn.execute(
            "SELECT * FROM messages WHERE user_id = ? AND date(created_at) = ? ORDER BY created_at",
            (user_id, today),
        )
        rows = await cursor.fetchall()
        return [_row_to_message(r) for r in rows]

    # --- Journal ---

    async def save_journal_entry(
        self,
        user_id: int,
        date: str,
        category: JournalCategory,
        content: str,
    ) -> int:
        cursor = await self._conn.execute(
            "INSERT INTO journal_entries (user_id, date, category, content) VALUES (?, ?, ?, ?)",
            (user_id, date, category.value, content),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_journal_entries(self, user_id: int, date: str) -> list[JournalEntry]:
        cursor = await self._conn.execute(
            "SELECT * FROM journal_entries WHERE user_id = ? AND date = ? ORDER BY category",
            (user_id, date),
        )
        rows = await cursor.fetchall()
        return [_row_to_journal(r) for r in rows]

    async def get_journal_range(
        self, user_id: int, start_date: str, end_date: str
    ) -> list[JournalEntry]:
        cursor = await self._conn.execute(
            "SELECT * FROM journal_entries WHERE user_id = ? AND date BETWEEN ? AND ? ORDER BY date, category",
            (user_id, start_date, end_date),
        )
        rows = await cursor.fetchall()
        return [_row_to_journal(r) for r in rows]

    # --- Plan Check-ins ---

    async def save_checkin(
        self,
        user_id: int,
        tag: str,
        date: str,
        note: str = "",
        duration_minutes: int = 0,
    ) -> int:
        cursor = await self._conn.execute(
            "INSERT INTO plan_checkins (user_id, tag, date, note, duration_minutes) VALUES (?, ?, ?, ?, ?)",
            (user_id, tag, date, note, duration_minutes),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_checkins_for_date(self, user_id: int, tag: str, date: str) -> list[PlanCheckIn]:
        cursor = await self._conn.execute(
            "SELECT * FROM plan_checkins WHERE user_id = ? AND tag = ? AND date = ?",
            (user_id, tag, date),
        )
        rows = await cursor.fetchall()
        return [_row_to_checkin(r) for r in rows]

    async def get_checkins_range(
        self, user_id: int, tag: str, start_date: str, end_date: str
    ) -> list[PlanCheckIn]:
        cursor = await self._conn.execute(
            "SELECT * FROM plan_checkins WHERE user_id = ? AND tag = ? AND date BETWEEN ? AND ? ORDER BY date",
            (user_id, tag, start_date, end_date),
        )
        rows = await cursor.fetchall()
        return [_row_to_checkin(r) for r in rows]

    # --- Summaries ---

    async def save_summary(
        self,
        user_id: int,
        period_type: str,
        period_start: str,
        period_end: str,
        content: str,
    ) -> int:
        cursor = await self._conn.execute(
            "INSERT INTO summaries (user_id, period_type, period_start, period_end, content) VALUES (?, ?, ?, ?, ?)",
            (user_id, period_type, period_start, period_end, content),
        )
        await self._conn.commit()
        return cursor.lastrowid


# --- Row converters ---

def _row_to_message(row: aiosqlite.Row) -> Message:
    return Message(
        id=row["id"],
        user_id=row["user_id"],
        msg_type=MessageType(row["msg_type"]),
        content=row["content"],
        category=JournalCategory(row["category"]) if row["category"] else None,
        metadata=row["metadata"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_journal(row: aiosqlite.Row) -> JournalEntry:
    return JournalEntry(
        id=row["id"],
        user_id=row["user_id"],
        date=row["date"],
        category=JournalCategory(row["category"]),
        content=row["content"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_checkin(row: aiosqlite.Row) -> PlanCheckIn:
    return PlanCheckIn(
        id=row["id"],
        user_id=row["user_id"],
        tag=row["tag"],
        date=row["date"],
        note=row["note"],
        duration_minutes=row["duration_minutes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
