"""Passive plan reminder — only remind if user hasn't checked in."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def check_needs_reminder(db, user_id: int, tag: str, date: str) -> bool:
    """Return True if user has NOT checked in for this tag today."""
    cursor = await db.conn.execute(
        "SELECT 1 FROM plan_checkins WHERE user_id = ? AND tag = ? AND date = ? LIMIT 1",
        (user_id, tag, date),
    )
    return await cursor.fetchone() is None
