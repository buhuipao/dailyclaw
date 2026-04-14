"""Reflect plugin command handlers."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from src.core.i18n import t
from src.core.i18n.shared import category_label

import src.plugins.reflect.locale  # noqa: F401

if TYPE_CHECKING:
    from src.core.bot import Event
    from src.core.context import AppContext

logger = logging.getLogger(__name__)

# Module-level session registry: user_id -> JournalEngine
_sessions: dict[int, object] = {}


def _get_ctx() -> "AppContext":
    from src.plugins.reflect import _plugin_ctx
    return _plugin_ctx


def _get_today(ctx: "AppContext") -> str:
    return datetime.now(ctx.tz).strftime("%Y-%m-%d")


async def cmd_reflect(event: "Event") -> str:
    from .db import JournalDB
    from .engine import JournalEngine

    ctx = _get_ctx()
    user_id = event.user_id

    if user_id in _sessions:
        return t("reflect.already_in_session", event.lang)

    journal_db = JournalDB(ctx.db)
    engine = JournalEngine(
        db=journal_db,
        llm=ctx.llm,
        user_id=user_id,
        date=_get_today(ctx),
        lang=event.lang,
    )
    _sessions[user_id] = engine
    return await engine.start()


async def cmd_cancel(event: "Event") -> str:
    user_id = event.user_id
    if user_id in _sessions:
        del _sessions[user_id]
        return t("reflect.cancelled", event.lang)
    return t("reflect.no_session", event.lang)


async def cmd_review(event: "Event") -> str:
    """Handle /review [YYYY-MM-DD] — review journal from date to today."""
    ctx = _get_ctx()
    lang = event.lang
    text = (event.text or "").strip()

    today = _get_today(ctx)

    if text:
        if not re.match(r"\d{4}-\d{2}-\d{2}$", text):
            return t("reflect.review_usage", lang)
        start_date = text
    else:
        start_date = (datetime.now(ctx.tz) - timedelta(days=6)).strftime("%Y-%m-%d")

    # Try wiki query first
    try:
        from src.plugins.wiki.db import WikiDB
        wiki_db = WikiDB(ctx.db)
        index = await wiki_db.get_topic_index(event.user_id)
        if index:
            from src.plugins.wiki.query import answer_question
            question = (
                f"Review and summarize my life from {start_date} to {today}. "
                "Cover themes, progress, mood, and any patterns."
            )
            result = await answer_question(
                llm=ctx.llm, wiki_db=wiki_db, db=ctx.db,
                user_id=event.user_id, question=question, lang=lang,
            )
            return f"📊 {start_date} ~ {today}\n\n{result}"
    except ImportError:
        pass
    except Exception:
        logger.debug("[review] wiki query failed, falling back to legacy", exc_info=True)

    # Fallback: legacy summary
    from .db import JournalDB
    from .summary import generate_summary

    journal_db = JournalDB(ctx.db)
    result = await generate_summary(
        db=journal_db,
        llm=ctx.llm,
        user_id=event.user_id,
        period_type="custom",
        start_date=start_date,
        end_date=today,
        lang=lang,
    )
    return f"📊 {start_date} ~ {today}\n\n{result}"


async def reflect_answer_handler(event: "Event") -> str | tuple[str, bool] | None:
    """Conversation state handler.

    Returns:
        None          — not in a session, pass through
        str           — reply text, stay in conversation
        (str, True)   — reply text, then end conversation
    """
    user_id = event.user_id
    engine = _sessions.get(user_id)
    if engine is None:
        return None  # Not in a reflect session — pass through

    text = event.text or ""
    response = await engine.answer(text)  # type: ignore[union-attr]

    if engine.is_complete:  # type: ignore[union-attr]
        del _sessions[user_id]
        return (response, True)

    return response
