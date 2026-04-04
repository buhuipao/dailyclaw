"""Generate periodic summaries (weekly/monthly) via LLM."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

PERIOD_LABELS: dict[str, str] = {
    "week": "本周",
    "month": "本月",
}

CATEGORY_LABELS: dict[str, str] = {
    "morning": "晨起",
    "reading": "所阅",
    "social": "待人接物",
    "reflection": "反省",
}


async def generate_summary(
    db: object,
    llm: object,
    user_id: int,
    period_type: str,
    start_date: str,
    end_date: str,
) -> str:
    """Generate and save a summary for the given period.

    Reads from journal_entries and saves to summaries.
    Both tables are owned by the journal plugin's migrations.
    """
    entries = await _get_journal_range(db, user_id, start_date, end_date)
    period_label = PERIOD_LABELS.get(period_type, period_type)

    if not entries:
        return f"{period_label}没有记录。开始用 /journal_start 记录每天的反思吧！"

    entry_text = "\n".join(
        f"- {e['date']} [{CATEGORY_LABELS.get(e['category'], e['category'])}] {e['content'][:120]}"
        for e in entries
    )

    response = await llm.chat(
        messages=[
            {
                "role": "system",
                "content": (
                    f"你是 DailyClaw 的总结助手。请为用户生成{period_label}总结。\n"
                    "包含：1) 整体评价 2) 做得好的地方 3) 需要改进的地方 4) 一句鼓励\n"
                    "简洁有力，用中文，300字以内。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"时间范围：{start_date} ~ {end_date}\n\n"
                    f"日记条目：\n{entry_text}"
                ),
            },
        ],
        max_tokens=500,
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
