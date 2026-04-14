"""Wiki lint — detect orphans, contradictions, stale content, merge candidates."""
from __future__ import annotations

import json
import logging
from typing import Any

from .db import WikiDB

logger = logging.getLogger(__name__)

_LANG_INSTRUCTION: dict[str, str] = {
    "zh": "用中文撰写报告。",
    "en": "Write the report in English.",
    "ja": "レポートは日本語で記述してください。",
}


def _build_link_graph(pages: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Build a directed link graph from page data.

    Returns {topic: [topics that link TO this topic]}.
    """
    inbound: dict[str, list[str]] = {p["topic"]: [] for p in pages}

    for page in pages:
        topic = page["topic"]
        try:
            links = json.loads(page.get("links", "[]"))
        except (json.JSONDecodeError, TypeError):
            links = []

        for target in links:
            if target in inbound:
                inbound[target] = [*inbound[target], topic]

    return inbound


def _find_orphans(
    pages: list[dict[str, Any]], inbound_graph: dict[str, list[str]]
) -> list[str]:
    """Find topics with no inbound links (orphans)."""
    return [
        p["topic"]
        for p in pages
        if not inbound_graph.get(p["topic"])
    ]


async def run_lint(
    llm: Any,
    wiki_db: WikiDB,
    user_id: int,
    lang: str,
) -> str | None:
    """Lint the wiki: detect orphans, contradictions, stale content, merge candidates.

    Returns a report string, or None if the wiki is empty.
    """
    topic_index = await wiki_db.get_topic_index(user_id)
    if not topic_index:
        return None

    topics = [t["topic"] for t in topic_index]
    pages = await wiki_db.get_pages(user_id, topics)

    if not pages:
        return None

    # Build link graph and find orphans
    inbound_graph = _build_link_graph(pages)
    orphans = _find_orphans(pages, inbound_graph)

    # Build page summaries for LLM analysis
    pages_desc = "\n\n".join(
        f"## {p['title']} ({p['topic']})\n"
        f"Links: {p.get('links', '[]')}\n"
        f"Content preview: {p['content'][:300]}"
        for p in pages
    )

    orphan_note = ""
    if orphans:
        orphan_note = f"\n\nOrphan topics (no inbound links): {', '.join(orphans)}"

    lang_inst = _LANG_INSTRUCTION.get(lang, _LANG_INSTRUCTION["en"])

    messages = [
        {
            "role": "system",
            "content": (
                "You are a personal wiki quality reviewer. "
                "Analyze the user's wiki for issues and provide a concise report.\n"
                "Check for:\n"
                "1. Orphan pages (listed below) — suggest how to link them\n"
                "2. Potential contradictions between pages\n"
                "3. Stale or outdated content\n"
                "4. Pages that could be merged\n"
                "5. Knowledge gaps — topics that should exist but don't\n\n"
                "Use emoji markers. Keep it actionable and concise. "
                f"No markdown headers. {lang_inst}"
            ),
        },
        {
            "role": "user",
            "content": f"Wiki pages ({len(pages)} total):\n{pages_desc}{orphan_note}",
        },
    ]

    report = await llm.chat(
        messages=messages,
        temperature=0.5,
        max_tokens=1000,
        lang=lang,
    )

    return report
