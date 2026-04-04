"""Journal plugin DB interface — wraps core Database for journal-specific operations."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class JournalDB:
    """Thin adapter that exposes journal operations on top of core Database."""

    def __init__(self, db: Any) -> None:
        self._db = db

    async def save_journal_entry(
        self,
        user_id: int,
        date: str,
        category: str,
        content: str,
    ) -> int:
        cursor = await self._db.conn.execute(
            "INSERT INTO journal_entries (user_id, date, category, content) VALUES (?, ?, ?, ?)",
            (user_id, date, category, content),
        )
        await self._db.conn.commit()
        return cursor.lastrowid

    async def get_journal_entries(self, user_id: int, date: str) -> list[dict[str, Any]]:
        cursor = await self._db.conn.execute(
            "SELECT id, user_id, date, category, content, created_at "
            "FROM journal_entries WHERE user_id = ? AND date = ? ORDER BY category",
            (user_id, date),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_journal_range(
        self, user_id: int, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        cursor = await self._db.conn.execute(
            "SELECT id, user_id, date, category, content, created_at "
            "FROM journal_entries "
            "WHERE user_id = ? AND date BETWEEN ? AND ? "
            "ORDER BY date, category",
            (user_id, start_date, end_date),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def save_summary(
        self,
        user_id: int,
        period_type: str,
        period_start: str,
        period_end: str,
        content: str,
    ) -> int:
        cursor = await self._db.conn.execute(
            "INSERT INTO summaries (user_id, period_type, period_start, period_end, content) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, period_type, period_start, period_end, content),
        )
        await self._db.conn.commit()
        return cursor.lastrowid
