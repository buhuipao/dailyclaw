"""Wiki ingest pipeline — reads source tables, asks LLM to update wiki pages."""
from __future__ import annotations

import json
import logging
from typing import Any

from .db import WikiDB

logger = logging.getLogger(__name__)

# Source table registry — reads tables directly, no imports from other plugins.
SOURCE_TABLES: list[dict[str, str]] = [
    {
        "name": "memos",
        "table": "messages",
        "content_col": "content",
        "meta_col": "metadata",
        "time_col": "created_at",
        "type_col": "msg_type",
        "filter": "deleted_at IS NULL",
    },
    {
        "name": "reflections",
        "table": "journal_entries",
        "content_col": "content",
        "category_col": "category",
        "time_col": "created_at",
    },
    {
        "name": "checkins",
        "table": "plan_checkins",
        "content_col": "note",
        "tag_col": "tag",
        "time_col": "created_at",
    },
]


async def fetch_sources_since(
    db: Any, user_id: int, since: str | None
) -> list[dict[str, Any]]:
    """Query each SOURCE_TABLE for rows since the watermark.

    Returns a flat list of {source, time, content, extra}.
    """
    results: list[dict[str, Any]] = []

    for src in SOURCE_TABLES:
        table = src["table"]
        content_col = src["content_col"]
        time_col = src["time_col"]

        # Check if the table exists before querying
        cursor = await db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not await cursor.fetchone():
            continue

        conditions = [f"user_id = ?"]
        params: list[Any] = [user_id]

        if since:
            conditions.append(f"{time_col} > ?")
            params.append(since)

        extra_filter = src.get("filter")
        if extra_filter:
            conditions.append(extra_filter)

        where = " AND ".join(conditions)

        # Build SELECT columns
        select_cols = [content_col, time_col]
        extra_cols: list[str] = []
        for key in ("meta_col", "type_col", "category_col", "tag_col"):
            col = src.get(key)
            if col:
                select_cols.append(col)
                extra_cols.append(col)

        cols_str = ", ".join(select_cols)
        query = f"SELECT {cols_str} FROM {table} WHERE {where} ORDER BY {time_col}"

        try:
            cursor = await db.conn.execute(query, params)
            rows = await cursor.fetchall()
        except Exception:
            logger.warning("Failed to query source table %s", table, exc_info=True)
            continue

        for row in rows:
            content = row[content_col]
            if not content or not content.strip():
                continue

            extra_parts: list[str] = []
            for col in extra_cols:
                val = row[col]
                if val:
                    extra_parts.append(f"{col}={val}")

            results.append({
                "source": src["name"],
                "time": row[time_col],
                "content": content,
                "extra": ", ".join(extra_parts) if extra_parts else "",
            })

    return results


def build_ingest_prompt(
    topic_index: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    lang: str,
) -> list[dict[str, str]]:
    """Build system + user messages for the LLM ingest call."""
    # Describe existing topics
    if topic_index:
        topics_desc = "\n".join(
            f"- {t['topic']}: {t['title']} (sources: {t['source_count']})"
            for t in topic_index
        )
    else:
        topics_desc = "(no existing topics)"

    lang_instruction = {
        "zh": "用中文撰写 wiki 内容。",
        "en": "Write wiki content in English.",
        "ja": "Wiki内容は日本語で記述してください。",
    }.get(lang, "Write wiki content in English.")

    system_msg = (
        "You are a personal knowledge wiki maintainer. "
        "The user's existing wiki topics are:\n"
        f"{topics_desc}\n\n"
        "Rules:\n"
        "1. Analyze the new source material and decide which wiki topics to create or update.\n"
        "2. For each topic, provide the FULL updated content (not a diff).\n"
        "3. Topic slugs: lowercase, hyphens, no spaces (e.g. 'daily-routine', 'reading-notes').\n"
        "4. Link related topics using [[topic-slug]] syntax inside content.\n"
        "5. Merge closely related material into existing topics when appropriate.\n"
        "6. Only create new topics when the material doesn't fit existing ones.\n"
        "7. If no sources warrant any update, return an empty JSON array [].\n"
        f"8. {lang_instruction}\n\n"
        "Return strict JSON (no markdown wrapping):\n"
        '[{"topic": "slug", "title": "Human Title", "action": "create|update", '
        '"content": "full page content", "links": ["related-topic"], "reason": "why"}]'
    )

    # Build source listing
    source_lines: list[str] = []
    for s in sources:
        line = f"[{s['source']}] ({s['time']}) {s['content'][:300]}"
        if s.get("extra"):
            line += f" [{s['extra']}]"
        source_lines.append(line)

    user_msg = "New source material:\n" + "\n".join(source_lines)

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


async def run_ingest(
    db: Any,
    llm: Any,
    wiki_db: WikiDB,
    user_id: int,
    lang: str,
) -> dict[str, int]:
    """Main ingest: fetch sources, ask LLM, upsert pages, log operation.

    Returns {created, updated, sources}.
    """
    watermark = await wiki_db.get_global_watermark(user_id)
    sources = await fetch_sources_since(db, user_id, watermark)

    if not sources:
        return {"created": 0, "updated": 0, "sources": 0}

    topic_index = await wiki_db.get_topic_index(user_id)
    messages = build_ingest_prompt(topic_index, sources, lang)

    raw = await llm.chat(
        messages=messages,
        temperature=0.3,
        max_tokens=3000,
        lang=lang,
    )

    try:
        updates = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[wiki-ingest] LLM returned non-JSON: %s", raw[:200])
        return {"created": 0, "updated": 0, "sources": len(sources)}

    if not isinstance(updates, list):
        logger.warning("[wiki-ingest] LLM returned non-list: %s", type(updates))
        return {"created": 0, "updated": 0, "sources": len(sources)}

    created = 0
    updated = 0

    for item in updates:
        topic = item.get("topic", "")
        title = item.get("title", "")
        content = item.get("content", "")
        links = item.get("links", [])
        action = item.get("action", "update")

        if not topic or not title or not content:
            continue

        if not isinstance(links, list):
            links = []

        await wiki_db.upsert_page(
            user_id=user_id,
            topic=topic,
            title=title,
            content=content,
            links=links,
            page_type="organic",
            source_delta=len(sources),
        )

        if action == "create":
            created += 1
        else:
            updated += 1

    detail = json.dumps(
        {"created": created, "updated": updated, "sources": len(sources)},
        ensure_ascii=False,
    )
    await wiki_db.log_op(user_id, "ingest", detail)

    return {"created": created, "updated": updated, "sources": len(sources)}
