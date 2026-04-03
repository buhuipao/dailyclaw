"""Telegram bot message handlers."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from ..llm.client import LLMClient
from ..storage.db import Database
from ..storage.models import CATEGORY_LABELS, JournalCategory, MessageType

logger = logging.getLogger(__name__)

# URL pattern for detecting links
URL_PATTERN = re.compile(r"https?://\S+")

# Map LLM categories to journal categories
CATEGORY_MAP = {
    "morning": JournalCategory.MORNING,
    "reading": JournalCategory.READING,
    "social": JournalCategory.SOCIAL,
    "reflection": JournalCategory.REFLECTION,
}


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    if not update.effective_user or not update.message:
        return
    db: Database = context.bot_data["db"]
    llm: LLMClient = context.bot_data["llm"]
    user_id = update.effective_user.id
    text = update.message.text

    # Detect message type
    has_url = bool(URL_PATTERN.search(text))
    msg_type = MessageType.LINK if has_url else MessageType.TEXT

    # Use LLM to classify the message
    classification = await llm.classify(text)
    category = CATEGORY_MAP.get(classification.get("category"))

    # Save the raw message
    metadata = json.dumps(classification, ensure_ascii=False)
    await db.save_message(user_id, msg_type, text, category, metadata)

    # Build response
    cat_label = CATEGORY_LABELS.get(category, "记录") if category else "记录"
    summary = classification.get("summary", "")
    reply = f"已记录到今日「{cat_label}」。"
    if summary and summary != text[:50]:
        reply += f"\n📝 {summary}"
    reply += "\n\n有更多想补充的吗？"

    await update.message.reply_text(reply)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming photo messages."""
    if not update.effective_user or not update.message:
        return
    db: Database = context.bot_data["db"]
    user_id = update.effective_user.id
    caption = update.message.caption or ""
    photo = update.message.photo[-1]  # highest resolution

    metadata = json.dumps({"file_id": photo.file_id}, ensure_ascii=False)
    await db.save_message(user_id, MessageType.PHOTO, caption, metadata=metadata)

    await update.message.reply_text("📷 图片已记录。" + (f"\n备注: {caption}" if caption else ""))


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming voice messages."""
    if not update.effective_user or not update.message:
        return
    db: Database = context.bot_data["db"]
    user_id = update.effective_user.id
    voice = update.message.voice

    metadata = json.dumps(
        {"file_id": voice.file_id, "duration": voice.duration},
        ensure_ascii=False,
    )
    await db.save_message(
        user_id, MessageType.VOICE, f"[语音消息 {voice.duration}秒]", metadata=metadata
    )

    await update.message.reply_text(f"🎤 语音已记录 ({voice.duration}秒)。后续版本会支持语音转文字。")
