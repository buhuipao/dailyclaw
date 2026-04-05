"""Schedule passive plan reminders via the core Scheduler abstraction."""
from __future__ import annotations

import logging
from datetime import time

from src.core.i18n import t

import src.plugins.planner.locale  # noqa: F401

from .reminder import check_needs_reminder

logger = logging.getLogger(__name__)

# python-telegram-bot v20+ days mapping: 0=Sun, 1=Mon, ..., 6=Sat
DAYS_MAP = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}


def _parse_schedule_days(schedule: str) -> tuple[int, ...] | None:
    """Parse a schedule string. Returns None for daily, tuple of weekday ints otherwise."""
    if schedule == "daily":
        return None
    days = []
    for part in schedule.split(","):
        key = part.strip().lower()
        if key in DAYS_MAP:
            days.append(DAYS_MAP[key])
    return tuple(days) if days else None


async def _make_reminder_callback(ctx, plan: dict):
    """Return a scheduler callback bound to ctx and plan (closure)."""

    async def reminder_callback() -> None:
        from datetime import datetime

        db = ctx.db
        bot = ctx.bot
        tz = ctx.tz
        tag = plan["tag"]
        name = plan["name"]
        today = datetime.now(tz).strftime("%Y-%m-%d")

        # Fetch all active users who have this plan
        cursor = await db.conn.execute(
            "SELECT DISTINCT user_id FROM plans WHERE tag = ? AND active = 1",
            (tag,),
        )
        rows = await cursor.fetchall()

        for row in rows:
            user_id = row[0]
            needs = await check_needs_reminder(db, user_id, tag, today)
            if needs:
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=t("planner.reminder", "zh", name=name, tag=tag),
                    )
                except Exception:
                    logger.exception("Failed to send plan reminder to user %s", user_id)

    return reminder_callback


async def register_plan_reminder(
    ctx, tag: str, name: str, schedule: str, remind_time_str: str,
) -> None:
    """Register a single plan's daily reminder. Can be called at startup or after /planner_add."""
    try:
        h, m = (int(x) for x in remind_time_str.split(":"))
    except ValueError:
        logger.warning("Invalid remind_time '%s' for plan '%s', defaulting to 20:00", remind_time_str, tag)
        h, m = 20, 0

    plan_data = {"tag": tag, "name": name, "schedule": schedule, "remind_time": remind_time_str}
    job_time = time(hour=h, minute=m, tzinfo=ctx.tz)
    days = _parse_schedule_days(schedule)
    callback = await _make_reminder_callback(ctx, plan_data)

    await ctx.scheduler.run_daily(
        callback,
        time=job_time,
        name=f"plan_reminder_{tag}",
        days=days,
        data=plan_data,
    )
    logger.info("Scheduled reminder for '%s' at %s (schedule: %s)", tag, remind_time_str, schedule)


async def setup_plan_reminders(ctx) -> None:
    """Query all active plans from DB and schedule a daily reminder for each."""
    cursor = await ctx.db.conn.execute(
        "SELECT DISTINCT tag, name, schedule, remind_time FROM plans WHERE active = 1"
    )
    plans = await cursor.fetchall()

    for row in plans:
        await register_plan_reminder(
            ctx,
            tag=row[0],
            name=row[1],
            schedule=row[2] if row[2] else "daily",
            remind_time_str=row[3] if row[3] else "20:00",
        )
