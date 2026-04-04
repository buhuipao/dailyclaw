"""Tests for the journal engine."""
from __future__ import annotations

import pytest
import pytest_asyncio

from src.journal.engine import JournalEngine
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
async def test_start_session_returns_first_prompt(db, fake_llm):
    llm = fake_llm(["今天几点起床的？精神状态怎么样？"])
    engine = JournalEngine(db=db, llm=llm, user_id=1, date="2026-04-03")
    result = await engine.start()
    assert result
    assert engine.current_category == JournalCategory.MORNING


@pytest.mark.asyncio
async def test_answer_saves_entry_and_advances(db, fake_llm):
    llm = fake_llm([
        "早起 prompt",
        "今天读了什么好文章？",
    ])
    engine = JournalEngine(db=db, llm=llm, user_id=1, date="2026-04-03")
    await engine.start()
    result = await engine.answer("7点起的，精神不错")
    entries = await db.get_journal_entries(1, "2026-04-03")
    assert len(entries) == 1
    assert entries[0].category == JournalCategory.MORNING
    assert "7点起的" in entries[0].content
    assert engine.current_category == JournalCategory.READING
    assert result


@pytest.mark.asyncio
async def test_full_session_completes_all_four(db, fake_llm):
    llm = fake_llm([
        "晨起 prompt",
        "所阅 prompt",
        "待人接物 prompt",
        "反省 prompt",
        "今日总结：做得不错！",
    ])
    engine = JournalEngine(db=db, llm=llm, user_id=1, date="2026-04-03")
    await engine.start()
    await engine.answer("7点起床")
    await engine.answer("看了一篇分布式系统文章")
    await engine.answer("和同事讨论了架构")
    result = await engine.answer("今天有点拖延")
    assert engine.is_complete
    entries = await db.get_journal_entries(1, "2026-04-03")
    assert len(entries) == 4
    categories = [e.category for e in entries]
    assert JournalCategory.MORNING in categories
    assert JournalCategory.READING in categories
    assert JournalCategory.SOCIAL in categories
    assert JournalCategory.REFLECTION in categories


@pytest.mark.asyncio
async def test_skip_category(db, fake_llm):
    llm = fake_llm([
        "晨起 prompt",
        "所阅 prompt",
    ])
    engine = JournalEngine(db=db, llm=llm, user_id=1, date="2026-04-03")
    await engine.start()
    result = await engine.answer("跳过")
    entries = await db.get_journal_entries(1, "2026-04-03")
    assert len(entries) == 0
    assert engine.current_category == JournalCategory.READING
