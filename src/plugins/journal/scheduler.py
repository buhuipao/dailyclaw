"""Journal plugin scheduler — evening prompt, auto-journal, weekly summary."""
from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING, Any

from src.core.i18n import t
from src.core.i18n.shared import category_label

import src.plugins.journal.locale  # noqa: F401

if TYPE_CHECKING:
    from src.core.context import AppContext

logger = logging.getLogger(__name__)


def _get_user_lang(ctx: "AppContext", user_id: int) -> str:
    """Look up user language from the bot adapter's auth cache."""
    try:
        return ctx.bot._auth.get_lang(user_id)
    except AttributeError:
        return "en"


async def _get_allowed_user_ids(ctx: "AppContext") -> list[int]:
    """Get allowed user IDs from config."""
    return ctx.config.get("allowed_user_ids", [])


# ---------------------------------------------------------------------------
# Evening reminder (configurable hour, default 21:00)
# ---------------------------------------------------------------------------


async def _evening_journal_callback(ctx: "AppContext", data: Any = None) -> None:
    """Send journal reminder only to users who haven't written today."""
    from .db import JournalDB

    journal_db = JournalDB(ctx.db)
    today = datetime.now(ctx.tz).strftime("%Y-%m-%d")

    for user_id in await _get_allowed_user_ids(ctx):
        try:
            entries = await journal_db.get_journal_entries(user_id, today)
            if entries:
                continue  # already wrote journal today
            lang = _get_user_lang(ctx, user_id)
            await ctx.bot.send_message(
                chat_id=user_id,
                text=t("journal.evening_reminder", lang),
            )
        except Exception:
            logger.exception("Failed to send journal reminder to user %s", user_id)


# ---------------------------------------------------------------------------
# Auto-journal (23:50 — 10 min before midnight)
# ---------------------------------------------------------------------------


async def _auto_journal_callback(ctx: "AppContext", data: Any = None) -> None:
    """Auto-generate journal from today's messages if user hasn't written one."""
    from .db import JournalDB

    journal_db = JournalDB(ctx.db)
    today = datetime.now(ctx.tz).strftime("%Y-%m-%d")

    for user_id in await _get_allowed_user_ids(ctx):
        try:
            await _auto_journal_for_user(ctx, journal_db, user_id, today)
        except Exception:
            logger.exception("Auto-journal failed for user %s", user_id)


async def _auto_journal_for_user(
    ctx: "AppContext",
    journal_db: Any,
    user_id: int,
    today: str,
) -> None:
    """Generate journal for one user if they have messages but no journal."""
    # 1. Check if journal already exists
    entries = await journal_db.get_journal_entries(user_id, today)
    if entries:
        return  # user already wrote journal

    # 2. Check if there are messages to summarize
    cursor = await ctx.db.conn.execute(
        "SELECT content, category, msg_type FROM messages "
        "WHERE user_id = ? AND date(created_at) = ? AND deleted_at IS NULL "
        "ORDER BY created_at",
        (user_id, today),
    )
    messages = await cursor.fetchall()
    if not messages:
        return  # no messages either, nothing to do

    lang = _get_user_lang(ctx, user_id)
    msg_count = len(messages)

    # 3. Notify user that auto-journal is starting
    await ctx.bot.send_message(
        chat_id=user_id,
        text=t("journal.auto_journal_notify", lang, count=msg_count),
    )

    # 4. Build message summary for LLM
    msg_text = "\n".join(
        f"- [{row['category'] or row['msg_type']}] {row['content'][:150]}"
        for row in messages
    )

    system_prompt = (
        t("journal.auto_journal_system_prompt", lang)
        + t("journal.auto_journal_format", lang)
    )

    raw = await ctx.llm.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": msg_text},
        ],
        temperature=0.5,
        max_tokens=600,
        lang=lang,
    )

    # 5. Parse LLM response and save entries
    try:
        generated = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[auto-journal] LLM returned non-JSON for user %d: %s", user_id, raw[:200])
        return

    if not isinstance(generated, list) or not generated:
        return

    saved_labels: list[str] = []
    for item in generated:
        cat = item.get("category", "")
        content = item.get("content", "")
        if cat and content:
            await journal_db.save_journal_entry(user_id, today, cat, content)
            saved_labels.append(f"【{category_label(cat, lang)}】{content}")

    if not saved_labels:
        return

    # 6. Notify user with the result
    summary_text = "\n".join(saved_labels)
    await ctx.bot.send_message(
        chat_id=user_id,
        text=t("journal.auto_journal_done", lang, content=summary_text),
    )
    logger.info("[auto-journal] generated %d entries for user %d", len(saved_labels), user_id)


# ---------------------------------------------------------------------------
# Weekly summary (Sunday 22:00)
# ---------------------------------------------------------------------------


async def _weekly_summary_callback(ctx: "AppContext", data: Any = None) -> None:
    """Generate and send weekly summary to all users."""
    from .db import JournalDB
    from .summary import generate_summary

    journal_db = JournalDB(ctx.db)
    now = datetime.now(ctx.tz)
    end = now.strftime("%Y-%m-%d")
    start = (now - timedelta(days=6)).strftime("%Y-%m-%d")

    for user_id in await _get_allowed_user_ids(ctx):
        try:
            lang = _get_user_lang(ctx, user_id)
            result = await generate_summary(
                db=journal_db,
                llm=ctx.llm,
                user_id=user_id,
                period_type="week",
                start_date=start,
                end_date=end,
                lang=lang,
            )
            await ctx.bot.send_message(
                chat_id=user_id,
                text=t("journal.weekly_summary_header", lang, content=result),
            )
        except Exception:
            logger.exception("Failed to send weekly summary to user %s", user_id)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


async def setup_journal_schedules(ctx: "AppContext") -> None:
    """Register evening prompt, auto-journal, and weekly summary jobs."""
    hour = ctx.config.get("remind_hour", 21)
    minute = ctx.config.get("remind_minute", 0)

    # Evening reminder (default 21:00)
    prompt_time = time(hour=hour, minute=minute, tzinfo=ctx.tz)
    await ctx.scheduler.run_daily(
        callback=lambda data=None: _evening_journal_callback(ctx, data),
        time=prompt_time,
        name="journal_evening_prompt",
    )
    logger.info("Scheduled journal evening prompt at %02d:%02d", hour, minute)

    # Auto-journal at 23:50 — generate from messages if no journal written
    auto_time = time(hour=23, minute=50, tzinfo=ctx.tz)
    await ctx.scheduler.run_daily(
        callback=lambda data=None: _auto_journal_callback(ctx, data),
        time=auto_time,
        name="journal_auto_generate",
    )
    logger.info("Scheduled auto-journal at 23:50")

    # Weekly summary on Sunday 22:00
    summary_time = time(hour=22, minute=0, tzinfo=ctx.tz)
    await ctx.scheduler.run_daily(
        callback=lambda data=None: _weekly_summary_callback(ctx, data),
        time=summary_time,
        name="journal_weekly_summary",
        days=(0,),  # Sunday (ptb v20+: 0=Sun, 6=Sat)
    )
    logger.info("Scheduled journal weekly summary for Sunday 22:00")
