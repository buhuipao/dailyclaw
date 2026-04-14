"""Tests for the wiki plugin."""
from __future__ import annotations

import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio

from src.core.bot import Event
from src.core.context import AppContext
from src.core.db import Database, MigrationRunner

from tests.conftest import FakeLLMService

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
_CORE_MIGRATIONS = str(_SRC_ROOT / "core" / "migrations")
_WIKI_MIGRATIONS = str(_SRC_ROOT / "plugins" / "wiki" / "migrations")
_MEMO_MIGRATIONS = str(_SRC_ROOT / "plugins" / "memo" / "migrations")
_REFLECT_MIGRATIONS = str(_SRC_ROOT / "plugins" / "reflect" / "migrations")
_TRACK_MIGRATIONS = str(_SRC_ROOT / "plugins" / "track" / "migrations")

TZ = ZoneInfo("Asia/Shanghai")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def wiki_db(tmp_path):
    """Provide a Database with wiki + source table migrations applied."""
    db = Database(db_path=str(tmp_path / "wiki_test.db"))
    await db.connect()
    runner = MigrationRunner(db)
    await runner.run("core", _CORE_MIGRATIONS)
    await runner.run("memo", _MEMO_MIGRATIONS)
    await runner.run("reflect", _REFLECT_MIGRATIONS)
    await runner.run("track", _TRACK_MIGRATIONS)
    await runner.run("wiki", _WIKI_MIGRATIONS)
    yield db
    await db.close()


# ---------------------------------------------------------------------------
# Task 8: Schema tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wiki_pages_accepts_inserts(wiki_db):
    """wiki_pages table should exist and accept inserts."""
    await wiki_db.conn.execute(
        "INSERT INTO wiki_pages (user_id, topic, title, content) VALUES (?, ?, ?, ?)",
        (42, "test-topic", "Test Topic", "Some content"),
    )
    await wiki_db.conn.commit()

    cursor = await wiki_db.conn.execute(
        "SELECT * FROM wiki_pages WHERE user_id = 42"
    )
    rows = await cursor.fetchall()
    assert len(rows) == 1
    assert rows[0]["topic"] == "test-topic"
    assert rows[0]["title"] == "Test Topic"


@pytest.mark.asyncio
async def test_wiki_pages_unique_constraint(wiki_db):
    """UNIQUE(user_id, topic) should prevent duplicate inserts."""
    await wiki_db.conn.execute(
        "INSERT INTO wiki_pages (user_id, topic, title, content) VALUES (?, ?, ?, ?)",
        (42, "dup-topic", "Title 1", "Content 1"),
    )
    await wiki_db.conn.commit()

    with pytest.raises(Exception):
        await wiki_db.conn.execute(
            "INSERT INTO wiki_pages (user_id, topic, title, content) VALUES (?, ?, ?, ?)",
            (42, "dup-topic", "Title 2", "Content 2"),
        )


@pytest.mark.asyncio
async def test_wiki_log_accepts_entries(wiki_db):
    """wiki_log table should accept entries."""
    await wiki_db.conn.execute(
        "INSERT INTO wiki_log (user_id, op, detail) VALUES (?, ?, ?)",
        (42, "test_op", "some detail"),
    )
    await wiki_db.conn.commit()

    cursor = await wiki_db.conn.execute(
        "SELECT * FROM wiki_log WHERE user_id = 42"
    )
    rows = await cursor.fetchall()
    assert len(rows) == 1
    assert rows[0]["op"] == "test_op"


# ---------------------------------------------------------------------------
# Task 8: WikiDB tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wikidb_upsert_creates_page(wiki_db):
    """upsert_page should create a new page."""
    from src.plugins.wiki.db import WikiDB

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(
        user_id=1,
        topic="reading",
        title="Reading Notes",
        content="I read a book today.",
        links=["daily-routine"],
        source_delta=3,
    )

    page = await wdb.get_page(1, "reading")
    assert page is not None
    assert page["title"] == "Reading Notes"
    assert page["content"] == "I read a book today."
    assert json.loads(page["links"]) == ["daily-routine"]
    assert page["source_count"] == 3


@pytest.mark.asyncio
async def test_wikidb_upsert_updates_existing(wiki_db):
    """upsert_page should update existing and bump source_count."""
    from src.plugins.wiki.db import WikiDB

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(
        user_id=1,
        topic="reading",
        title="Reading Notes",
        content="Version 1",
        links=[],
        source_delta=3,
    )
    await wdb.upsert_page(
        user_id=1,
        topic="reading",
        title="Reading Notes Updated",
        content="Version 2",
        links=["ideas"],
        source_delta=5,
    )

    page = await wdb.get_page(1, "reading")
    assert page is not None
    assert page["title"] == "Reading Notes Updated"
    assert page["content"] == "Version 2"
    assert page["source_count"] == 8  # 3 + 5


@pytest.mark.asyncio
async def test_wikidb_topic_index(wiki_db):
    """get_topic_index should return user's topics."""
    from src.plugins.wiki.db import WikiDB

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "a-topic", "A Topic", "Content A", [])
    await wdb.upsert_page(1, "b-topic", "B Topic", "Content B", [])
    await wdb.upsert_page(2, "other", "Other User", "Not mine", [])

    index = await wdb.get_topic_index(1)
    assert len(index) == 2
    topics = {i["topic"] for i in index}
    assert topics == {"a-topic", "b-topic"}


@pytest.mark.asyncio
async def test_wikidb_log_op(wiki_db):
    """log_op should write to wiki_log and get_recent_logs should read."""
    from src.plugins.wiki.db import WikiDB

    wdb = WikiDB(wiki_db)
    await wdb.log_op(1, "test", "detail1")
    await wdb.log_op(1, "test", "detail2")

    logs = await wdb.get_recent_logs(1, limit=10)
    assert len(logs) == 2
    assert logs[0]["detail"] == "detail2"  # most recent first
    assert logs[1]["detail"] == "detail1"


# ---------------------------------------------------------------------------
# Task 9: Ingest tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sources_since_reads_messages(wiki_db):
    """fetch_sources_since should read from messages table."""
    from src.plugins.wiki.ingest import fetch_sources_since

    await wiki_db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content, created_at) VALUES (?, ?, ?, ?)",
        (1, "text", "Hello world", "2026-04-10 10:00:00"),
    )
    await wiki_db.conn.commit()

    sources = await fetch_sources_since(wiki_db, 1, None)
    assert len(sources) >= 1
    memo_sources = [s for s in sources if s["source"] == "memos"]
    assert len(memo_sources) == 1
    assert memo_sources[0]["content"] == "Hello world"


@pytest.mark.asyncio
async def test_fetch_sources_since_respects_watermark(wiki_db):
    """fetch_sources_since should only return rows after the watermark."""
    from src.plugins.wiki.ingest import fetch_sources_since

    await wiki_db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content, created_at) VALUES (?, ?, ?, ?)",
        (1, "text", "Old message", "2026-04-01 10:00:00"),
    )
    await wiki_db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content, created_at) VALUES (?, ?, ?, ?)",
        (1, "text", "New message", "2026-04-10 10:00:00"),
    )
    await wiki_db.conn.commit()

    sources = await fetch_sources_since(wiki_db, 1, "2026-04-05 00:00:00")
    memo_sources = [s for s in sources if s["source"] == "memos"]
    assert len(memo_sources) == 1
    assert memo_sources[0]["content"] == "New message"


@pytest.mark.asyncio
async def test_build_ingest_prompt_includes_topics_and_sources():
    """build_ingest_prompt should include topic index and sources."""
    from src.plugins.wiki.ingest import build_ingest_prompt

    topic_index = [
        {"topic": "reading", "title": "Reading Notes", "source_count": 5},
    ]
    sources = [
        {"source": "memos", "time": "2026-04-10", "content": "Read a book", "extra": ""},
    ]

    msgs = build_ingest_prompt(topic_index, sources, "en")
    assert len(msgs) == 2
    assert "reading" in msgs[0]["content"]
    assert "Read a book" in msgs[1]["content"]


class FakeIngestLLM:
    """LLM fake that returns ingest JSON."""

    def __init__(self, response: list[dict]) -> None:
        self._response = response
        self.calls: list[list[dict]] = []

    async def chat(self, messages: list[dict], **kwargs) -> str:
        self.calls.append(messages)
        return json.dumps(self._response, ensure_ascii=False)


@pytest.mark.asyncio
async def test_run_ingest_processes_sources(wiki_db):
    """run_ingest should read sources, call LLM, and write pages."""
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.ingest import run_ingest

    # Insert a source message
    await wiki_db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content, created_at) VALUES (?, ?, ?, ?)",
        (1, "text", "I started learning Python", "2026-04-10 10:00:00"),
    )
    await wiki_db.conn.commit()

    llm = FakeIngestLLM([
        {
            "topic": "learning-python",
            "title": "Learning Python",
            "action": "create",
            "content": "Started learning Python in April.",
            "links": [],
            "reason": "New topic from memo",
        },
    ])

    wdb = WikiDB(wiki_db)
    result = await run_ingest(wiki_db, llm, wdb, 1, "en")

    assert result["created"] == 1
    assert result["updated"] == 0
    assert result["sources"] >= 1

    page = await wdb.get_page(1, "learning-python")
    assert page is not None
    assert page["title"] == "Learning Python"


# ---------------------------------------------------------------------------
# Task 10: Query tests
# ---------------------------------------------------------------------------


class FakeQueryLLM:
    """LLM fake that returns topic picks then an answer."""

    def __init__(self, topic_picks: list[str], answer: str) -> None:
        self._responses = [
            json.dumps(topic_picks),
            answer,
        ]
        self._idx = 0
        self.calls: list[list[dict]] = []

    async def chat(self, messages: list[dict], **kwargs) -> str:
        self.calls.append(messages)
        if self._idx < len(self._responses):
            resp = self._responses[self._idx]
            self._idx += 1
            return resp
        return "default"


@pytest.mark.asyncio
async def test_answer_question_two_stage(wiki_db):
    """answer_question should use two-stage retrieval."""
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.query import answer_question

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "reading", "Reading Notes", "I read 3 books this month.", [])

    llm = FakeQueryLLM(["reading"], "You read 3 books this month.")

    result = await answer_question(llm, wdb, wiki_db, 1, "What did I read?", "en")

    assert "3 books" in result
    assert len(llm.calls) == 2  # pick + answer


@pytest.mark.asyncio
async def test_answer_question_fallback_no_topics(wiki_db):
    """answer_question should fall back when no topics exist."""
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.query import answer_question

    # Insert a message for fallback
    await wiki_db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content, created_at) VALUES (?, ?, ?, ?)",
        (1, "text", "I had coffee today", "2026-04-10 10:00:00"),
    )
    await wiki_db.conn.commit()

    wdb = WikiDB(wiki_db)
    llm = FakeLLMService(responses=["Based on your messages, you had coffee."])

    result = await answer_question(llm, wdb, wiki_db, 1, "What did I drink?", "en")
    assert "coffee" in result


# ---------------------------------------------------------------------------
# Task 11: Nudge tests
# ---------------------------------------------------------------------------


class FakeNudgeLLM:
    """LLM fake for nudge check."""

    def __init__(self, connected: bool, confidence: float, nudge: str) -> None:
        self._response = {
            "connected": connected,
            "confidence": confidence,
            "topic": "reading",
            "nudge": nudge,
        }

    async def chat(self, messages: list[dict], **kwargs) -> str:
        return json.dumps(self._response)


@pytest.mark.asyncio
async def test_nudge_returns_message_on_high_confidence(wiki_db):
    """check_nudge should return message when confidence >= threshold."""
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.nudge import check_nudge

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "reading", "Reading", "I read books.", [])

    llm = FakeNudgeLLM(connected=True, confidence=0.95, nudge="This connects to your reading topic!")

    result = await check_nudge(llm, wdb, 1, "Just finished a chapter", "en")
    assert result is not None
    assert "reading" in result


@pytest.mark.asyncio
async def test_nudge_returns_none_on_low_confidence(wiki_db):
    """check_nudge should return None when confidence < threshold."""
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.nudge import check_nudge

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "reading", "Reading", "I read books.", [])

    llm = FakeNudgeLLM(connected=False, confidence=0.3, nudge="")

    result = await check_nudge(llm, wdb, 1, "Random stuff", "en")
    assert result is None


# ---------------------------------------------------------------------------
# Task 11: Digest tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_digest_generates_from_updated_pages(wiki_db):
    """generate_digest should produce output from recently updated pages."""
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.digest import generate_digest

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "reading", "Reading", "Read 5 books.", [])

    llm = FakeLLMService(responses=["This week you focused on reading."])

    result = await generate_digest(llm, wdb, 1, "en")
    assert result is not None
    assert "reading" in result


@pytest.mark.asyncio
async def test_digest_returns_none_when_empty(wiki_db):
    """generate_digest should return None when no pages updated."""
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.digest import generate_digest

    wdb = WikiDB(wiki_db)
    llm = FakeLLMService(responses=[])

    result = await generate_digest(llm, wdb, 1, "en")
    assert result is None


# ---------------------------------------------------------------------------
# Task 11: Lint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lint_detects_orphans(wiki_db):
    """run_lint should detect orphan pages (no inbound links)."""
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.lint import _build_link_graph, _find_orphans, run_lint

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "a", "Topic A", "Content A", ["b"])  # links to b
    await wdb.upsert_page(1, "b", "Topic B", "Content B", [])  # no outgoing links
    await wdb.upsert_page(1, "c", "Topic C", "Content C", [])  # orphan

    pages = await wdb.get_pages(1, ["a", "b", "c"])
    graph = _build_link_graph(pages)
    orphans = _find_orphans(pages, graph)

    # 'a' has no inbound links (nothing links to 'a')
    # 'b' has inbound from 'a'
    # 'c' has no inbound links
    assert "a" in orphans
    assert "b" not in orphans
    assert "c" in orphans


@pytest.mark.asyncio
async def test_lint_returns_none_for_empty_wiki(wiki_db):
    """run_lint should return None for empty wiki."""
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.lint import run_lint

    wdb = WikiDB(wiki_db)
    llm = FakeLLMService(responses=[])

    result = await run_lint(llm, wdb, 1, "en")
    assert result is None


@pytest.mark.asyncio
async def test_lint_returns_report(wiki_db):
    """run_lint should return a report when wiki has pages."""
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.lint import run_lint

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "a", "Topic A", "Content A", [])

    llm = FakeLLMService(responses=["Orphan: topic a has no inbound links."])

    result = await run_lint(llm, wdb, 1, "en")
    assert result is not None
    assert "orphan" in result.lower() or "Orphan" in result


# ---------------------------------------------------------------------------
# Task 12: Command tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_topics_shows_index(wiki_db, fake_bot, fake_scheduler):
    """cmd_topics should display the topic index."""
    from src.plugins.wiki.commands import cmd_topics
    from src.plugins.wiki.db import WikiDB

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "reading", "Reading Notes", "Content", [], source_delta=5)

    ctx = AppContext(
        db=wiki_db,
        llm=FakeLLMService(),
        bot=fake_bot,
        scheduler=fake_scheduler,
        config={},
        tz=TZ,
    )

    handler = cmd_topics(ctx)
    event = Event(user_id=1, chat_id=1, lang="en")
    result = await handler(event)

    assert result is not None
    assert "reading" in result
    assert "Reading Notes" in result
    assert "5 sources" in result


@pytest.mark.asyncio
async def test_cmd_topics_empty(wiki_db, fake_bot, fake_scheduler):
    """cmd_topics should show empty message when no topics."""
    from src.plugins.wiki.commands import cmd_topics

    ctx = AppContext(
        db=wiki_db,
        llm=FakeLLMService(),
        bot=fake_bot,
        scheduler=fake_scheduler,
        config={},
        tz=TZ,
    )

    handler = cmd_topics(ctx)
    event = Event(user_id=1, chat_id=1, lang="en")
    result = await handler(event)

    assert result is not None
    assert "empty" in result.lower()


@pytest.mark.asyncio
async def test_cmd_topic_shows_page(wiki_db, fake_bot, fake_scheduler):
    """cmd_topic should display the full page content."""
    from src.plugins.wiki.commands import cmd_topic
    from src.plugins.wiki.db import WikiDB

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "reading", "Reading Notes", "I read 3 books.", ["daily-routine"])

    ctx = AppContext(
        db=wiki_db,
        llm=FakeLLMService(),
        bot=fake_bot,
        scheduler=fake_scheduler,
        config={},
        tz=TZ,
    )

    handler = cmd_topic(ctx)
    event = Event(user_id=1, chat_id=1, text="reading", lang="en")
    result = await handler(event)

    assert result is not None
    assert "Reading Notes" in result
    assert "I read 3 books." in result
    assert "daily-routine" in result


@pytest.mark.asyncio
async def test_cmd_topic_not_found(wiki_db, fake_bot, fake_scheduler):
    """cmd_topic should show not found for missing topic."""
    from src.plugins.wiki.commands import cmd_topic

    ctx = AppContext(
        db=wiki_db,
        llm=FakeLLMService(),
        bot=fake_bot,
        scheduler=fake_scheduler,
        config={},
        tz=TZ,
    )

    handler = cmd_topic(ctx)
    event = Event(user_id=1, chat_id=1, text="nonexistent", lang="en")
    result = await handler(event)

    assert result is not None
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_cmd_ask_usage(wiki_db, fake_bot, fake_scheduler):
    """cmd_ask without text should show usage."""
    from src.plugins.wiki.commands import cmd_ask

    ctx = AppContext(
        db=wiki_db,
        llm=FakeLLMService(),
        bot=fake_bot,
        scheduler=fake_scheduler,
        config={},
        tz=TZ,
    )

    handler = cmd_ask(ctx)
    event = Event(user_id=1, chat_id=1, text=None, lang="en")
    result = await handler(event)

    assert result is not None
    assert "usage" in result.lower()
