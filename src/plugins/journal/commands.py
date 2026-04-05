"""Journal plugin command handlers."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from src.core.i18n import t
from src.core.i18n.shared import category_label

import src.plugins.journal.locale  # noqa: F401

if TYPE_CHECKING:
    from src.core.bot import Event
    from src.core.context import AppContext

logger = logging.getLogger(__name__)

# Module-level session registry: user_id -> JournalEngine
_sessions: dict[int, object] = {}


def _get_ctx() -> "AppContext":
    from src.plugins.journal import _plugin_ctx
    return _plugin_ctx


def _get_today(ctx: "AppContext") -> str:
    return datetime.now(ctx.tz).strftime("%Y-%m-%d")


async def cmd_journal_start(event: "Event") -> str:
    from .db import JournalDB
    from .engine import JournalEngine

    ctx = _get_ctx()
    user_id = event.user_id

    if user_id in _sessions:
        return t("journal.already_in_session", event.lang)

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


async def cmd_journal_today(event: "Event") -> str:
    from .db import JournalDB

    ctx = _get_ctx()
    journal_db = JournalDB(ctx.db)
    entries = await journal_db.get_journal_entries(event.user_id, _get_today(ctx))

    if not entries:
        return t("journal.today_empty", event.lang)

    lines = [t("journal.today_header", event.lang, date=_get_today(ctx))]
    for entry in entries:
        label = category_label(entry["category"], event.lang)
        lines.append(f"【{label}】{entry['content']}")
    return "\n".join(lines)


async def cmd_journal_cancel(event: "Event") -> str:
    user_id = event.user_id
    if user_id in _sessions:
        del _sessions[user_id]
        return t("journal.cancelled", event.lang)
    return t("journal.no_session", event.lang)


async def cmd_journal_summary(event: "Event") -> str:
    """Handle /journal_summary [YYYY-MM-DD] — summarize journal from date to today."""
    from .db import JournalDB
    from .summary import generate_summary

    ctx = _get_ctx()
    lang = event.lang
    text = (event.text or "").strip()

    today = _get_today(ctx)

    if text:
        # Validate date format
        if not re.match(r"\d{4}-\d{2}-\d{2}$", text):
            return t("journal.summary_usage", lang)
        start_date = text
    else:
        # Default: last 7 days
        start_date = (datetime.now(ctx.tz) - timedelta(days=6)).strftime("%Y-%m-%d")

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


async def journal_answer_handler(event: "Event") -> str | tuple[str, bool] | None:
    """Conversation state handler.

    Returns:
        None          — not in a session, pass through
        str           — reply text, stay in conversation
        (str, True)   — reply text, then end conversation
    """
    user_id = event.user_id
    engine = _sessions.get(user_id)
    if engine is None:
        return None  # Not in a journal session — pass through

    text = event.text or ""
    response = await engine.answer(text)  # type: ignore[union-attr]

    if engine.is_complete:  # type: ignore[union-attr]
        del _sessions[user_id]
        return (response, True)

    return response
