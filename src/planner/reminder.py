"""Passive plan reminder — only remind if user hasn't checked in."""
from __future__ import annotations

import logging

from ..storage.db import Database

logger = logging.getLogger(__name__)


async def check_needs_reminder(db: Database, user_id: int, tag: str, date: str) -> bool:
    """Return True if user has NOT checked in for this tag today."""
    checkins = await db.get_checkins_for_date(user_id, tag, date)
    return len(checkins) == 0
