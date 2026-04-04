"""Recorder plugin message handlers for text/photo/voice/video."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime

from src.core.bot import Event, MessageHandler, MessageType

from .dedup import check_dedup
from .url_fetcher import extract_readable_text, fetch_url

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"https?://\S+")

CATEGORY_MAP = {
    "morning": "morning",
    "reading": "reading",
    "social": "social",
    "reflection": "reflection",
}

CATEGORY_LABELS = {
    "morning": "晨起",
    "reading": "所阅",
    "social": "待人接物",
    "reflection": "反省",
    "idea": "想法",
    "other": "记录",
}

_ACK_TEXT = "💬 收到，正在处理..."
_ACK_PHOTO = "📷 图片收到，正在处理..."
_ACK_VOICE = "🎤 语音收到，正在保存..."
_ACK_VIDEO = "🎬 视频收到，正在保存..."


def make_handlers(ctx: object) -> list[MessageHandler]:
    """Build and return all message handlers for the recorder plugin."""
    return [
        MessageHandler(msg_type=MessageType.TEXT, handler=_make_text_handler(ctx)),
        MessageHandler(msg_type=MessageType.PHOTO, handler=_make_photo_handler(ctx)),
        MessageHandler(msg_type=MessageType.VOICE, handler=_make_voice_handler(ctx)),
        MessageHandler(msg_type=MessageType.VIDEO, handler=_make_video_handler(ctx)),
    ]


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

def _make_text_handler(ctx: object):
    async def handle_text(event: Event) -> None:
        db = ctx.db
        llm = ctx.llm
        bot = ctx.bot
        text = event.text or ""
        user_id = event.user_id
        chat_id = event.chat_id

        logger.debug("[recv] text from user=%d len=%d: %.80s", user_id, len(text), text)

        payload = json.dumps({"text": text}, ensure_ascii=False)
        queue_id = await _enqueue(db, user_id, chat_id, "text", payload)
        logger.debug("[queue] enqueued id=%d type=text user=%d", queue_id, user_id)

        ack_msg_id = await _try_ack(bot, event, _ACK_TEXT)

        asyncio.create_task(
            _bg_process_text(bot, db, llm, user_id, chat_id, text, queue_id, ack_msg_id)
        )

    return handle_text


async def _bg_process_text(
    bot: object,
    db: object,
    llm: object,
    user_id: int,
    chat_id: int,
    text: str,
    queue_id: int,
    ack_msg_id: int,
) -> None:
    try:
        reply = await _process_text(db, llm, user_id, text)
        await _mark_done(db, queue_id)
    except Exception as exc:
        await _mark_failed(db, queue_id, str(exc))
        logger.warning("[queue] processing failed id=%d, will retry: %s", queue_id, exc)
        await _try_edit(bot, chat_id, ack_msg_id, "⏳ 消息已收到，处理暂时失败，稍后会自动重试。")
        return

    logger.debug("[send] reply to user=%d len=%d: %.80s", user_id, len(reply), reply)
    await _try_send_reply(bot, chat_id, ack_msg_id, reply)


async def _process_text(db: object, llm: object, user_id: int, text: str) -> str:
    """Core text processing: classify, dedup, URL-fetch, save, build reply."""
    urls = URL_PATTERN.findall(text)
    has_url = bool(urls)

    logger.debug("[process] classifying text for user=%d", user_id)
    classification = await llm.classify(text)
    category = classification.get("category")
    logger.debug("[process] classified as category=%s tags=%s", category, classification.get("tags"))

    url_summary = ""
    if has_url:
        first_url = urls[0]
        logger.debug("[process] fetching URL: %s", first_url)
        html = await fetch_url(first_url)
        if html:
            readable = extract_readable_text(html, url=first_url)
            logger.debug("[process] extracted readable text len=%d", len(readable) if readable else 0)
            if readable:
                logger.debug("[process] summarizing URL content")
                url_summary = await llm.summarize_text(text=readable, url=first_url)

    meta = dict(classification)
    if url_summary:
        meta["url_summary"] = url_summary
    metadata = json.dumps(meta, ensure_ascii=False)
    msg_type = "link" if has_url else "text"

    # Semantic dedup check
    dedup = await check_dedup(db, llm, user_id, text)
    if dedup is not None:
        row_id = await _apply_dedup(db, user_id, dedup, text, msg_type, category, metadata)
        if row_id is None:
            return "这条消息刚刚已经记录过了，不会重复保存。"
        cat_label = CATEGORY_LABELS.get(category, "记录")
        summary = classification.get("summary", "")
        reply = f"已更新今日「{cat_label}」(#{row_id})。"
        if summary and summary != text[:50]:
            reply += f"\n📝 {summary}"
        reply += f"\n\n有误？发送 /recorder_del {row_id}"
        return reply

    row_id = await _insert_message(db, user_id, msg_type, text, category, metadata)
    if row_id is None:
        return "这条消息刚刚已经记录过了，不会重复保存。"

    cat_label = CATEGORY_LABELS.get(category, "记录")
    summary = classification.get("summary", "")
    reply = f"已记录到今日「{cat_label}」(#{row_id})\n📝 {summary}" if summary and summary != text[:50] else f"已记录到今日「{cat_label}」(#{row_id})。"
    if url_summary:
        reply += f"\n\n🔗 链接摘要：\n{url_summary}"
    else:
        reply += "\n\n有更多想补充的吗？"
    reply += f"\n\n有误？发送 /recorder_del {row_id}"
    return reply


# ---------------------------------------------------------------------------
# Photo
# ---------------------------------------------------------------------------

def _make_photo_handler(ctx: object):
    async def handle_photo(event: Event) -> None:
        db = ctx.db
        bot = ctx.bot
        llm = ctx.llm
        user_id = event.user_id
        chat_id = event.chat_id
        file_id = event.photo_file_id or ""
        caption = event.caption or ""
        today = datetime.now(ctx.tz).strftime("%Y-%m-%d")

        logger.debug("[recv] photo from user=%d file_id=%s caption=%r", user_id, file_id[:20], caption[:50])

        payload = json.dumps({"file_id": file_id, "caption": caption, "date": today}, ensure_ascii=False)
        queue_id = await _enqueue(db, user_id, chat_id, "photo", payload)
        logger.debug("[queue] enqueued id=%d type=photo user=%d", queue_id, user_id)

        ack_msg_id = await _try_ack(bot, event, _ACK_PHOTO)

        asyncio.create_task(
            _bg_process_photo(bot, db, llm, user_id, chat_id, file_id, caption, queue_id, ack_msg_id)
        )

    return handle_photo


async def _bg_process_photo(
    bot: object,
    db: object,
    llm: object,
    user_id: int,
    chat_id: int,
    file_id: str,
    caption: str,
    queue_id: int,
    ack_msg_id: int | None,
) -> None:
    try:
        image_bytes = await bot.download_file(file_id)
        meta: dict = {"file_id": file_id, "size": len(image_bytes)}
        analysis = ""

        # Save locally
        local_path = await _save_media(image_bytes, "jpg")
        if local_path:
            meta["local_path"] = local_path

        if llm.supports("vision"):
            analysis = await llm.analyze_image(image_bytes, prompt=caption)
            meta["vision_analysis"] = analysis

        metadata = json.dumps(meta, ensure_ascii=False)
        content = caption or analysis or "[图片]"
        row_id = await _insert_message(db, user_id, "photo", content, None, metadata)
        await _mark_done(db, queue_id)
    except Exception as exc:
        await _mark_failed(db, queue_id, str(exc))
        logger.warning("Photo processing failed (queued id=%d): %s", queue_id, exc)
        await _try_edit(bot, chat_id, ack_msg_id, "⏳ 图片已收到，处理暂时失败，稍后会自动重试。")
        return

    reply = f"📷 图片已记录 (#{row_id})。"
    if caption:
        reply += f"\n备注: {caption}"
    if analysis:
        reply += f"\n\n🔍 图片理解：\n{analysis}"
    reply += f"\n\n有误？发送 /recorder_del {row_id}"
    logger.debug("[send] photo reply to user=%d len=%d", user_id, len(reply))
    await _try_send_reply(bot, chat_id, ack_msg_id, reply)


# ---------------------------------------------------------------------------
# Voice
# ---------------------------------------------------------------------------

def _make_voice_handler(ctx: object):
    async def handle_voice(event: Event) -> None:
        db = ctx.db
        bot = ctx.bot
        user_id = event.user_id
        chat_id = event.chat_id
        file_id = event.voice_file_id or ""
        today = datetime.now(ctx.tz).strftime("%Y-%m-%d")

        logger.debug("[recv] voice from user=%d", user_id)

        payload = json.dumps({"file_id": file_id, "date": today}, ensure_ascii=False)
        queue_id = await _enqueue(db, user_id, chat_id, "voice", payload)
        logger.debug("[queue] enqueued id=%d type=voice user=%d", queue_id, user_id)

        ack_msg_id = await _try_ack(bot, event, _ACK_VOICE)

        asyncio.create_task(
            _bg_process_voice(bot, db, user_id, chat_id, file_id, queue_id, ack_msg_id)
        )

    return handle_voice


async def _bg_process_voice(
    bot: object,
    db: object,
    user_id: int,
    chat_id: int,
    file_id: str,
    queue_id: int,
    ack_msg_id: int | None,
) -> None:
    try:
        audio_bytes = await bot.download_file(file_id)
        meta: dict = {"file_id": file_id, "size": len(audio_bytes)}

        local_path = await _save_media(audio_bytes, "ogg")
        if local_path:
            meta["local_path"] = local_path

        metadata = json.dumps(meta, ensure_ascii=False)
        row_id = await _insert_message(db, user_id, "voice", "[语音消息]", None, metadata)
        await _mark_done(db, queue_id)
    except Exception as exc:
        await _mark_failed(db, queue_id, str(exc))
        logger.warning("Voice processing failed (queued id=%d): %s", queue_id, exc)
        await _try_edit(bot, chat_id, ack_msg_id, "⏳ 语音已收到，处理暂时失败，稍后会自动重试。")
        return

    reply = f"🎤 语音已记录 (#{row_id})。"
    reply += f"\n\n有误？发送 /recorder_del {row_id}"
    logger.debug("[send] voice reply to user=%d", user_id)
    await _try_send_reply(bot, chat_id, ack_msg_id, reply)


# ---------------------------------------------------------------------------
# Video
# ---------------------------------------------------------------------------

def _make_video_handler(ctx: object):
    async def handle_video(event: Event) -> None:
        db = ctx.db
        bot = ctx.bot
        user_id = event.user_id
        chat_id = event.chat_id
        file_id = event.video_file_id or ""
        caption = event.caption or ""
        today = datetime.now(ctx.tz).strftime("%Y-%m-%d")

        logger.debug("[recv] video from user=%d caption=%r", user_id, caption[:50])

        payload = json.dumps({"file_id": file_id, "caption": caption, "date": today}, ensure_ascii=False)
        queue_id = await _enqueue(db, user_id, chat_id, "video", payload)
        logger.debug("[queue] enqueued id=%d type=video user=%d", queue_id, user_id)

        ack_msg_id = await _try_ack(bot, event, _ACK_VIDEO)

        asyncio.create_task(
            _bg_process_video(bot, db, user_id, chat_id, file_id, caption, queue_id, ack_msg_id)
        )

    return handle_video


async def _bg_process_video(
    bot: object,
    db: object,
    user_id: int,
    chat_id: int,
    file_id: str,
    caption: str,
    queue_id: int,
    ack_msg_id: int | None,
) -> None:
    try:
        video_bytes = await bot.download_file(file_id)
        meta: dict = {"file_id": file_id, "size": len(video_bytes)}

        local_path = await _save_media(video_bytes, "mp4")
        if local_path:
            meta["local_path"] = local_path

        metadata = json.dumps(meta, ensure_ascii=False)
        content = caption or "[视频]"
        row_id = await _insert_message(db, user_id, "video", content, None, metadata)
        await _mark_done(db, queue_id)
    except Exception as exc:
        await _mark_failed(db, queue_id, str(exc))
        logger.warning("Video processing failed (queued id=%d): %s", queue_id, exc)
        await _try_edit(bot, chat_id, ack_msg_id, "⏳ 视频已收到，处理暂时失败，稍后会自动重试。")
        return

    reply = f"🎬 视频已记录 (#{row_id})。"
    if caption:
        reply += f"\n备注: {caption}"
    reply += f"\n\n有误？发送 /recorder_del {row_id}"
    logger.debug("[send] video reply to user=%d", user_id)
    await _try_send_reply(bot, chat_id, ack_msg_id, reply)


# ---------------------------------------------------------------------------
# DB helpers (plugin-local, no dependency on old Database class)
# ---------------------------------------------------------------------------

async def _enqueue(db: object, user_id: int, chat_id: int, msg_type: str, payload: str) -> int:
    cursor = await db.conn.execute(
        "INSERT INTO message_queue (user_id, chat_id, msg_type, payload) VALUES (?, ?, ?, ?)",
        (user_id, chat_id, msg_type, payload),
    )
    await db.conn.commit()
    return cursor.lastrowid


async def _mark_done(db: object, queue_id: int) -> None:
    await db.conn.execute(
        "UPDATE message_queue SET status = 'done' WHERE id = ?", (queue_id,)
    )
    await db.conn.commit()


async def _mark_failed(db: object, queue_id: int, error: str) -> None:
    await db.conn.execute(
        "UPDATE message_queue SET status = 'failed', attempts = attempts + 1, last_error = ? WHERE id = ?",
        (error[:500], queue_id),
    )
    await db.conn.commit()


async def _insert_message(
    db: object,
    user_id: int,
    msg_type: str,
    content: str,
    category: str | None,
    metadata: str,
) -> int | None:
    """Insert a new message. Returns the new row ID or None on exact-content dup (5-min window)."""
    dup = await db.conn.execute(
        "SELECT 1 FROM messages WHERE user_id = ? AND content = ? AND deleted_at IS NULL "
        "AND created_at > datetime('now', '-5 minutes')",
        (user_id, content),
    )
    if await dup.fetchone():
        return None

    cursor = await db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content, category, metadata) VALUES (?, ?, ?, ?, ?)",
        (user_id, msg_type, content, category, metadata),
    )
    await db.conn.commit()
    return cursor.lastrowid


async def _apply_dedup(
    db: object,
    user_id: int,
    dedup: dict,
    new_content: str,
    msg_type: str,
    category: str | None,
    metadata: str,
) -> int | None:
    """Apply the dedup strategy (merge or replace).

    Returns the affected row ID, or None if nothing was changed.
    """
    dup_id = dedup["duplicate_of"]
    action = dedup["action"]
    merged = dedup.get("merged_content", new_content)

    # Verify the duplicate row still exists and belongs to this user
    cursor = await db.conn.execute(
        "SELECT id, user_id FROM messages WHERE id = ? AND deleted_at IS NULL",
        (dup_id,),
    )
    row = await cursor.fetchone()
    if row is None or row["user_id"] != user_id:
        # Fallback: just insert as new
        return await _insert_message(db, user_id, msg_type, new_content, category, metadata)

    if action == "replace":
        await db.conn.execute(
            "UPDATE messages SET content = ?, metadata = ? WHERE id = ?",
            (merged, metadata, dup_id),
        )
        await db.conn.commit()
        return dup_id
    else:  # merge
        await db.conn.execute(
            "UPDATE messages SET content = ?, metadata = ? WHERE id = ?",
            (merged, metadata, dup_id),
        )
        await db.conn.commit()
        return dup_id


# ---------------------------------------------------------------------------
# ACK / reply helpers — best-effort, never crash the handler
# ---------------------------------------------------------------------------

async def _try_ack(bot: object, event: Event, text: str) -> int | None:
    """Send ACK reply. Returns message_id or None if send failed."""
    try:
        ref = await bot.reply(event, text)
        return ref.message_id
    except Exception:
        logger.debug("ACK send failed (network?), will proceed without edit", exc_info=True)
        return None


async def _try_edit(bot: object, chat_id: int, msg_id: int | None, text: str) -> None:
    """Edit a message if msg_id is available. Best-effort."""
    if msg_id is None:
        return
    try:
        await bot.edit_message(chat_id, msg_id, text)
    except Exception:
        pass


async def _try_send_reply(bot: object, chat_id: int, ack_msg_id: int | None, text: str) -> None:
    """Edit the ACK message with final reply, or send a new message if ACK was lost."""
    if ack_msg_id is not None:
        try:
            await bot.edit_message(chat_id, ack_msg_id, text)
            return
        except Exception:
            pass
    try:
        await bot.send_message(chat_id, text)
    except Exception:
        logger.warning("Failed to send reply to chat=%d", chat_id)


# ---------------------------------------------------------------------------
# Local media storage
# ---------------------------------------------------------------------------

_MEDIA_DIR = "data/media"


async def _save_media(data: bytes, ext: str) -> str | None:
    """Save media bytes to data/media/YYYY-MM-DD/. Returns local path or None."""
    import os
    from datetime import datetime
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        dir_path = os.path.join(_MEDIA_DIR, today)
        os.makedirs(dir_path, exist_ok=True)
        ts = datetime.now().strftime("%H%M%S_%f")
        filename = f"{ts}.{ext}"
        path = os.path.join(dir_path, filename)
        with open(path, "wb") as f:
            f.write(data)
        logger.debug("Saved media: %s (%d bytes)", path, len(data))
        return path
    except Exception:
        logger.warning("Failed to save media locally", exc_info=True)
        return None
