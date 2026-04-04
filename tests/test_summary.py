"""Tests for summary generation."""
from __future__ import annotations

import pytest
import pytest_asyncio

from src.journal.summary import generate_summary
from src.storage.db import Database
from src.storage.models import JournalCategory


@pytest_asyncio.fixture
async def db(tmp_path):
    """Legacy db fixture using src.storage.db.Database for these tests."""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path=db_path)
    await database.connect()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_generate_weekly_summary(db, fake_llm):
    for day in range(1, 4):
        date = f"2026-04-0{day}"
        await db.save_journal_entry(1, date, JournalCategory.MORNING, f"Day {day} morning")
        await db.save_journal_entry(1, date, JournalCategory.REFLECTION, f"Day {day} reflection")

    llm = fake_llm(["本周你坚持了3天早起，反思认真。继续保持！"])
    result = await generate_summary(
        db=db, llm=llm, user_id=1,
        period_type="week",
        start_date="2026-04-01",
        end_date="2026-04-07",
    )

    assert "本周" in result


@pytest.mark.asyncio
async def test_generate_summary_no_entries(db, fake_llm):
    llm = fake_llm(["这段时间没有记录。"])
    result = await generate_summary(
        db=db, llm=llm, user_id=1,
        period_type="week",
        start_date="2026-04-01",
        end_date="2026-04-07",
    )

    assert result
