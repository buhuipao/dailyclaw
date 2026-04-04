"""Tests for passive plan reminders."""
from __future__ import annotations

import pytest
import pytest_asyncio

from src.planner.reminder import check_needs_reminder
from src.storage.db import Database


@pytest_asyncio.fixture
async def db(tmp_path):
    """Legacy db fixture using src.storage.db.Database for these tests."""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path=db_path)
    await database.connect()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_needs_reminder_when_no_checkin(db):
    result = await check_needs_reminder(db, user_id=1, tag="ielts", date="2026-04-03")
    assert result is True


@pytest.mark.asyncio
async def test_no_reminder_when_already_checked_in(db):
    await db.save_checkin(user_id=1, tag="ielts", date="2026-04-03", note="done")
    result = await check_needs_reminder(db, user_id=1, tag="ielts", date="2026-04-03")
    assert result is False


@pytest.mark.asyncio
async def test_needs_reminder_different_tag(db):
    await db.save_checkin(user_id=1, tag="workout", date="2026-04-03", note="ran")
    result = await check_needs_reminder(db, user_id=1, tag="ielts", date="2026-04-03")
    assert result is True
