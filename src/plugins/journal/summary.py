"""Generate periodic summaries (weekly/monthly/quarterly/yearly) via LLM."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

PERIOD_LABELS = {
    "week": "本周",
    "month": "本月",
    "quarter": "本季度",
    "year": "本年",
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
    """Generate and save a summary for the given period."""
    entries = await db.get_journal_range(user_id, start_date, end_date)
    period_label = PERIOD_LABELS.get(period_type, period_type)

    if not entries:
        return f"{period_label}没有记录。开始用 /journal 记录每天的反思吧！"

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

    await db.save_summary(user_id, period_type, start_date, end_date, response)
    return response
