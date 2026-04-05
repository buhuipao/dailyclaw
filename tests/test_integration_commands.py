"""End-to-end integration tests for all plugin commands and conversation flows.

Uses a real SQLite database and fake LLM/bot/scheduler, exercising the full
command→handler→db→response pipeline for every registered command.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio

from src.core.bot import Command, ConversationFlow, Event
from src.core.context import AppContext
from src.core.db import Database, MigrationRunner

from tests.conftest import FakeBotAdapter, FakeLLMService, FakeScheduler

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "src" / "plugins"
CORE_MIGRATIONS = str(Path(__file__).resolve().parent.parent / "src" / "core" / "migrations")
TZ = ZoneInfo("Asia/Shanghai")
LANG = "zh"  # Tests assert Chinese strings


def _ev(user_id: int, chat_id: int | None = None, text: str | None = None) -> Event:
    """Create an Event with default lang=zh for test assertions."""
    return Event(user_id=user_id, chat_id=chat_id or user_id, text=text, lang=LANG)


# ---------------------------------------------------------------------------
# Shared fixture — full DB with all core + plugin migrations
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def full_ctx(tmp_path):
    """AppContext with all migrations applied (core + all plugins)."""
    from src.core.plugin import PluginRegistry

    db_path = str(tmp_path / "integration_cmd.db")
    db = Database(db_path=db_path)
    await db.connect()

    runner = MigrationRunner(db)
    await runner.run("core", CORE_MIGRATIONS)

    llm = FakeLLMService()
    bot = FakeBotAdapter()
    scheduler = FakeScheduler()
    config = {
        "plugins": {
            "recorder": {},
            "journal": {"remind_hour": 21, "remind_minute": 0},
            "planner": {},
        }
    }

    registry = PluginRegistry(
        db=db, llm=llm, bot=bot, scheduler=scheduler, config=config, tz=TZ,
    )
    plugins = await registry.discover(str(PLUGINS_DIR))

    ctx = AppContext(db=db, llm=llm, bot=bot, scheduler=scheduler, config=config, tz=TZ)

    yield ctx, plugins, registry

    await registry.shutdown_all()
    await db.close()


def _find_handler(plugins, cmd_name: str):
    """Find a command handler by name across all plugins."""
    for plugin in plugins:
        for cmd in plugin.get_commands():
            if cmd.name == cmd_name:
                return cmd.handler
    raise KeyError(f"Command {cmd_name!r} not found")


def _find_conversation(plugins, conv_name: str) -> ConversationFlow:
    """Find a conversation flow by name across all plugins."""
    for plugin in plugins:
        for conv in plugin.get_conversations():
            if conv.name == conv_name:
                return conv
    raise KeyError(f"Conversation {conv_name!r} not found")


# ===========================================================================
# 1. JOURNAL CONVERSATION FLOW — the main fix
# ===========================================================================


class TestJournalConversationFlow:
    """Verify the full journal_start → answer → ... → complete flow."""

    @pytest.mark.asyncio
    async def test_conversation_flow_has_entry_handler(self, full_ctx):
        """ConversationFlow should carry entry_handler (not just entry_command)."""
        _ctx, plugins, _reg = full_ctx
        conv = _find_conversation(plugins, "journal_reflection")

        assert conv.entry_command == "journal_start"
        assert conv.entry_handler is not None
        assert callable(conv.entry_handler)
        assert conv.cancel_command == "journal_cancel"

    @pytest.mark.asyncio
    async def test_journal_start_returns_prompt(self, full_ctx):
        """cmd_journal_start should create a session and return the LLM prompt."""
        ctx, plugins, _reg = full_ctx
        conv = _find_conversation(plugins, "journal_reflection")

        event = _ev(100)
        result = await conv.entry_handler(event)

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_journal_start_duplicate_session_blocked(self, full_ctx):
        """Starting a second session should return a warning, not crash."""
        _ctx, plugins, _reg = full_ctx
        conv = _find_conversation(plugins, "journal_reflection")

        event = _ev(200)
        await conv.entry_handler(event)
        second = await conv.entry_handler(event)

        assert "正在进行" in second

        # Cleanup session
        cancel = _find_handler(plugins, "journal_cancel")
        await cancel(event)

    @pytest.mark.asyncio
    async def test_journal_full_flow_four_answers(self, full_ctx):
        """Full 4-step journal flow: start → 4 answers → completion tuple."""
        ctx, plugins, _reg = full_ctx
        # Provide enough LLM responses for the whole flow
        ctx.llm._responses = [
            "你今天几点起床？",       # start
            "你今天读了什么？",        # after morning
            "你今天和谁交流了？",      # after reading
            "今天有什么需要反省的？",  # after social
            "辛苦了，明天继续加油！",  # closing
        ]
        ctx.llm._call_index = 0

        conv = _find_conversation(plugins, "journal_reflection")
        state_handler = list(conv.states.values())[0]

        event = _ev(300)

        # Entry
        prompt = await conv.entry_handler(event)
        assert isinstance(prompt, str)

        # Answer 1-3: should return str (stay in conversation)
        for answer_text in ["七点起", "读了曾国藩家书", "和同事交流项目"]:
            event_with_text = _ev(300, text=answer_text)
            result = await state_handler(event_with_text)
            assert isinstance(result, str), f"Expected str, got {type(result)}: {result}"

        # Answer 4 (final): should return (str, True) — end signal
        final_event = _ev(300, text="今天有些拖延")
        result = await state_handler(final_event)

        assert isinstance(result, tuple), f"Expected tuple, got {type(result)}: {result}"
        text, is_end = result
        assert isinstance(text, str)
        assert is_end is True

        # Verify entries saved
        cursor = await ctx.db.conn.execute(
            "SELECT category FROM journal_entries WHERE user_id = 300 ORDER BY id"
        )
        rows = await cursor.fetchall()
        categories = [r[0] for r in rows]
        assert categories == ["morning", "reading", "social", "reflection"]

    @pytest.mark.asyncio
    async def test_journal_answer_no_session_returns_none(self, full_ctx):
        """journal_answer_handler returns None when no session exists."""
        _ctx, plugins, _reg = full_ctx
        conv = _find_conversation(plugins, "journal_reflection")
        state_handler = list(conv.states.values())[0]

        event = _ev(999, text="random message")
        result = await state_handler(event)

        assert result is None

    @pytest.mark.asyncio
    async def test_journal_cancel_clears_session(self, full_ctx):
        """journal_cancel should remove active session."""
        _ctx, plugins, _reg = full_ctx
        conv = _find_conversation(plugins, "journal_reflection")
        state_handler = list(conv.states.values())[0]
        cancel = _find_handler(plugins, "journal_cancel")

        event = _ev(400)
        await conv.entry_handler(event)

        cancel_reply = await cancel(event)
        assert "已取消" in cancel_reply

        # After cancel, answer handler should return None
        result = await state_handler(_ev(400, text="hello"))
        assert result is None


# ===========================================================================
# 2. PLANNER LIST — enhanced detail output
# ===========================================================================


class TestPlannerListDetail:
    """Verify planner_list shows schedule, remind time, and recent check-ins."""

    @pytest.mark.asyncio
    async def test_list_shows_schedule_and_remind_time(self, full_ctx):
        """planner_list should include frequency and remind time."""
        ctx, plugins, _reg = full_ctx

        await ctx.db.conn.execute(
            "INSERT INTO plans (user_id, tag, name, schedule, remind_time) VALUES (?, ?, ?, ?, ?)",
            (1, "ielts", "每天学雅思", "daily", "20:00"),
        )
        await ctx.db.conn.commit()

        handler = _find_handler(plugins, "planner_list")
        reply = await handler(_ev(1))

        assert "每天学雅思" in reply
        assert "[ielts]" in reply
        assert "每天" in reply
        assert "20:00" in reply

    @pytest.mark.asyncio
    async def test_list_shows_weekly_schedule(self, full_ctx):
        """planner_list shows day names for weekly schedules."""
        ctx, plugins, _reg = full_ctx

        await ctx.db.conn.execute(
            "INSERT INTO plans (user_id, tag, name, schedule, remind_time) VALUES (?, ?, ?, ?, ?)",
            (2, "workout", "锻炼", "mon,wed,fri", "07:00"),
        )
        await ctx.db.conn.commit()

        handler = _find_handler(plugins, "planner_list")
        reply = await handler(_ev(2))

        assert "锻炼" in reply
        assert "每周" in reply
        assert "一" in reply and "三" in reply and "五" in reply
        assert "07:00" in reply

    @pytest.mark.asyncio
    async def test_list_shows_recent_checkins(self, full_ctx):
        """planner_list should include last 3 check-in records."""
        ctx, plugins, _reg = full_ctx

        await ctx.db.conn.execute(
            "INSERT INTO plans (user_id, tag, name, schedule, remind_time) VALUES (?, ?, ?, ?, ?)",
            (3, "reading", "每日阅读", "daily", "21:00"),
        )
        for i, (date, note, dur) in enumerate([
            ("2026-04-01", "读了第一章", 30),
            ("2026-04-02", "读了第二章", 45),
            ("2026-04-03", "读了第三章", 60),
            ("2026-04-04", "读了第四章", 25),
        ]):
            await ctx.db.conn.execute(
                "INSERT INTO plan_checkins (user_id, tag, date, note, duration_minutes) VALUES (?, ?, ?, ?, ?)",
                (3, "reading", date, note, dur),
            )
        await ctx.db.conn.commit()

        handler = _find_handler(plugins, "planner_list")
        reply = await handler(_ev(3))

        # Should show last 3 (most recent first)
        assert "读了第四章" in reply
        assert "读了第三章" in reply
        assert "读了第二章" in reply
        # 4th record (oldest) should NOT appear (limit 3)
        assert "读了第一章" not in reply
        # Duration should be shown
        assert "25分钟" in reply

    @pytest.mark.asyncio
    async def test_list_no_checkins_message(self, full_ctx):
        """planner_list shows '暂无打卡记录' when no check-ins exist."""
        ctx, plugins, _reg = full_ctx

        await ctx.db.conn.execute(
            "INSERT INTO plans (user_id, tag, name, schedule, remind_time) VALUES (?, ?, ?, ?, ?)",
            (4, "coding", "刷题", "daily", "22:00"),
        )
        await ctx.db.conn.commit()

        handler = _find_handler(plugins, "planner_list")
        reply = await handler(_ev(4))

        assert "暂无打卡记录" in reply

    @pytest.mark.asyncio
    async def test_list_empty_plans(self, full_ctx):
        """planner_list returns guidance when no plans exist."""
        _ctx, plugins, _reg = full_ctx

        handler = _find_handler(plugins, "planner_list")
        reply = await handler(_ev(999))

        assert "planner_add" in reply


# ===========================================================================
# 3. OTHER COMMANDS — end-to-end smoke tests
# ===========================================================================


class TestRecorderCommands:
    """Smoke tests for recorder commands."""

    @pytest.mark.asyncio
    async def test_recorder_today_empty(self, full_ctx):
        """recorder_today returns empty message when no records exist."""
        _ctx, plugins, _reg = full_ctx

        handler = _find_handler(plugins, "recorder_today")
        reply = await handler(_ev(1))

        assert reply is not None
        assert isinstance(reply, str)

    @pytest.mark.asyncio
    async def test_recorder_del_missing_arg(self, full_ctx):
        """recorder_del with no text returns usage."""
        _ctx, plugins, _reg = full_ctx

        handler = _find_handler(plugins, "recorder_del")
        reply = await handler(_ev(1, text=None))

        assert reply is not None
        assert "用法" in reply or "id" in reply.lower()

    @pytest.mark.asyncio
    async def test_recorder_list_empty(self, full_ctx):
        """recorder_list returns photo dict with 0 records when no data."""
        _ctx, plugins, _reg = full_ctx

        handler = _find_handler(plugins, "recorder_list")
        result = await handler(_ev(1))

        assert isinstance(result, dict)
        assert "photo" in result
        assert isinstance(result["photo"], bytes)
        assert len(result["photo"]) > 0
        assert "共 0 条记录" in result["caption"]
        assert "活跃 0 天" in result["caption"]

    @pytest.mark.asyncio
    async def test_recorder_list_with_data(self, full_ctx):
        """recorder_list returns photo with correct counts in caption."""
        ctx, plugins, _reg = full_ctx

        for day_offset, count in [(0, 3), (1, 1), (5, 7)]:
            day = (datetime.now(TZ) - timedelta(days=day_offset)).strftime("%Y-%m-%d")
            for i in range(count):
                await ctx.db.conn.execute(
                    "INSERT INTO messages (user_id, msg_type, content, category, metadata, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (7, "text", f"msg {i}", "other", "{}", f"{day} 10:00:00"),
                )
        await ctx.db.conn.commit()

        handler = _find_handler(plugins, "recorder_list")
        result = await handler(_ev(7))

        assert isinstance(result, dict)
        assert "photo" in result
        assert "共 11 条记录" in result["caption"]
        assert "活跃 3 天" in result["caption"]

    @pytest.mark.asyncio
    async def test_recorder_list_ignores_deleted(self, full_ctx):
        """recorder_list excludes soft-deleted messages."""
        ctx, plugins, _reg = full_ctx
        today = datetime.now(TZ).strftime("%Y-%m-%d")

        await ctx.db.conn.execute(
            "INSERT INTO messages (user_id, msg_type, content, category, metadata, created_at, deleted_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (8, "text", "deleted msg", "other", "{}", f"{today} 10:00:00", "2026-04-05T00:00:00Z"),
        )
        await ctx.db.conn.execute(
            "INSERT INTO messages (user_id, msg_type, content, category, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (8, "text", "active msg", "other", "{}", f"{today} 11:00:00"),
        )
        await ctx.db.conn.commit()

        handler = _find_handler(plugins, "recorder_list")
        result = await handler(_ev(8))

        assert "共 1 条记录" in result["caption"]
        assert "活跃 1 天" in result["caption"]

    @pytest.mark.asyncio
    async def test_recorder_today_with_data(self, full_ctx):
        """recorder_today shows inserted messages."""
        ctx, plugins, _reg = full_ctx
        now = datetime.now(TZ)
        today = now.strftime("%Y-%m-%d")

        await ctx.db.conn.execute(
            "INSERT INTO messages (user_id, msg_type, content, category, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (5, "text", "今天天气不错", "other", "{}", f"{today} 10:00:00"),
        )
        await ctx.db.conn.commit()

        handler = _find_handler(plugins, "recorder_today")
        reply = await handler(_ev(5))

        assert "今天天气不错" in reply


class TestPlannerCommands:
    """Smoke tests for planner commands (beyond list)."""

    @pytest.mark.asyncio
    async def test_planner_add_no_args(self, full_ctx):
        """planner_add with no text returns usage."""
        _ctx, plugins, _reg = full_ctx

        handler = _find_handler(plugins, "planner_add")
        reply = await handler(_ev(1, text=None))

        assert "用法" in reply

    @pytest.mark.asyncio
    async def test_planner_checkin_no_args(self, full_ctx):
        """planner_checkin with no text returns usage."""
        _ctx, plugins, _reg = full_ctx

        handler = _find_handler(plugins, "planner_checkin")
        reply = await handler(_ev(1, text=None))

        assert "用法" in reply

    @pytest.mark.asyncio
    async def test_planner_del_no_args(self, full_ctx):
        """planner_del with no text returns usage."""
        _ctx, plugins, _reg = full_ctx

        handler = _find_handler(plugins, "planner_del")
        reply = await handler(_ev(1, text=None))

        assert "用法" in reply

    @pytest.mark.asyncio
    async def test_planner_add_and_checkin_and_list_flow(self, full_ctx):
        """Full flow: add plan → check in → list shows progress."""
        ctx, plugins, _reg = full_ctx

        add_handler = _find_handler(plugins, "planner_add")
        checkin_handler = _find_handler(plugins, "planner_checkin")
        list_handler = _find_handler(plugins, "planner_list")

        # Add a plan
        reply = await add_handler(_ev(10, text="每天学雅思，晚上8点提醒"))
        assert "已创建计划" in reply

        # Check in
        reply = await checkin_handler(_ev(10, text="练了30分钟听力"))
        assert "已打卡" in reply

        # List should show the plan with check-in
        reply = await list_handler(_ev(10))
        assert "🟩" in reply
        assert "练了30分钟听力" in reply


class TestJournalCommands:
    """Smoke tests for journal non-conversation commands."""

    @pytest.mark.asyncio
    async def test_journal_today_empty(self, full_ctx):
        """journal_today returns guidance when no entries exist."""
        _ctx, plugins, _reg = full_ctx

        handler = _find_handler(plugins, "journal_today")
        reply = await handler(_ev(1))

        assert "还没有" in reply

    @pytest.mark.asyncio
    async def test_journal_cancel_no_session(self, full_ctx):
        """journal_cancel returns message when no active session."""
        _ctx, plugins, _reg = full_ctx

        handler = _find_handler(plugins, "journal_cancel")
        reply = await handler(_ev(1))

        assert "没有进行中" in reply

    @pytest.mark.asyncio
    async def test_journal_today_with_data(self, full_ctx):
        """journal_today shows today's entries."""
        ctx, plugins, _reg = full_ctx
        today = datetime.now(TZ).strftime("%Y-%m-%d")

        await ctx.db.conn.execute(
            "INSERT INTO journal_entries (user_id, date, category, content) VALUES (?, ?, ?, ?)",
            (6, today, "morning", "七点起床"),
        )
        await ctx.db.conn.execute(
            "INSERT INTO journal_entries (user_id, date, category, content) VALUES (?, ?, ?, ?)",
            (6, today, "reading", "读了论语"),
        )
        await ctx.db.conn.commit()

        handler = _find_handler(plugins, "journal_today")
        reply = await handler(_ev(6))

        assert "七点起床" in reply
        assert "读了论语" in reply
        assert "晨起" in reply
        assert "所阅" in reply


class TestJournalSummaryCommand:
    """Tests for journal_summary command."""

    @pytest.mark.asyncio
    async def test_journal_summary_no_data(self, full_ctx):
        """journal_summary returns empty message when no entries."""
        _ctx, plugins, _reg = full_ctx

        handler = _find_handler(plugins, "journal_summary")
        reply = await handler(_ev(1, text=None))

        assert reply is not None
        assert isinstance(reply, str)

    @pytest.mark.asyncio
    async def test_journal_summary_with_date(self, full_ctx):
        """journal_summary with start date returns a summary."""
        ctx, plugins, _reg = full_ctx

        await ctx.db.conn.execute(
            "INSERT INTO journal_entries (user_id, date, category, content) VALUES (?, ?, ?, ?)",
            (60, "2026-04-01", "morning", "Early start"),
        )
        await ctx.db.conn.commit()

        handler = _find_handler(plugins, "journal_summary")
        reply = await handler(_ev(60, text="2026-04-01"))

        assert "2026-04-01" in reply

    @pytest.mark.asyncio
    async def test_journal_summary_invalid_date(self, full_ctx):
        """journal_summary with bad date shows usage."""
        _ctx, plugins, _reg = full_ctx

        handler = _find_handler(plugins, "journal_summary")
        reply = await handler(_ev(1, text="bad-date"))

        assert "/journal_summary" in reply


# ===========================================================================
# 4. AUTO-JOURNAL GENERATION
# ===========================================================================


class TestAutoJournal:
    """Test auto-journal generation from messages when no journal exists."""

    @pytest.mark.asyncio
    async def test_auto_journal_generates_entries(self, full_ctx):
        """Auto-journal should create journal entries from messages."""
        ctx, plugins, _reg = full_ctx
        today = datetime.now(TZ).strftime("%Y-%m-%d")

        # Insert some messages but no journal entries
        for text in ["早上七点起床", "读了一篇文章", "和朋友吃了饭"]:
            await ctx.db.conn.execute(
                "INSERT INTO messages (user_id, msg_type, content, category, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (50, "text", text, "other", "{}", f"{today} 10:00:00"),
            )
        await ctx.db.conn.commit()

        # LLM returns structured journal entries
        ctx.llm._responses = [
            '[{"category":"morning","content":"Early riser today"},{"category":"reading","content":"Read an article"}]',
        ]
        ctx.llm._call_index = 0

        from src.plugins.journal.scheduler import _auto_journal_for_user
        from src.plugins.journal.db import JournalDB

        journal_db = JournalDB(ctx.db)
        await _auto_journal_for_user(ctx, journal_db, user_id=50, today=today)

        # Verify journal entries were created
        entries = await journal_db.get_journal_entries(50, today)
        assert len(entries) == 2
        cats = {e["category"] for e in entries}
        assert "morning" in cats
        assert "reading" in cats

        # Verify bot was notified (notify + done = 2 messages)
        assert len(ctx.bot.sent) >= 2

    @pytest.mark.asyncio
    async def test_auto_journal_skips_when_journal_exists(self, full_ctx):
        """Auto-journal should not run if user already wrote journal."""
        ctx, plugins, _reg = full_ctx
        today = datetime.now(TZ).strftime("%Y-%m-%d")

        # Insert a journal entry
        await ctx.db.conn.execute(
            "INSERT INTO journal_entries (user_id, date, category, content) VALUES (?, ?, ?, ?)",
            (51, today, "morning", "Already wrote this"),
        )
        await ctx.db.conn.commit()

        from src.plugins.journal.scheduler import _auto_journal_for_user
        from src.plugins.journal.db import JournalDB

        journal_db = JournalDB(ctx.db)
        await _auto_journal_for_user(ctx, journal_db, user_id=51, today=today)

        # No messages sent — skipped
        assert len(ctx.bot.sent) == 0

    @pytest.mark.asyncio
    async def test_auto_journal_skips_when_no_messages(self, full_ctx):
        """Auto-journal should not run if no messages exist."""
        ctx, plugins, _reg = full_ctx
        today = datetime.now(TZ).strftime("%Y-%m-%d")

        from src.plugins.journal.scheduler import _auto_journal_for_user
        from src.plugins.journal.db import JournalDB

        journal_db = JournalDB(ctx.db)
        await _auto_journal_for_user(ctx, journal_db, user_id=52, today=today)

        # No messages sent — nothing to do
        assert len(ctx.bot.sent) == 0


# ===========================================================================
# 5. CONVERSATION FLOW STRUCTURE TESTS
# ===========================================================================


class TestConversationFlowContract:
    """Verify the ConversationFlow dataclass contract across all plugins."""

    @pytest.mark.asyncio
    async def test_all_conversations_have_entry_handler(self, full_ctx):
        """Every ConversationFlow must have a callable entry_handler."""
        _ctx, plugins, _reg = full_ctx

        for plugin in plugins:
            for conv in plugin.get_conversations():
                assert hasattr(conv, "entry_handler"), (
                    f"ConversationFlow {conv.name!r} missing entry_handler"
                )
                assert callable(conv.entry_handler), (
                    f"ConversationFlow {conv.name!r} entry_handler not callable"
                )

    @pytest.mark.asyncio
    async def test_all_conversations_have_matching_commands(self, full_ctx):
        """Every ConversationFlow entry_command should have a matching Command."""
        _ctx, plugins, _reg = full_ctx

        all_cmd_names = set()
        for plugin in plugins:
            for cmd in plugin.get_commands():
                all_cmd_names.add(cmd.name)

        for plugin in plugins:
            for conv in plugin.get_conversations():
                assert conv.entry_command in all_cmd_names, (
                    f"ConversationFlow {conv.name!r} entry_command "
                    f"{conv.entry_command!r} has no matching Command"
                )
