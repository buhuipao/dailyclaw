"""Wiki digest — weekly insight generation from recently updated pages."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from .db import WikiDB

logger = logging.getLogger(__name__)

_LANG_INSTRUCTION: dict[str, str] = {
    "zh": "用中文撰写。",
    "en": "Write in English.",
    "ja": "日本語で記述してください。",
}


async def generate_digest(
    llm: Any,
    wiki_db: WikiDB,
    user_id: int,
    lang: str,
    days: int = 7,
) -> str | None:
    """Generate a weekly digest from pages updated in the last N days.

    Returns None if no pages were updated.
    """
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    pages = await wiki_db.get_pages_updated_since(user_id, since)

    if not pages:
        return None

    pages_summary = "\n".join(
        f"- {p['title']} ({p['topic']}): {p['content'][:200]}..."
        for p in pages
    )

    lang_inst = _LANG_INSTRUCTION.get(lang, _LANG_INSTRUCTION["en"])

    messages = [
        {
            "role": "system",
            "content": (
                "You are a personal knowledge wiki assistant. "
                "Generate a weekly insight digest from the user's recently updated wiki pages.\n"
                "Include:\n"
                "1. Key themes this week\n"
                "2. Interesting connections between topics\n"
                "3. Notable progress or changes\n"
                "4. One suggestion for the coming week\n\n"
                "Keep it concise (under 300 words). Use emoji markers for sections. "
                f"No markdown headers. {lang_inst}"
            ),
        },
        {
            "role": "user",
            "content": f"Updated wiki pages ({len(pages)} pages in the last {days} days):\n\n{pages_summary}",
        },
    ]

    result = await llm.chat(
        messages=messages,
        temperature=0.5,
        max_tokens=800,
        lang=lang,
    )

    return result
