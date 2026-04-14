"""Wiki nudge — detect when user content connects to a wiki topic."""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from .db import WikiDB

logger = logging.getLogger(__name__)

# In-memory daily counter: {user_id: {date_str: count}}
_daily_counts: dict[int, dict[str, int]] = {}


def _get_today_count(user_id: int) -> int:
    """Return the number of nudges sent today for this user."""
    today = date.today().isoformat()
    user_counts = _daily_counts.get(user_id, {})
    return user_counts.get(today, 0)


def _increment_today_count(user_id: int) -> None:
    """Increment the nudge count for today (creates new dict entries, no mutation)."""
    today = date.today().isoformat()
    user_counts = dict(_daily_counts.get(user_id, {}))
    user_counts[today] = user_counts.get(today, 0) + 1
    _daily_counts[user_id] = user_counts


async def check_nudge(
    llm: Any,
    wiki_db: WikiDB,
    user_id: int,
    content: str,
    lang: str,
    threshold: float = 0.85,
    max_per_day: int = 3,
) -> str | None:
    """Check if user content connects to any wiki topic.

    Returns a nudge message if confidence >= threshold, else None.
    Rate-limited to max_per_day nudges per user.
    """
    if _get_today_count(user_id) >= max_per_day:
        return None

    topic_index = await wiki_db.get_topic_index(user_id)
    if not topic_index:
        return None

    index_desc = "\n".join(
        f"- {t['topic']}: {t['title']}"
        for t in topic_index
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a personal wiki nudge assistant. "
                "Check if the user's new message connects to any of their wiki topics. "
                "Return strict JSON (no markdown):\n"
                '{"connected": true/false, "confidence": 0.0-1.0, '
                '"topic": "matched-topic-slug", "nudge": "brief connection message"}\n'
                "Only return connected=true if you are very confident the content "
                "relates to an existing topic. The nudge should be a short, helpful "
                "observation (1 sentence)."
            ),
        },
        {
            "role": "user",
            "content": f"Wiki topics:\n{index_desc}\n\nNew content: {content[:500]}",
        },
    ]

    raw = await llm.chat(
        messages=messages,
        temperature=0.2,
        max_tokens=200,
        lang=lang,
    )

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.debug("[wiki-nudge] LLM returned non-JSON: %s", raw[:200])
        return None

    if not isinstance(result, dict):
        return None

    connected = result.get("connected", False)
    confidence = float(result.get("confidence", 0.0))
    nudge_msg = result.get("nudge", "")

    if connected and confidence >= threshold and nudge_msg:
        _increment_today_count(user_id)
        return nudge_msg

    return None
