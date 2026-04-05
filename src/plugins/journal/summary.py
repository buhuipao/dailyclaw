"""Generate periodic summaries (weekly/monthly/quarterly/yearly) via LLM."""
from __future__ import annotations

import logging

from src.core.i18n import t
from src.core.i18n.shared import category_label, period_label

import src.plugins.journal.locale  # noqa: F401

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
    """Generate and save a summary for the given period."""
    entries = await db.get_journal_range(user_id, start_date, end_date)
    period_lbl = (
        f"{start_date} ~ {end_date}"
        if period_type == "custom"
        else period_label(period_type, lang)
    )

    if not entries:
        return t("journal.no_entries", lang, period=period_lbl)

    entry_text = "\n".join(
        f"- {e['date']} [{category_label(e['category'], lang)}] {e['content'][:120]}"
        for e in entries
    )

    response = await llm.chat(
        messages=[
            {
                "role": "system",
                "content": t("journal.summary_system_prompt", lang, period=period_lbl),
            },
            {
                "role": "user",
                "content": t("journal.summary_user_prompt", lang, start=start_date, end=end_date, entries=entry_text),
            },
        ],
        max_tokens=500,
        lang=lang,
    )

    await db.save_summary(user_id, period_type, start_date, end_date, response)
    return response
