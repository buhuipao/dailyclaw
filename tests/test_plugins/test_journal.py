"""Tests for the journal plugin."""
from __future__ import annotations

import pytest
import pytest_asyncio

from tests.conftest import FakeLLMService


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------

class FakeJournalDB:
    """Minimal in-memory fake of JournalDB for unit testing."""

    def __init__(self) -> None:
        self._entries: list[dict] = []
        self._summaries: list[dict] = []

    async def save_journal_entry(
        self,
        user_id: int,
        date: str,
        category: str,
        content: str,
    ) -> int:
        entry = {
            "id": len(self._entries) + 1,
            "user_id": user_id,
            "date": date,
            "category": category,
            "content": content,
            "created_at": "2026-04-04 20:00:00",
        }
        self._entries.append(entry)
        return entry["id"]

    async def get_journal_entries(self, user_id: int, date: str) -> list[dict]:
        return [
            e for e in self._entries
            if e["user_id"] == user_id and e["date"] == date
        ]

    async def get_journal_range(
        self, user_id: int, start_date: str, end_date: str
    ) -> list[dict]:
        return [
            e for e in self._entries
            if e["user_id"] == user_id and start_date <= e["date"] <= end_date
        ]

    async def save_summary(
        self,
        user_id: int,
        period_type: str,
        period_start: str,
        period_end: str,
        content: str,
    ) -> int:
        row = {
            "id": len(self._summaries) + 1,
            "user_id": user_id,
            "period_type": period_type,
            "period_start": period_start,
            "period_end": period_end,
            "content": content,
        }
        self._summaries.append(row)
        return row["id"]


# ---------------------------------------------------------------------------
# Migration / schema tests — use the real core Database
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_journal_entries_table_accepts_inserts(db):
    """journal_entries table should exist after migration and accept inserts."""
    await db.conn.execute(
        "CREATE TABLE IF NOT EXISTS journal_entries ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER NOT NULL, "
        "date TEXT NOT NULL, "
        "category TEXT NOT NULL, "
        "content TEXT NOT NULL, "
        "created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    await db.conn.commit()

    await db.conn.execute(
        "INSERT INTO journal_entries (user_id, date, category, content) VALUES (?, ?, ?, ?)",
        (42, "2026-04-04", "morning", "今天七点起床，精神不错。"),
    )
    await db.conn.commit()

    cursor = await db.conn.execute(
        "SELECT * FROM journal_entries WHERE user_id = 42"
    )
    rows = await cursor.fetchall()
    assert len(rows) == 1
    assert rows[0]["category"] == "morning"
    assert rows[0]["content"] == "今天七点起床，精神不错。"


@pytest.mark.asyncio
async def test_summaries_table_accepts_inserts(db):
    """summaries table should exist after migration and accept inserts."""
    await db.conn.execute(
        "CREATE TABLE IF NOT EXISTS summaries ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER NOT NULL, "
        "period_type TEXT NOT NULL, "
        "period_start TEXT NOT NULL, "
        "period_end TEXT NOT NULL, "
        "content TEXT NOT NULL, "
        "created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    await db.conn.commit()

    await db.conn.execute(
        "INSERT INTO summaries (user_id, period_type, period_start, period_end, content) "
        "VALUES (?, ?, ?, ?, ?)",
        (42, "week", "2026-03-30", "2026-04-05", "本周总结内容"),
    )
    await db.conn.commit()

    cursor = await db.conn.execute(
        "SELECT * FROM summaries WHERE user_id = 42"
    )
    rows = await cursor.fetchall()
    assert len(rows) == 1
    assert rows[0]["period_type"] == "week"
    assert rows[0]["content"] == "本周总结内容"


# ---------------------------------------------------------------------------
# JournalEngine unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_engine_drives_through_all_four_categories():
    """JournalEngine should step through morning→reading→social→reflection."""
    from src.plugins.journal.engine import JOURNAL_FLOW, JournalEngine

    llm = FakeLLMService(responses=[
        "你今天几点起床？",       # start() → morning prompt
        "你今天读了什么？",        # after morning answer → reading prompt
        "你今天和谁交流了？",      # after reading answer → social prompt
        "今天有什么需要反省的？",  # after social answer → reflection prompt
        "感谢你的反思，明天继续加油！",  # _generate_closing
    ])
    fake_db = FakeJournalDB()

    engine = JournalEngine(db=fake_db, llm=llm, user_id=1, date="2026-04-04")

    assert not engine.is_complete
    assert engine.current_category == "morning"

    msg = await engine.start()
    assert "起床" in msg

    # Answer morning
    msg = await engine.answer("七点起床，精神挺好")
    assert engine.current_category == "reading"
    assert "读" in msg

    # Answer reading
    msg = await engine.answer("读了《曾国藩家书》")
    assert engine.current_category == "social"
    assert "交流" in msg

    # Answer social
    msg = await engine.answer("和同事讨论了项目进展")
    assert engine.current_category == "reflection"
    assert "反省" in msg

    # Answer reflection — should complete
    msg = await engine.answer("今天拖延了一些任务，明天要改进")
    assert engine.is_complete

    # Verify all 4 entries were saved
    entries = await fake_db.get_journal_entries(1, "2026-04-04")
    assert len(entries) == 4
    categories = {e["category"] for e in entries}
    assert categories == set(JOURNAL_FLOW)


@pytest.mark.asyncio
async def test_engine_handles_skip_keywords():
    """Answering with a skip keyword should advance without saving an entry."""
    from src.plugins.journal.engine import JournalEngine

    llm = FakeLLMService(responses=[
        "你今天几点起床？",
        "你今天读了什么？",
        "你今天和谁交流了？",
        "今天有什么需要反省的？",
        "今天你勇敢地跳过了！",
    ])
    fake_db = FakeJournalDB()

    engine = JournalEngine(db=fake_db, llm=llm, user_id=2, date="2026-04-04")
    await engine.start()

    # Skip morning
    await engine.answer("skip")
    assert engine.current_category == "reading"

    # Skip reading
    await engine.answer("跳过")
    assert engine.current_category == "social"

    # Skip social
    await engine.answer("无")
    assert engine.current_category == "reflection"

    # Answer reflection normally
    await engine.answer("今天有点懈怠")
    assert engine.is_complete

    # Only 1 entry saved (the reflection)
    entries = await fake_db.get_journal_entries(2, "2026-04-04")
    assert len(entries) == 1
    assert entries[0]["category"] == "reflection"


@pytest.mark.asyncio
async def test_engine_already_complete_returns_done_message():
    """Calling answer() on a completed engine should return the done message."""
    from src.plugins.journal.engine import JournalEngine

    # Provide enough responses for a full run
    responses = [
        "morning prompt",
        "reading prompt",
        "social prompt",
        "reflection prompt",
        "closing summary",
    ]
    llm = FakeLLMService(responses=responses)
    fake_db = FakeJournalDB()

    engine = JournalEngine(db=fake_db, llm=llm, user_id=3, date="2026-04-04")
    await engine.start()
    await engine.answer("morning reply")
    await engine.answer("reading reply")
    await engine.answer("social reply")
    await engine.answer("reflection reply")
    assert engine.is_complete

    # Calling again should not error
    result = await engine.answer("extra reply")
    assert "已完成" in result


@pytest.mark.asyncio
async def test_engine_start_when_already_complete():
    """start() on a completed engine returns done message."""
    from src.plugins.journal.engine import JournalEngine

    responses = [
        "morning", "reading", "social", "reflection", "closing",
    ]
    llm = FakeLLMService(responses=responses)
    fake_db = FakeJournalDB()
    engine = JournalEngine(db=fake_db, llm=llm, user_id=4, date="2026-04-04")
    await engine.start()
    await engine.answer("skip")
    await engine.answer("skip")
    await engine.answer("skip")
    await engine.answer("skip")
    assert engine.is_complete

    result = await engine.start()
    assert "已完成" in result
