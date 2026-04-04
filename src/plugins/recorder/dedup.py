"""Semantic deduplication for recorder messages."""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

_DEDUP_SYSTEM_PROMPT = """你是 DailyClaw 的去重助手。用户刚发来一条新消息，请判断它是否与最近的历史消息语义重复。

返回严格的 JSON 格式（不要 markdown 包裹）：

如果不重复：
{"duplicate": false}

如果重复：
{"duplicate": true, "duplicate_of": <id>, "action": "merge"|"replace", "merged_content": "合并后的内容"}

规则：
- duplicate: 仅当新消息与某条历史消息表达相同或高度相似的内容时为 true
- action:
  - "merge" — 两条消息互补，合并成一条更完整的记录
  - "replace" — 新消息是对旧消息的更新或更清晰的表达，直接替换
- merged_content: 合并或替换后的内容文字，仅在 duplicate=true 时提供
- 如有多条重复，选择最相似的那一条"""


async def check_dedup(
    db: object,
    llm: object,
    user_id: int,
    new_content: str,
    window: int = 10,
) -> dict | None:
    """Check if new_content is a semantic duplicate of recent messages.

    Args:
        db: Database instance with conn attribute (aiosqlite connection).
        llm: LLMService instance with chat() method.
        user_id: The user's Telegram ID.
        new_content: The new message content to check.
        window: How many recent messages to look back through.

    Returns:
        None if not a duplicate.
        Dict with keys duplicate_of, action, merged_content if duplicate.
    """
    recent = await _fetch_recent_messages(db, user_id, window)
    if not recent:
        return None

    history_text = "\n".join(
        f'[id={row["id"]}] {row["content"][:200]}' for row in recent
    )
    prompt = (
        f"最近 {len(recent)} 条历史记录：\n{history_text}\n\n"
        f"新消息：{new_content[:300]}"
    )

    try:
        raw = await llm.chat(
            messages=[
                {"role": "system", "content": _DEDUP_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=300,
        )
        result = json.loads(raw)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("[dedup] LLM call or parse failed: %s", exc)
        return None

    if not result.get("duplicate"):
        return None

    dup_id = result.get("duplicate_of")
    action = result.get("action", "merge")
    merged = result.get("merged_content", new_content)

    if dup_id is None:
        logger.warning("[dedup] duplicate=true but no duplicate_of field")
        return None

    logger.info(
        "[dedup] duplicate detected: new vs id=%s action=%s", dup_id, action
    )
    return {
        "duplicate_of": int(dup_id),
        "action": action,
        "merged_content": merged,
    }


async def _fetch_recent_messages(db: object, user_id: int, limit: int) -> list:
    """Fetch the most recent non-deleted messages for a user."""
    cursor = await db.conn.execute(
        "SELECT id, content FROM messages "
        "WHERE user_id = ? AND deleted_at IS NULL "
        "ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    )
    return await cursor.fetchall()
