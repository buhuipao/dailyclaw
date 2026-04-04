"""Retry job for failed queued messages in the recorder plugin."""
from __future__ import annotations

import json
import logging

from .handlers import _insert_message, _mark_done, _mark_failed, _process_text

logger = logging.getLogger(__name__)

MAX_RETRY_ATTEMPTS = 10


def make_retry_callback(ctx: object):
    """Return an async callback suitable for use with scheduler.run_repeating."""

    async def retry_failed_messages() -> None:
        """Pick up failed messages and retry processing.

        Text messages are fully replayed (classify + save).
        Media messages save a placeholder to avoid data loss if the
        Telegram file download URL has expired.
        """
        db = ctx.db
        llm = ctx.llm
        bot = ctx.bot

        pending = await _get_pending(db, MAX_RETRY_ATTEMPTS)
        if not pending:
            return

        logger.info("Retrying %d failed messages", len(pending))

        for msg in pending:
            payload = json.loads(msg["payload"])
            try:
                if msg["msg_type"] == "text":
                    reply = await _process_text(db, llm, msg["user_id"], payload["text"])
                    await _mark_done(db, msg["id"])
                    await bot.send_message(
                        msg["chat_id"],
                        f"✅ 之前失败的消息已处理完成：\n{reply}",
                    )
                else:
                    await _retry_media_fallback(db, msg, payload)
                    await _mark_done(db, msg["id"])
                    await bot.send_message(
                        msg["chat_id"],
                        f"✅ 之前失败的{_type_label(msg['msg_type'])}已补录。",
                    )

                logger.info("Retry succeeded for queue id=%d", msg["id"])

            except Exception as exc:
                await _mark_failed(db, msg["id"], str(exc))
                logger.warning(
                    "Retry failed for queue id=%d (attempt %d): %s",
                    msg["id"], msg["attempts"] + 1, exc,
                )

    return retry_failed_messages


async def _get_pending(db: object, max_attempts: int) -> list[dict]:
    """Fetch failed messages that haven't exceeded max retry attempts."""
    cursor = await db.conn.execute(
        "SELECT id, user_id, chat_id, msg_type, payload, attempts "
        "FROM message_queue WHERE status = 'failed' AND attempts < ? ORDER BY created_at",
        (max_attempts,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def _retry_media_fallback(db: object, msg: dict, payload: dict) -> None:
    """Save a minimal placeholder record for media that failed processing."""
    type_map = {
        "photo": "photo",
        "voice": "voice",
        "video": "video",
    }
    msg_type = type_map.get(msg["msg_type"], "text")
    content = payload.get("caption") or f"[{_type_label(msg['msg_type'])}，处理时失败已补录]"
    metadata = json.dumps(payload, ensure_ascii=False)
    await _insert_message(db, msg["user_id"], msg_type, content, None, metadata)


def _type_label(msg_type: str) -> str:
    return {"photo": "图片", "voice": "语音", "video": "视频"}.get(msg_type, "消息")
