"""Schedule passive plan reminders via JobQueue."""
from __future__ import annotations

import logging
from datetime import datetime, time

from telegram.ext import Application

from .reminder import check_needs_reminder

logger = logging.getLogger(__name__)

DAYS_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


async def plan_reminder_callback(context) -> None:
    """Check if user needs a reminder and send it."""
    db = context.bot_data["db"]
    tz = context.bot_data["tz"]
    plan = context.job.data
    tag = plan["tag"]
    name = plan["name"]
    today = datetime.now(tz).strftime("%Y-%m-%d")

    allowed_ids = context.bot_data["config"].get("telegram", {}).get("allowed_user_ids", [])
    for user_id in allowed_ids:
        needs = await check_needs_reminder(db, user_id, tag, today)
        if needs:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📖 今天的「{name}」还没打卡哦，还在计划中吗？\n用 /checkin {tag} <备注> 来打卡",
                )
            except Exception:
                logger.exception("Failed to send plan reminder to user %s", user_id)


def _parse_schedule_days(schedule: str) -> tuple[int, ...] | None:
    """Parse schedule string. Returns None for daily, tuple of weekday ints otherwise."""
    if schedule == "daily":
        return None
    days = []
    for d in schedule.split(","):
        d = d.strip().lower()
        if d in DAYS_MAP:
            days.append(DAYS_MAP[d])
    return tuple(days) if days else None


def schedule_plan_reminders(app: Application, plans: list[dict], tz) -> None:
    """Register reminder jobs for each configured plan."""
    for plan in plans:
        tag = plan["tag"]
        remind_time_str = plan.get("remind_time", "20:00")
        h, m = (int(x) for x in remind_time_str.split(":"))
        job_time = time(hour=h, minute=m, tzinfo=tz)
        schedule = plan.get("schedule", "daily")
        days = _parse_schedule_days(schedule)

        if days is None:
            app.job_queue.run_daily(
                plan_reminder_callback,
                time=job_time,
                name=f"plan_reminder_{tag}",
                data=plan,
            )
        else:
            app.job_queue.run_daily(
                plan_reminder_callback,
                time=job_time,
                days=days,
                name=f"plan_reminder_{tag}",
                data=plan,
            )

        logger.info("Scheduled reminder for '%s' at %s (schedule: %s)", tag, remind_time_str, schedule)
