"""Retry job for failed queued messages.

The framework-level message_queue stores all failed messages. This job
picks them up and re-dispatches. Text messages get full replay (classify
+ save). Media messages get a placeholder if the file URL has expired.
"""
from __future__ import annotations

import json
import logging

from src.core.i18n import t

import src.plugins.memo.locale  # noqa: F401

logger = logging.getLogger(__name__)

MAX_RETRY_ATTEMPTS = 10


def make_retry_callback(ctx: object):
    """Return an async callback for scheduler.run_repeating."""

    async def retry_failed_messages() -> None:
        db = ctx.db
        llm = ctx.llm
        bot = ctx.bot

        pending = await _get_pending(db, MAX_RETRY_ATTEMPTS)
        if not pending:
            return

        logger.info("Retrying %d failed messages", len(pending))

        for msg in pending:
            try:
                await _retry_one(db, llm, bot, msg)
                await _mark_done(db, msg["id"])
                logger.info("Retry succeeded for queue id=%d", msg["id"])
            except Exception as exc:
                await _mark_failed(db, msg["id"], str(exc))
                logger.warning(
                    "Retry failed for queue id=%d (attempt %d): %s",
                    msg["id"], msg["attempts"] + 1, exc,
                )

    return retry_failed_messages


async def _retry_one(db: object, llm: object, bot: object, msg: dict) -> None:
    """Retry a single failed message."""
    payload = json.loads(msg["payload"])
    msg_type = msg["msg_type"]

    if msg_type == "text":
        # Full replay: classify + save
        from .handlers import _insert_message
        text = payload.get("text", "")
        classification = await llm.classify(text)
        category = classification.get("category")
        meta = dict(classification)
        metadata = json.dumps(meta, ensure_ascii=False)
        row_id = await _insert_message(db, msg["user_id"], "text", text, category, metadata)
        if row_id:
            await bot.send_message(
                msg["chat_id"],
                t("memo.retry_done", "zh", id=row_id),
            )
    elif msg_type in ("photo", "voice", "video"):
        # Media: file URL may have expired, save placeholder
        from .handlers import _insert_message
        type_label = t(f"recorder.retry_type.{msg_type}", "zh")
        content = payload.get("caption") or payload.get("text") or t("memo.retry_backfill", "zh", type=type_label)
        metadata = json.dumps(payload, ensure_ascii=False)
        row_id = await _insert_message(db, msg["user_id"], msg_type, content, None, metadata)
        if row_id:
            await bot.send_message(
                msg["chat_id"],
                t("memo.retry_media_done", "zh", type=type_label, id=row_id),
            )
    else:
        # Command or unknown type — just mark done, can't meaningfully retry
        logger.debug("Skipping retry for msg_type=%s queue_id=%d", msg_type, msg["id"])


async def _get_pending(db: object, max_attempts: int) -> list[dict]:
    """Fetch failed messages that haven't exceeded max retry attempts."""
    cursor = await db.conn.execute(
        "SELECT id, user_id, chat_id, msg_type, payload, attempts "
        "FROM message_queue WHERE status = 'failed' AND attempts < ? ORDER BY created_at",
        (max_attempts,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def _mark_done(db: object, queue_id: int) -> None:
    await db.conn.execute("UPDATE message_queue SET status = 'done' WHERE id = ?", (queue_id,))
    await db.conn.commit()


async def _mark_failed(db: object, queue_id: int, error: str) -> None:
    await db.conn.execute(
        "UPDATE message_queue SET status = 'failed', attempts = attempts + 1, last_error = ? WHERE id = ?",
        (error[:500], queue_id),
    )
    await db.conn.commit()
