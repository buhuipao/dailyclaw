"""Wiki query engine — two-stage retrieval with fallback to raw messages."""
from __future__ import annotations

import json
import logging
from typing import Any

from .db import WikiDB

logger = logging.getLogger(__name__)

_LANG_INSTRUCTION: dict[str, str] = {
    "zh": "用中文回答。",
    "en": "Answer in English.",
    "ja": "日本語で回答してください。",
}

_EMPTY_WIKI_MSG: dict[str, str] = {
    "zh": "你的知识库还是空的。随着你每天记录，wiki 会自动整理你的知识。",
    "en": "Your wiki is still empty. As you record daily, the wiki will organize your knowledge automatically.",
    "ja": "あなたのWikiはまだ空です。毎日記録するにつれて、Wikiが自動的に知識を整理します。",
}

_NO_DATA_MSG: dict[str, str] = {
    "zh": "暂时没有找到相关记录。继续每天记录，知识库会越来越丰富。",
    "en": "No relevant records found yet. Keep recording daily and your wiki will grow.",
    "ja": "関連する記録がまだ見つかりません。毎日記録を続ければ、Wikiは充実していきます。",
}


async def answer_question(
    llm: Any,
    wiki_db: WikiDB,
    db: Any,
    user_id: int,
    question: str,
    lang: str,
) -> str:
    """Two-stage retrieval: pick topics, then answer grounded in wiki content."""
    topic_index = await wiki_db.get_topic_index(user_id)

    if not topic_index:
        return await _fallback_raw_search(db, llm, user_id, question, lang)

    # Stage 1: LLM picks relevant topics from index
    index_desc = "\n".join(
        f"- {t['topic']}: {t['title']}"
        for t in topic_index
    )
    lang_inst = _LANG_INSTRUCTION.get(lang, _LANG_INSTRUCTION["en"])

    pick_messages = [
        {
            "role": "system",
            "content": (
                "You are a wiki search assistant. Given the user's question and the list of wiki topics, "
                "pick 1-5 most relevant topics. Return strict JSON array of topic slugs.\n"
                'Example: ["daily-routine", "reading-notes"]\n'
                "If no topic is relevant, return []."
            ),
        },
        {
            "role": "user",
            "content": f"Topics:\n{index_desc}\n\nQuestion: {question}",
        },
    ]

    raw_picks = await llm.chat(
        messages=pick_messages,
        temperature=0.1,
        max_tokens=200,
        lang=lang,
    )

    try:
        picked_topics = json.loads(raw_picks)
    except json.JSONDecodeError:
        logger.warning("[wiki-query] topic pick returned non-JSON: %s", raw_picks[:200])
        picked_topics = []

    if not isinstance(picked_topics, list):
        picked_topics = []

    # Filter to valid strings
    picked_topics = [t for t in picked_topics if isinstance(t, str)]

    if not picked_topics:
        return await _fallback_raw_search(db, llm, user_id, question, lang)

    # Stage 2: Fetch full pages and generate grounded answer
    pages = await wiki_db.get_pages(user_id, picked_topics)

    if not pages:
        return await _fallback_raw_search(db, llm, user_id, question, lang)

    pages_text = "\n\n---\n\n".join(
        f"# {p['title']} ({p['topic']})\n{p['content']}"
        for p in pages
    )

    answer_messages = [
        {
            "role": "system",
            "content": (
                "You are the user's personal knowledge assistant. "
                "Answer the question based ONLY on the wiki content provided. "
                "If the wiki doesn't contain enough information, say so honestly. "
                f"{lang_inst}"
            ),
        },
        {
            "role": "user",
            "content": f"Wiki content:\n{pages_text}\n\nQuestion: {question}",
        },
    ]

    answer = await llm.chat(
        messages=answer_messages,
        temperature=0.5,
        max_tokens=1000,
        lang=lang,
    )

    await wiki_db.log_op(
        user_id,
        "query",
        json.dumps(
            {"question": question[:100], "topics": picked_topics},
            ensure_ascii=False,
        ),
    )

    return answer


async def _fallback_raw_search(
    db: Any,
    llm: Any,
    user_id: int,
    question: str,
    lang: str,
) -> str:
    """Search last 30 days of messages and generate an answer from those."""
    lang_inst = _LANG_INSTRUCTION.get(lang, _LANG_INSTRUCTION["en"])

    # Check if messages table exists
    cursor = await db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
    )
    if not await cursor.fetchone():
        return _EMPTY_WIKI_MSG.get(lang, _EMPTY_WIKI_MSG["en"])

    cursor = await db.conn.execute(
        "SELECT content, created_at FROM messages "
        "WHERE user_id = ? AND deleted_at IS NULL "
        "AND created_at > datetime('now', '-30 days') "
        "ORDER BY created_at DESC LIMIT 50",
        (user_id,),
    )
    rows = await cursor.fetchall()

    if not rows:
        return _NO_DATA_MSG.get(lang, _NO_DATA_MSG["en"])

    msgs_text = "\n".join(
        f"[{row['created_at']}] {row['content'][:200]}"
        for row in rows
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are the user's personal assistant. "
                "Answer the question based on their recent messages. "
                "If not enough information, say so honestly. "
                f"{lang_inst}"
            ),
        },
        {
            "role": "user",
            "content": f"Recent messages:\n{msgs_text}\n\nQuestion: {question}",
        },
    ]

    return await llm.chat(
        messages=messages,
        temperature=0.5,
        max_tokens=800,
        lang=lang,
    )
