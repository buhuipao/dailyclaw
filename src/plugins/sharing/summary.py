"""Generate periodic summaries (weekly/monthly) via LLM."""
from __future__ import annotations

import logging

from src.core.i18n import t
from src.core.i18n.shared import category_label, period_label

import src.plugins.sharing.locale  # noqa: F401

logger = logging.getLogger(__name__)


async def generate_summary(
    db: object,
    llm: object,
    user_id: int,
    period_type: str,
    start_date: str,
    end_date: str,
    lang: str = "zh",
) -> str:
    """Generate and save a summary for the given period.

    Reads from journal_entries and saves to summaries.
    Both tables are owned by the journal plugin's migrations.
    """
    entries = await _get_journal_range(db, user_id, start_date, end_date)
    period_lbl = period_label(period_type, lang)

    if not entries:
        return t("sharing.no_entries", lang, period=period_lbl)

    entry_text = "\n".join(
        f"- {e['date']} [{category_label(e['category'], lang)}] {e['content'][:120]}"
        for e in entries
    )

    response = await llm.chat(
        messages=[
            {
                "role": "system",
                "content": t("sharing.summary_system_prompt", lang, period=period_lbl),
            },
            {
                "role": "user",
                "content": f"{start_date} ~ {end_date}\n\n{entry_text}",
            },
        ],
        max_tokens=500,
        lang=lang,
    )

    await _save_summary(db, user_id, period_type, start_date, end_date, response)
    return response


async def _get_journal_range(
    db: object, user_id: int, start_date: str, end_date: str
) -> list[dict]:
    """Fetch journal entries for a date range."""
    try:
        cursor = await db.conn.execute(
            "SELECT date, category, content FROM journal_entries "
            "WHERE user_id = ? AND date BETWEEN ? AND ? "
            "ORDER BY date, category",
            (user_id, start_date, end_date),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        logger.warning("journal_entries table unavailable", exc_info=True)
        return []


async def _save_summary(
    db: object,
    user_id: int,
    period_type: str,
    period_start: str,
    period_end: str,
    content: str,
) -> None:
    """Persist the generated summary to the summaries table."""
    try:
        await db.conn.execute(
            "INSERT INTO summaries (user_id, period_type, period_start, period_end, content) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, period_type, period_start, period_end, content),
        )
        await db.conn.commit()
    except Exception:
        logger.warning("Could not save summary (summaries table may not exist)", exc_info=True)
