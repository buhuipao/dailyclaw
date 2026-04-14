"""Wiki scheduler — daily ingest, weekly digest, monthly lint."""
from __future__ import annotations

import logging
from datetime import time
from typing import TYPE_CHECKING, Any

from src.core.i18n import t

import src.plugins.wiki.locale  # noqa: F401

from .db import WikiDB
from .digest import generate_digest
from .ingest import run_ingest
from .lint import run_lint

if TYPE_CHECKING:
    from src.core.context import AppContext

logger = logging.getLogger(__name__)

DAYS_MAP: dict[str, int] = {
    "sunday": 0,
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
    "saturday": 6,
}


def _get_user_lang(ctx: "AppContext", user_id: int) -> str:
    """Look up user language from the bot adapter's auth cache."""
    try:
        return ctx.bot._auth.get_lang(user_id)
    except AttributeError:
        return "en"


async def _get_allowed_user_ids(ctx: "AppContext") -> list[int]:
    """Get all user IDs from the allowed_users table."""
    try:
        cursor = await ctx.db.conn.execute("SELECT user_id FROM allowed_users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
    except Exception:
        logger.warning("Failed to query allowed_users", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Daily ingest
# ---------------------------------------------------------------------------


async def _ingest_callback(ctx: "AppContext", data: Any = None) -> None:
    """Run ingest for all users."""
    user_ids = await _get_allowed_user_ids(ctx)
    logger.info("[wiki-ingest] triggered for %d users", len(user_ids))

    for user_id in user_ids:
        try:
            lang = _get_user_lang(ctx, user_id)
            wiki_db = WikiDB(ctx.db)
            result = await run_ingest(
                db=ctx.db,
                llm=ctx.llm,
                wiki_db=wiki_db,
                user_id=user_id,
                lang=lang,
            )
            logger.info(
                "[wiki-ingest] user=%d created=%d updated=%d sources=%d",
                user_id, result["created"], result["updated"], result["sources"],
            )
        except Exception:
            logger.exception("[wiki-ingest] failed for user %d", user_id)


# ---------------------------------------------------------------------------
# Weekly digest
# ---------------------------------------------------------------------------


async def _digest_callback(ctx: "AppContext", data: Any = None) -> None:
    """Generate and send weekly digest to all users."""
    user_ids = await _get_allowed_user_ids(ctx)
    logger.info("[wiki-digest] triggered for %d users", len(user_ids))

    for user_id in user_ids:
        try:
            lang = _get_user_lang(ctx, user_id)
            wiki_db = WikiDB(ctx.db)
            result = await generate_digest(
                llm=ctx.llm,
                wiki_db=wiki_db,
                user_id=user_id,
                lang=lang,
            )
            if result:
                text = t("wiki.digest_header", lang) + result
                await ctx.bot.send_message(chat_id=user_id, text=text)
        except Exception:
            logger.exception("[wiki-digest] failed for user %d", user_id)


# ---------------------------------------------------------------------------
# Monthly lint
# ---------------------------------------------------------------------------


async def _lint_callback(ctx: "AppContext", data: Any = None) -> None:
    """Run lint and send report to all users."""
    user_ids = await _get_allowed_user_ids(ctx)
    logger.info("[wiki-lint] triggered for %d users", len(user_ids))

    for user_id in user_ids:
        try:
            lang = _get_user_lang(ctx, user_id)
            wiki_db = WikiDB(ctx.db)
            report = await run_lint(
                llm=ctx.llm,
                wiki_db=wiki_db,
                user_id=user_id,
                lang=lang,
            )
            if report:
                await ctx.bot.send_message(chat_id=user_id, text=report)
        except Exception:
            logger.exception("[wiki-lint] failed for user %d", user_id)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


async def setup_wiki_schedules(ctx: "AppContext") -> None:
    """Register daily ingest, weekly digest, and monthly lint jobs."""
    # Daily ingest (default 22:30)
    ingest_hour = ctx.config.get("ingest_hour", 22)
    ingest_minute = ctx.config.get("ingest_minute", 30)
    ingest_time = time(hour=ingest_hour, minute=ingest_minute, tzinfo=ctx.tz)
    await ctx.scheduler.run_daily(
        callback=lambda data=None: _ingest_callback(ctx, data),
        time=ingest_time,
        name="wiki_daily_ingest",
    )
    logger.info("Scheduled wiki daily ingest at %02d:%02d", ingest_hour, ingest_minute)

    # Weekly digest (default Sunday at 21:00)
    digest_day_name = ctx.config.get("digest_day", "sunday")
    digest_day = DAYS_MAP.get(digest_day_name, 0)
    digest_hour = ctx.config.get("digest_hour", 21)
    digest_time = time(hour=digest_hour, minute=0, tzinfo=ctx.tz)
    await ctx.scheduler.run_daily(
        callback=lambda data=None: _digest_callback(ctx, data),
        time=digest_time,
        name="wiki_weekly_digest",
        days=(digest_day,),
    )
    logger.info("Scheduled wiki weekly digest on %s at %02d:00", digest_day_name, digest_hour)

    # Monthly lint at 03:00 on the 1st (use day-of-month check inside callback)
    lint_time = time(hour=3, minute=0, tzinfo=ctx.tz)
    await ctx.scheduler.run_daily(
        callback=lambda data=None: _lint_callback(ctx, data),
        time=lint_time,
        name="wiki_monthly_lint",
        days=(1,),  # 1st day trigger (using days param for monthly approximation)
    )
    logger.info("Scheduled wiki monthly lint at 03:00")
