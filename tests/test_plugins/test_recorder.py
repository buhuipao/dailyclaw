"""Tests for the recorder plugin."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio

from src.core.db import Database, MigrationRunner
from src.core.bot import Event

# Migration directories
_SRC_ROOT = Path(__file__).parent.parent.parent / "src"
_RECORDER_MIGRATIONS = str(_SRC_ROOT / "plugins" / "recorder" / "migrations")
_CORE_MIGRATIONS = str(_SRC_ROOT / "core" / "migrations")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def recorder_db(tmp_path):
    """In-memory Database with core + recorder migrations applied."""
    db_path = str(tmp_path / "recorder_test.db")
    db = Database(db_path=db_path)
    await db.connect()
    runner = MigrationRunner(db)
    await runner.run("core", _CORE_MIGRATIONS)
    await runner.run("recorder", _RECORDER_MIGRATIONS)
    yield db
    await db.close()


class FakeLLM:
    """Minimal LLM stub that returns preset responses for chat()."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._index = 0

    def supports(self, capability: str) -> bool:
        return False

    async def chat(self, messages: list[dict], **kwargs) -> str:
        if self._index < len(self._responses):
            resp = self._responses[self._index]
            self._index += 1
            return resp
        return '{"duplicate": false}'

    async def classify(self, text: str) -> dict:
        return {"category": "other", "summary": text[:50], "tags": ""}

    async def summarize_text(self, text: str, url: str = "") -> str:
        return "test summary"


# ---------------------------------------------------------------------------
# 1. Messages table accepts inserts after migration (incl. deleted_at column)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_messages_table_schema(recorder_db):
    """Messages table should be created with all columns including deleted_at."""
    db = recorder_db
    cursor = await db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content) VALUES (?, ?, ?)",
        (111, "text", "test content"),
    )
    await db.conn.commit()
    row_id = cursor.lastrowid
    assert row_id is not None and row_id > 0

    cursor = await db.conn.execute(
        "SELECT id, user_id, msg_type, content, category, metadata, deleted_at, created_at "
        "FROM messages WHERE id = ?",
        (row_id,),
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row["content"] == "test content"
    assert row["deleted_at"] is None  # not deleted by default


@pytest.mark.asyncio
async def test_messages_deleted_at_accepts_value(recorder_db):
    """deleted_at column should accept a timestamp value."""
    db = recorder_db
    cursor = await db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content, deleted_at) VALUES (?, ?, ?, ?)",
        (111, "text", "soft deleted content", "2026-01-01T00:00:00Z"),
    )
    await db.conn.commit()
    row_id = cursor.lastrowid

    cursor = await db.conn.execute(
        "SELECT deleted_at FROM messages WHERE id = ?", (row_id,)
    )
    row = await cursor.fetchone()
    assert row["deleted_at"] == "2026-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# 2. Soft delete works (deleted_at filters out)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_soft_delete_filters_out(recorder_db):
    """Active messages are returned; soft-deleted ones are excluded."""
    db = recorder_db
    # Insert one active and one soft-deleted message for same user
    await db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content) VALUES (?, ?, ?)",
        (222, "text", "active message"),
    )
    await db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content, deleted_at) VALUES (?, ?, ?, ?)",
        (222, "text", "deleted message", "2026-01-01T00:00:00Z"),
    )
    await db.conn.commit()

    cursor = await db.conn.execute(
        "SELECT content FROM messages WHERE user_id = ? AND deleted_at IS NULL",
        (222,),
    )
    rows = await cursor.fetchall()
    contents = [r["content"] for r in rows]

    assert "active message" in contents
    assert "deleted message" not in contents


# ---------------------------------------------------------------------------
# 3. Message queue table works
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_message_queue_insert_and_status(recorder_db):
    """message_queue table should accept inserts and status updates."""
    db = recorder_db
    payload = json.dumps({"text": "hello"}, ensure_ascii=False)

    cursor = await db.conn.execute(
        "INSERT INTO message_queue (user_id, chat_id, msg_type, payload) VALUES (?, ?, ?, ?)",
        (333, 9001, "text", payload),
    )
    await db.conn.commit()
    queue_id = cursor.lastrowid
    assert queue_id > 0

    # Verify default status
    cursor = await db.conn.execute(
        "SELECT status, attempts, last_error FROM message_queue WHERE id = ?",
        (queue_id,),
    )
    row = await cursor.fetchone()
    assert row["status"] == "pending"
    assert row["attempts"] == 0

    # Mark as failed
    await db.conn.execute(
        "UPDATE message_queue SET status = 'failed', attempts = 1, last_error = 'test error' WHERE id = ?",
        (queue_id,),
    )
    await db.conn.commit()

    cursor = await db.conn.execute(
        "SELECT status, attempts, last_error FROM message_queue WHERE id = ?",
        (queue_id,),
    )
    row = await cursor.fetchone()
    assert row["status"] == "failed"
    assert row["attempts"] == 1
    assert row["last_error"] == "test error"


# ---------------------------------------------------------------------------
# 4. Dedup detects similar messages (mock LLM returning duplicate)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dedup_detects_duplicate(recorder_db):
    """check_dedup returns a dict when LLM says it's a duplicate."""
    from src.plugins.recorder.dedup import check_dedup

    db = recorder_db
    # Insert an existing message
    cursor = await db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content) VALUES (?, ?, ?)",
        (444, "text", "今天读了一本书，很有收获"),
    )
    await db.conn.commit()
    existing_id = cursor.lastrowid

    # LLM says it's a duplicate of existing_id with merge action
    dup_response = json.dumps({
        "duplicate": True,
        "duplicate_of": existing_id,
        "action": "merge",
        "merged_content": "今天读了一本书，很有收获，学到了很多",
    })
    llm = FakeLLM([dup_response])

    result = await check_dedup(db, llm, 444, "今天读了一本书，学到了很多")

    assert result is not None
    assert result["duplicate_of"] == existing_id
    assert result["action"] == "merge"
    assert "merged_content" in result


# ---------------------------------------------------------------------------
# 5. Dedup returns None when no duplicate (mock LLM returning not duplicate)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dedup_returns_none_when_not_duplicate(recorder_db):
    """check_dedup returns None when LLM says no duplicate."""
    from src.plugins.recorder.dedup import check_dedup

    db = recorder_db
    # Insert an existing message
    await db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content) VALUES (?, ?, ?)",
        (555, "text", "今天天气很好"),
    )
    await db.conn.commit()

    llm = FakeLLM(['{"duplicate": false}'])

    result = await check_dedup(db, llm, 555, "学习了新知识")

    assert result is None


@pytest.mark.asyncio
async def test_dedup_returns_none_when_no_history(recorder_db):
    """check_dedup returns None when user has no prior messages."""
    from src.plugins.recorder.dedup import check_dedup

    db = recorder_db
    llm = FakeLLM([])  # Will never be called

    result = await check_dedup(db, llm, 999, "brand new user message")

    assert result is None


# ---------------------------------------------------------------------------
# 6. recorder_del validates ID and ownership
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recorder_del_soft_deletes_own_message(recorder_db):
    """recorder_del should soft-delete a message owned by the caller."""
    from src.plugins.recorder.commands import recorder_del

    db = recorder_db
    cursor = await db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content) VALUES (?, ?, ?)",
        (666, "text", "my message"),
    )
    await db.conn.commit()
    msg_id = cursor.lastrowid

    event = Event(user_id=666, chat_id=9001, text=str(msg_id))
    reply = await recorder_del(db, event)

    assert reply is not None
    assert "✅" in reply
    assert str(msg_id) in reply

    cursor = await db.conn.execute(
        "SELECT deleted_at FROM messages WHERE id = ?", (msg_id,)
    )
    row = await cursor.fetchone()
    assert row["deleted_at"] is not None


@pytest.mark.asyncio
async def test_recorder_del_rejects_wrong_owner(recorder_db):
    """recorder_del should refuse to delete another user's message."""
    from src.plugins.recorder.commands import recorder_del

    db = recorder_db
    cursor = await db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content) VALUES (?, ?, ?)",
        (777, "text", "owner's message"),
    )
    await db.conn.commit()
    msg_id = cursor.lastrowid

    # Different user tries to delete it
    event = Event(user_id=888, chat_id=9001, text=str(msg_id))
    reply = await recorder_del(db, event)

    assert reply is not None
    assert "❌" in reply

    # Message should still be active
    cursor = await db.conn.execute(
        "SELECT deleted_at FROM messages WHERE id = ?", (msg_id,)
    )
    row = await cursor.fetchone()
    assert row["deleted_at"] is None


@pytest.mark.asyncio
async def test_recorder_del_invalid_id(recorder_db):
    """recorder_del should return an error for non-numeric IDs."""
    from src.plugins.recorder.commands import recorder_del

    db = recorder_db
    event = Event(user_id=999, chat_id=9001, text="abc")
    reply = await recorder_del(db, event)

    assert reply is not None
    assert "❌" in reply


@pytest.mark.asyncio
async def test_recorder_del_missing_id(recorder_db):
    """recorder_del should return an error when no ID is provided."""
    from src.plugins.recorder.commands import recorder_del

    db = recorder_db
    event = Event(user_id=999, chat_id=9001, text=None)
    reply = await recorder_del(db, event)

    assert reply is not None
    assert "❌" in reply


@pytest.mark.asyncio
async def test_recorder_del_nonexistent_message(recorder_db):
    """recorder_del should return an error for IDs that don't exist."""
    from src.plugins.recorder.commands import recorder_del

    db = recorder_db
    event = Event(user_id=999, chat_id=9001, text="99999")
    reply = await recorder_del(db, event)

    assert reply is not None
    assert "❌" in reply


@pytest.mark.asyncio
async def test_recorder_del_already_deleted(recorder_db):
    """recorder_del should return an error if the message is already deleted."""
    from src.plugins.recorder.commands import recorder_del

    db = recorder_db
    cursor = await db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content, deleted_at) VALUES (?, ?, ?, ?)",
        (100, "text", "already gone", "2026-01-01T00:00:00Z"),
    )
    await db.conn.commit()
    msg_id = cursor.lastrowid

    event = Event(user_id=100, chat_id=9001, text=str(msg_id))
    reply = await recorder_del(db, event)

    assert reply is not None
    assert "❌" in reply
