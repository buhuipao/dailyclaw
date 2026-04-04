"""Recorder plugin commands."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.core.bot import Event

logger = logging.getLogger(__name__)


async def recorder_del(db: object, event: Event) -> str | None:
    """Handle /recorder_del <id> — soft delete a recorded message.

    Validates that the ID is a valid integer, the message exists,
    and the requesting user owns that message before soft-deleting.

    Returns a user-facing confirmation or error string.
    """
    text = (event.text or "").strip()
    if not text or not text.lstrip("-").isdigit():
        return "❌ 请提供要删除的记录 ID，例如：/recorder_del 42"

    record_id = int(text)
    if record_id <= 0:
        return "❌ 记录 ID 必须是正整数。"

    row = await _fetch_message(db, record_id)
    if row is None:
        return f"❌ 找不到记录 #{record_id}。"

    if row["user_id"] != event.user_id:
        return "❌ 你无权删除此记录。"

    if row["deleted_at"] is not None:
        return f"❌ 记录 #{record_id} 已经删除过了。"

    deleted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    await db.conn.execute(
        "UPDATE messages SET deleted_at = ? WHERE id = ?",
        (deleted_at, record_id),
    )
    await db.conn.commit()

    logger.info("[recorder_del] soft-deleted id=%d user=%d", record_id, event.user_id)
    return f"✅ 记录 #{record_id} 已删除。"


async def recorder_today(db: object, tz: object, event: Event) -> str | None:
    """Handle /recorder_today — show today's recorded messages."""
    today = datetime.now(tz).strftime("%Y-%m-%d")
    cursor = await db.conn.execute(
        "SELECT id, msg_type, content, category, created_at FROM messages "
        "WHERE user_id = ? AND date(created_at) = ? AND deleted_at IS NULL "
        "ORDER BY created_at",
        (event.user_id, today),
    )
    rows = await cursor.fetchall()

    if not rows:
        return f"📭 {today} 还没有记录。随时发消息给我吧！"

    lines = [f"📅 {today} 今日记录 ({len(rows)} 条)\n"]
    for row in rows[-15:]:  # show last 15
        prefix = {"link": "🔗", "photo": "📷", "voice": "🎤", "video": "🎬"}.get(
            row["msg_type"], "💬"
        )
        content = row["content"][:60]
        if len(row["content"]) > 60:
            content += "..."
        lines.append(f"  {prefix} #{row['id']} {content}")

    if len(rows) > 15:
        lines.append(f"\n  ...还有 {len(rows) - 15} 条更早的记录")

    return "\n".join(lines)


async def _fetch_message(db: object, record_id: int) -> object | None:
    """Fetch a single message row by ID."""
    cursor = await db.conn.execute(
        "SELECT id, user_id, deleted_at FROM messages WHERE id = ?",
        (record_id,),
    )
    return await cursor.fetchone()
