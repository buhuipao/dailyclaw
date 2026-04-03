"""Schedule the evening journal prompt and weekly summaries."""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

from telegram.ext import Application

logger = logging.getLogger(__name__)


async def evening_journal_callback(context) -> None:
    """Send journal reminder to all allowed users."""
    config = context.bot_data["config"]
    allowed_ids = config.get("telegram", {}).get("allowed_user_ids", [])

    for user_id in allowed_ids:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🌙 今天过得怎么样？用 /journal 开始今日反思吧。",
            )
        except Exception:
            logger.exception("Failed to send journal reminder to user %s", user_id)


def schedule_evening_journal(app: Application, hour: int, minute: int, tz) -> None:
    """Register a daily job to send the journal prompt."""
    job_time = time(hour=hour, minute=minute, tzinfo=tz)
    app.job_queue.run_daily(
        evening_journal_callback,
        time=job_time,
        name="evening_journal",
    )
    logger.info("Scheduled evening journal at %02d:%02d %s", hour, minute, tz)


async def weekly_summary_callback(context) -> None:
    """Generate and send weekly summary every Sunday evening."""
    from .summary import generate_summary

    db = context.bot_data["db"]
    llm = context.bot_data["llm"]
    tz = context.bot_data["tz"]
    config = context.bot_data["config"]
    allowed_ids = config.get("telegram", {}).get("allowed_user_ids", [])

    now = datetime.now(tz)
    end = now.strftime("%Y-%m-%d")
    start = (now - timedelta(days=6)).strftime("%Y-%m-%d")

    for user_id in allowed_ids:
        try:
            result = await generate_summary(
                db=db, llm=llm, user_id=user_id,
                period_type="week", start_date=start, end_date=end,
            )
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📊 本周总结\n\n{result}",
            )
        except Exception:
            logger.exception("Failed to send weekly summary to user %s", user_id)


def schedule_weekly_summary(app: Application, tz) -> None:
    """Register weekly summary job for Sunday 22:00."""
    job_time = time(hour=22, minute=0, tzinfo=tz)
    app.job_queue.run_daily(
        weekly_summary_callback,
        time=job_time,
        days=(6,),  # Sunday
        name="weekly_summary",
    )
    logger.info("Scheduled weekly summary for Sunday 22:00 %s", tz)
