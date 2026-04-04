"""Journal plugin scheduler — evening prompt and weekly summary."""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.context import AppContext

logger = logging.getLogger(__name__)


async def _evening_journal_callback(ctx: "AppContext", data: Any = None) -> None:
    """Send journal reminder to configured users."""
    allowed_ids: list[int] = ctx.config.get("allowed_user_ids", [])
    for user_id in allowed_ids:
        try:
            await ctx.bot.send_message(
                chat_id=user_id,
                text="今天过得怎么样？用 /journal_start 开始今日反思吧。",
            )
        except Exception:
            logger.exception("Failed to send journal reminder to user %s", user_id)


async def _weekly_summary_callback(ctx: "AppContext", data: Any = None) -> None:
    """Generate and send weekly summary to all users."""
    from .db import JournalDB
    from .summary import generate_summary

    allowed_ids: list[int] = ctx.config.get("allowed_user_ids", [])
    journal_db = JournalDB(ctx.db)
    now = datetime.now(ctx.tz)
    end = now.strftime("%Y-%m-%d")
    start = (now - timedelta(days=6)).strftime("%Y-%m-%d")

    for user_id in allowed_ids:
        try:
            result = await generate_summary(
                db=journal_db,
                llm=ctx.llm,
                user_id=user_id,
                period_type="week",
                start_date=start,
                end_date=end,
            )
            await ctx.bot.send_message(
                chat_id=user_id,
                text=f"本周总结\n\n{result}",
            )
        except Exception:
            logger.exception("Failed to send weekly summary to user %s", user_id)


async def setup_journal_schedules(ctx: "AppContext") -> None:
    """Register evening journal prompt and weekly summary jobs."""
    hour = ctx.config.get("remind_hour", 21)
    minute = ctx.config.get("remind_minute", 0)

    prompt_time = time(hour=hour, minute=minute, tzinfo=ctx.tz)
    await ctx.scheduler.run_daily(
        callback=lambda data=None: _evening_journal_callback(ctx, data),
        time=prompt_time,
        name="journal_evening_prompt",
    )
    logger.info("Scheduled journal evening prompt at %02d:%02d", hour, minute)

    summary_time = time(hour=22, minute=0, tzinfo=ctx.tz)
    await ctx.scheduler.run_daily(
        callback=lambda data=None: _weekly_summary_callback(ctx, data),
        time=summary_time,
        name="journal_weekly_summary",
        days=(6,),  # Sunday
    )
    logger.info("Scheduled journal weekly summary for Sunday 22:00")
