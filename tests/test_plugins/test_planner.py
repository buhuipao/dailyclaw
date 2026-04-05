"""Tests for the planner plugin."""
from __future__ import annotations

from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio

from src.core.context import AppContext
from src.core.db import Database, MigrationRunner


MIGRATIONS_DIR = "src/plugins/planner/migrations"
TZ = ZoneInfo("Asia/Shanghai")


@pytest_asyncio.fixture
async def planner_db(tmp_path):
    """Provide a Database with planner migrations applied."""
    db_path = str(tmp_path / "test_planner.db")
    database = Database(db_path=db_path)
    await database.connect()
    runner = MigrationRunner(database)
    await runner.run("planner", MIGRATIONS_DIR)
    yield database
    await database.close()


@pytest_asyncio.fixture
async def ctx(planner_db, fake_llm, fake_bot, fake_scheduler):
    """Provide an AppContext backed by the planner DB."""
    return AppContext(
        db=planner_db,
        llm=fake_llm(),
        bot=fake_bot,
        scheduler=fake_scheduler,
        config={},
        tz=TZ,
    )


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plans_table_accepts_insert(planner_db):
    """plans table is created and accepts rows after migration."""
    await planner_db.conn.execute(
        "INSERT INTO plans (user_id, tag, name, schedule, remind_time) VALUES (?, ?, ?, ?, ?)",
        (1, "ielts", "每天学雅思", "daily", "20:00"),
    )
    await planner_db.conn.commit()

    cursor = await planner_db.conn.execute("SELECT tag, name FROM plans WHERE user_id = 1")
    row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "ielts"
    assert row[1] == "每天学雅思"


@pytest.mark.asyncio
async def test_plan_checkins_table_works(planner_db):
    """plan_checkins table is created and accepts rows."""
    await planner_db.conn.execute(
        "INSERT INTO plan_checkins (user_id, tag, date, note, duration_minutes) VALUES (?, ?, ?, ?, ?)",
        (1, "ielts", "2026-04-04", "听力练习30分钟", 30),
    )
    await planner_db.conn.commit()

    cursor = await planner_db.conn.execute(
        "SELECT note, duration_minutes FROM plan_checkins WHERE user_id = 1 AND tag = 'ielts'"
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "听力练习30分钟"
    assert row[1] == 30


@pytest.mark.asyncio
async def test_archive_plan_sets_active_zero(planner_db):
    """Archiving a plan sets active = 0."""
    await planner_db.conn.execute(
        "INSERT INTO plans (user_id, tag, name, schedule, remind_time) VALUES (?, ?, ?, ?, ?)",
        (1, "workout", "锻炼", "daily", "07:00"),
    )
    await planner_db.conn.commit()

    await planner_db.conn.execute(
        "UPDATE plans SET active = 0 WHERE user_id = ? AND tag = ?",
        (1, "workout"),
    )
    await planner_db.conn.commit()

    cursor = await planner_db.conn.execute(
        "SELECT active FROM plans WHERE user_id = 1 AND tag = 'workout'"
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row[0] == 0


# ---------------------------------------------------------------------------
# check_needs_reminder tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_needs_reminder_true_when_no_checkins(planner_db):
    """check_needs_reminder returns True when no checkin exists for today."""
    from src.plugins.planner.reminder import check_needs_reminder

    result = await check_needs_reminder(planner_db, user_id=1, tag="ielts", date="2026-04-04")
    assert result is True


@pytest.mark.asyncio
async def test_check_needs_reminder_false_when_checkin_exists(planner_db):
    """check_needs_reminder returns False when a checkin exists for today."""
    from src.plugins.planner.reminder import check_needs_reminder

    await planner_db.conn.execute(
        "INSERT INTO plan_checkins (user_id, tag, date, note, duration_minutes) VALUES (?, ?, ?, ?, ?)",
        (1, "ielts", "2026-04-04", "已打卡", 0),
    )
    await planner_db.conn.commit()

    result = await check_needs_reminder(planner_db, user_id=1, tag="ielts", date="2026-04-04")
    assert result is False


@pytest.mark.asyncio
async def test_check_needs_reminder_different_date_still_true(planner_db):
    """check_needs_reminder returns True when checkin exists for a different date."""
    from src.plugins.planner.reminder import check_needs_reminder

    await planner_db.conn.execute(
        "INSERT INTO plan_checkins (user_id, tag, date, note, duration_minutes) VALUES (?, ?, ?, ?, ?)",
        (1, "ielts", "2026-04-03", "昨天打卡", 0),
    )
    await planner_db.conn.commit()

    result = await check_needs_reminder(planner_db, user_id=1, tag="ielts", date="2026-04-04")
    assert result is True


# ---------------------------------------------------------------------------
# Command handler tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_planner_add_creates_plan(ctx):
    """cmd_planner_add inserts a plan row and returns confirmation."""
    from src.core.bot import Event
    from src.plugins.planner.commands import make_commands

    commands = make_commands(ctx)
    handler = next(c.handler for c in commands if c.name == "planner_add")

    event = Event(user_id=1, chat_id=1, lang="zh", text="每天学雅思，晚上8点提醒")
    reply = await handler(event)

    assert reply is not None
    assert "已创建计划" in reply

    cursor = await ctx.db.conn.execute("SELECT tag, active FROM plans WHERE user_id = 1")
    row = await cursor.fetchone()
    assert row is not None
    assert row[1] == 1  # active


@pytest.mark.asyncio
async def test_cmd_planner_add_missing_text_returns_usage(ctx):
    """cmd_planner_add with no text returns usage string."""
    from src.core.bot import Event
    from src.plugins.planner.commands import make_commands

    commands = make_commands(ctx)
    handler = next(c.handler for c in commands if c.name == "planner_add")

    event = Event(user_id=1, chat_id=1, lang="zh", text=None)
    reply = await handler(event)

    assert reply is not None
    assert "用法" in reply


@pytest.mark.asyncio
async def test_cmd_planner_add_duplicate_tag_blocked(ctx):
    """cmd_planner_add blocks inserting a duplicate active tag."""
    from src.core.bot import Event
    from src.plugins.planner.commands import make_commands

    # Seed an existing plan with the same tag the FakeLLMService returns ("test")
    await ctx.db.conn.execute(
        "INSERT INTO plans (user_id, tag, name, schedule, remind_time) VALUES (?, ?, ?, ?, ?)",
        (1, "test", "旧计划", "daily", "20:00"),
    )
    await ctx.db.conn.commit()

    commands = make_commands(ctx)
    handler = next(c.handler for c in commands if c.name == "planner_add")

    event = Event(user_id=1, chat_id=1, lang="zh", text="重复的计划")
    reply = await handler(event)

    assert reply is not None
    assert "已存在同名计划" in reply


@pytest.mark.asyncio
async def test_cmd_planner_checkin_saves_record(ctx):
    """cmd_planner_checkin saves a checkin row."""
    from src.core.bot import Event
    from src.plugins.planner.commands import make_commands

    # Seed a plan (FakeLLMService.match_checkin returns first plan's tag)
    await ctx.db.conn.execute(
        "INSERT INTO plans (user_id, tag, name, schedule, remind_time) VALUES (?, ?, ?, ?, ?)",
        (1, "test", "测试计划", "daily", "20:00"),
    )
    await ctx.db.conn.commit()

    commands = make_commands(ctx)
    handler = next(c.handler for c in commands if c.name == "planner_checkin")

    event = Event(user_id=1, chat_id=1, lang="zh", text="今天练了30分钟")
    reply = await handler(event)

    assert reply is not None
    assert "已打卡" in reply

    cursor = await ctx.db.conn.execute("SELECT tag FROM plan_checkins WHERE user_id = 1")
    row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "test"


@pytest.mark.asyncio
async def test_cmd_planner_checkin_no_plans(ctx):
    """cmd_planner_checkin returns guidance when no plans exist."""
    from src.core.bot import Event
    from src.plugins.planner.commands import make_commands

    commands = make_commands(ctx)
    handler = next(c.handler for c in commands if c.name == "planner_checkin")

    event = Event(user_id=1, chat_id=1, lang="zh", text="跑了5公里")
    reply = await handler(event)

    assert reply is not None
    assert "planner_add" in reply


@pytest.mark.asyncio
async def test_cmd_planner_list_shows_progress(ctx):
    """cmd_planner_list formats the progress bar."""
    from src.core.bot import Event
    from src.plugins.planner.commands import make_commands

    await ctx.db.conn.execute(
        "INSERT INTO plans (user_id, tag, name, schedule, remind_time) VALUES (?, ?, ?, ?, ?)",
        (1, "reading", "每日阅读", "daily", "21:00"),
    )
    await ctx.db.conn.commit()

    commands = make_commands(ctx)
    handler = next(c.handler for c in commands if c.name == "planner_list")

    event = Event(user_id=1, chat_id=1, lang="zh", text=None)
    reply = await handler(event)

    assert reply is not None
    assert "每日阅读" in reply
    assert "0/" in reply


@pytest.mark.asyncio
async def test_cmd_planner_del_archives_plan(ctx):
    """cmd_planner_del sets active = 0 for the matched plan."""
    from src.core.bot import Event
    from src.plugins.planner.commands import make_commands

    await ctx.db.conn.execute(
        "INSERT INTO plans (user_id, tag, name, schedule, remind_time) VALUES (?, ?, ?, ?, ?)",
        (1, "test", "待归档计划", "daily", "20:00"),
    )
    await ctx.db.conn.commit()

    commands = make_commands(ctx)
    handler = next(c.handler for c in commands if c.name == "planner_del")

    # FakeLLMService.match_checkin returns first plan's tag ("test")
    event = Event(user_id=1, chat_id=1, lang="zh", text="待归档计划")
    reply = await handler(event)

    assert reply is not None
    assert "已归档" in reply

    cursor = await ctx.db.conn.execute("SELECT active FROM plans WHERE user_id = 1 AND tag = 'test'")
    row = await cursor.fetchone()
    assert row is not None
    assert row[0] == 0


# ---------------------------------------------------------------------------
# Scheduler tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_setup_plan_reminders_registers_jobs(planner_db, fake_bot, fake_scheduler):
    """setup_plan_reminders creates a run_daily job per active plan."""
    from src.core.context import AppContext
    from src.plugins.planner.scheduler import setup_plan_reminders

    await planner_db.conn.execute(
        "INSERT INTO plans (user_id, tag, name, schedule, remind_time) VALUES (?, ?, ?, ?, ?)",
        (1, "ielts", "每天学雅思", "daily", "20:00"),
    )
    await planner_db.conn.execute(
        "INSERT INTO plans (user_id, tag, name, schedule, remind_time) VALUES (?, ?, ?, ?, ?)",
        (1, "workout", "锻炼", "mon,wed,fri", "07:00"),
    )
    await planner_db.conn.commit()

    ctx = AppContext(
        db=planner_db,
        llm=None,
        bot=fake_bot,
        scheduler=fake_scheduler,
        config={},
        tz=TZ,
    )
    await setup_plan_reminders(ctx)

    assert "plan_reminder_ielts" in fake_scheduler.jobs
    assert "plan_reminder_workout" in fake_scheduler.jobs

    ielts_job = fake_scheduler.jobs["plan_reminder_ielts"]
    assert ielts_job["type"] == "daily"
    assert ielts_job["days"] is None  # daily schedule

    workout_job = fake_scheduler.jobs["plan_reminder_workout"]
    assert workout_job["days"] == (1, 3, 5)  # mon, wed, fri (ptb v20+: 0=Sun)
