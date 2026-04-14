"""Recorder plugin message handlers for text/photo/voice/video.

All handlers return a str reply. The framework (TelegramAdapter) handles:
  1. Enqueue to message_queue
  2. Send ACK
  3. Call handler in background
  4. Edit ACK with the returned string
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime

from src.core.bot import Event, MessageHandler, MessageType
from src.core.i18n import t
from src.core.i18n.shared import category_label

import src.plugins.memo.locale  # noqa: F401

from .dedup import check_dedup
from .url_fetcher import extract_readable_text, fetch_url

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"https?://\S+")

_MEDIA_DIR = "data/media"


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
    async def handle_text(event: Event) -> str | None:
        db = ctx.db
        llm = ctx.llm
        text = event.text or ""
        user_id = event.user_id

        logger.debug("[process] classifying text for user=%d", user_id)
        classification = await llm.classify(text, lang=event.lang)
        category = classification.get("category")
        logger.debug("[process] classified as category=%s", category)

        # URL fetch + summarize
        urls = URL_PATTERN.findall(text)
        url_summary = ""
        if urls:
            first_url = urls[0]
            logger.debug("[process] fetching URL: %s", first_url)
            html = await fetch_url(first_url)
            if html:
                readable = extract_readable_text(html, url=first_url)
                if readable:
                    url_summary = await llm.summarize_text(text=readable, url=first_url, lang=event.lang)

        meta = dict(classification)
        if url_summary:
            meta["url_summary"] = url_summary
        metadata = json.dumps(meta, ensure_ascii=False)
        msg_type = "link" if urls else "text"

        # Semantic dedup check
        dedup = await check_dedup(db, llm, user_id, text)
        if dedup is not None:
            row_id = await _apply_dedup(db, user_id, dedup, text, msg_type, category, metadata)
            if row_id is None:
                return t("memo.dedup_skip", event.lang)
            cat_label = category_label(category, event.lang)
            summary = classification.get("summary", "")
            reply = t("memo.text_updated", event.lang, cat=cat_label, id=row_id)
            if summary and summary != text[:50]:
                reply += f"\n📝 {summary}"
            reply += t("memo.delete_hint", event.lang, id=row_id)
        else:
            row_id = await _insert_message(db, user_id, msg_type, text, category, metadata)
            if row_id is None:
                return t("memo.dedup_skip", event.lang)

            cat_label = category_label(category, event.lang)
            summary = classification.get("summary", "")
            reply = t("memo.text_recorded", event.lang, cat=cat_label, id=row_id)
            if summary and summary != text[:50]:
                reply += f"\n📝 {summary}"
            if url_summary:
                reply += t("memo.url_summary_label", event.lang, summary=url_summary)
            else:
                reply += t("memo.text_more_prompt", event.lang)
            reply += t("memo.delete_hint", event.lang, id=row_id)

        # Wiki nudge check (runs only if wiki plugin loaded)
        if ctx.wiki_nudge and row_id is not None:
            try:
                nudge_text = await ctx.wiki_nudge(user_id, text, event.lang)
                if nudge_text:
                    reply += f"\n\n{nudge_text}"
            except Exception:
                logger.debug("[nudge] check failed", exc_info=True)

        return reply

    return handle_text


# ---------------------------------------------------------------------------
# Photo
# ---------------------------------------------------------------------------

def _make_photo_handler(ctx: object):
    async def handle_photo(event: Event) -> str | None:
        db = ctx.db
        bot = ctx.bot
        llm = ctx.llm
        user_id = event.user_id
        file_id = event.photo_file_id or ""
        caption = event.caption or ""

        image_bytes = await bot.download_file(file_id)

        # Dedup by image content hash — same image within 30 minutes
        img_hash = hashlib.sha256(image_bytes).hexdigest()[:16]
        dup = await db.conn.execute(
            "SELECT id FROM messages WHERE user_id = ? AND msg_type = 'photo' "
            "AND metadata LIKE ? AND deleted_at IS NULL "
            "AND created_at > datetime('now', '-30 minutes')",
            (user_id, f'%"hash": "{img_hash}"%'),
        )
        if await dup.fetchone():
            return t("memo.dedup_skip", event.lang)
        meta: dict = {"file_id": file_id, "size": len(image_bytes), "hash": img_hash}
        analysis = ""

        local_path = _save_media(image_bytes, "jpg")
        if local_path:
            meta["local_path"] = local_path

        if llm.supports("vision"):
            analysis = await llm.analyze_image(image_bytes, prompt=caption, lang=event.lang)
            meta["vision_analysis"] = analysis

        metadata = json.dumps(meta, ensure_ascii=False)
        content = caption or analysis or t("memo.media_placeholder.photo", event.lang)
        row_id = await _insert_message(db, user_id, "photo", content, None, metadata)
        if row_id is None:
            return t("memo.dedup_skip", event.lang)

        reply = t("memo.photo_recorded", event.lang, id=row_id)
        if caption:
            reply += t("memo.photo_note", event.lang, caption=caption)
        if analysis:
            reply += t("memo.photo_analysis", event.lang, analysis=analysis)
        reply += t("memo.delete_hint", event.lang, id=row_id)
        return reply

    return handle_photo


# ---------------------------------------------------------------------------
# Voice
# ---------------------------------------------------------------------------

def _make_voice_handler(ctx: object):
    async def handle_voice(event: Event) -> str | None:
        db = ctx.db
        bot = ctx.bot
        user_id = event.user_id
        file_id = event.voice_file_id or ""

        audio_bytes = await bot.download_file(file_id)
        meta: dict = {"file_id": file_id, "size": len(audio_bytes)}

        local_path = _save_media(audio_bytes, "ogg")
        if local_path:
            meta["local_path"] = local_path

        metadata = json.dumps(meta, ensure_ascii=False)
        row_id = await _insert_message(
            db, user_id, "voice", t("memo.media_placeholder.voice", event.lang), None, metadata,
        )

        reply = t("memo.voice_recorded", event.lang, id=row_id)
        reply += t("memo.delete_hint", event.lang, id=row_id)
        return reply

    return handle_voice


# ---------------------------------------------------------------------------
# Video
# ---------------------------------------------------------------------------

def _make_video_handler(ctx: object):
    async def handle_video(event: Event) -> str | None:
        db = ctx.db
        bot = ctx.bot
        user_id = event.user_id
        file_id = event.video_file_id or ""
        caption = event.caption or ""

        video_bytes = await bot.download_file(file_id)
        meta: dict = {"file_id": file_id, "size": len(video_bytes)}

        local_path = _save_media(video_bytes, "mp4")
        if local_path:
            meta["local_path"] = local_path

        metadata = json.dumps(meta, ensure_ascii=False)
        content = caption or t("memo.media_placeholder.video", event.lang)
        row_id = await _insert_message(db, user_id, "video", content, None, metadata)

        reply = t("memo.video_recorded", event.lang, id=row_id)
        if caption:
            reply += t("memo.video_note", event.lang, caption=caption)
        reply += t("memo.delete_hint", event.lang, id=row_id)
        return reply

    return handle_video


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def _insert_message(
    db: object, user_id: int, msg_type: str, content: str,
    category: str | None, metadata: str,
) -> int | None:
    """Insert a new message. Returns row ID or None on exact-content dup (5-min window)."""
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
    db: object, user_id: int, dedup: dict, new_content: str,
    msg_type: str, category: str | None, metadata: str,
) -> int | None:
    """Apply dedup merge/replace. Returns affected row ID or None."""
    dup_id = dedup["duplicate_of"]
    merged = dedup.get("merged_content", new_content)

    cursor = await db.conn.execute(
        "SELECT id, user_id FROM messages WHERE id = ? AND deleted_at IS NULL",
        (dup_id,),
    )
    row = await cursor.fetchone()
    if row is None or row["user_id"] != user_id:
        return await _insert_message(db, user_id, msg_type, new_content, category, metadata)

    await db.conn.execute(
        "UPDATE messages SET content = ?, metadata = ? WHERE id = ?",
        (merged, metadata, dup_id),
    )
    await db.conn.commit()
    return dup_id


# ---------------------------------------------------------------------------
# Local media storage
# ---------------------------------------------------------------------------

def _save_media(data: bytes, ext: str) -> str | None:
    """Save media bytes to data/media/YYYY-MM-DD/. Returns local path or None."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        dir_path = os.path.join(_MEDIA_DIR, today)
        os.makedirs(dir_path, exist_ok=True)
        ts = datetime.now().strftime("%H%M%S_%f")
        path = os.path.join(dir_path, f"{ts}.{ext}")
        with open(path, "wb") as f:
            f.write(data)
        logger.debug("Saved media: %s (%d bytes)", path, len(data))
        return path
    except Exception:
        logger.warning("Failed to save media locally", exc_info=True)
        return None
