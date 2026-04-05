"""Sharing plugin command handlers — summary and export."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from src.core.i18n import t
from src.core.i18n.shared import category_label

import src.plugins.sharing.locale  # noqa: F401

if TYPE_CHECKING:
    from src.core.bot import Command, Event
    from src.core.context import AppContext

logger = logging.getLogger(__name__)

MSG_TYPE_ICONS: dict[str, str] = {
    "link": "🔗",
    "photo": "📷",
    "voice": "🎤",
}
DEFAULT_ICON = "💬"


def make_commands(ctx: "AppContext") -> list["Command"]:
    """Return sharing commands with ctx bound via closure."""
    from src.core.bot import Command

    return [
        Command(
            name="sharing_summary",
            description="生成周/月总结 (用法: /sharing_summary [week|month])",
            handler=_make_summary_handler(ctx),
        ),
        Command(
            name="sharing_export",
            description="导出指定日期的内容 (用法: /sharing_export [YYYY-MM-DD])",
            handler=_make_export_handler(ctx),
        ),
    ]


def _make_summary_handler(ctx: "AppContext"):
    """Build the sharing_summary handler with ctx bound."""
    from .summary import generate_summary

    async def cmd_sharing_summary(event: "Event") -> str:
        text = (event.text or "").strip()
        period_type = text if text else "week"

        if period_type not in ("week", "month"):
            return t("sharing.summary_usage", event.lang)

        now = datetime.now(ctx.tz)
        if period_type == "week":
            start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
            end = now.strftime("%Y-%m-%d")
        else:
            start = now.strftime("%Y-%m-01")
            end = now.strftime("%Y-%m-%d")

        result = await generate_summary(
            db=ctx.db,
            llm=ctx.llm,
            user_id=event.user_id,
            period_type=period_type,
            start_date=start,
            end_date=end,
            lang=event.lang,
        )
        return f"📊 {result}"

    return cmd_sharing_summary


def _make_export_handler(ctx: "AppContext"):
    """Build the sharing_export handler with ctx bound."""

    async def cmd_sharing_export(event: "Event") -> str:
        text = (event.text or "").strip()
        date = text if text else datetime.now(ctx.tz).strftime("%Y-%m-%d")
        lang = event.lang

        messages = await _get_messages(ctx.db, event.user_id, date)
        journal = await _get_journal_entries(ctx.db, event.user_id, date)

        if not messages and not journal:
            return t("sharing.export_empty", lang, date=date)

        # Build raw material for LLM
        raw_parts: list[str] = []
        for msg in messages:
            icon = MSG_TYPE_ICONS.get(msg.get("msg_type", ""), DEFAULT_ICON)
            content = (msg.get("content") or "")[:300]
            line = f"{icon} {content}"
            meta_raw = msg.get("metadata") or ""
            if meta_raw:
                try:
                    meta = json.loads(meta_raw)
                    if meta.get("url_summary"):
                        line += f" | {meta['url_summary']}"
                    if meta.get("vision_analysis"):
                        line += f" | {meta['vision_analysis']}"
                except json.JSONDecodeError:
                    pass
            raw_parts.append(line)

        for entry in journal:
            cat_label = category_label(entry.get("category", ""), lang)
            raw_parts.append(f"[{cat_label}] {entry.get('content', '')}")

        raw_text = "\n".join(raw_parts)
        total = len(messages) + len(journal)

        # LLM polish
        polished = await ctx.llm.chat(
            messages=[
                {"role": "system", "content": t("sharing.export_system_prompt", lang)},
                {"role": "user", "content": raw_text},
            ],
            max_tokens=800,
            lang=lang,
        )

        header = t("sharing.export_header", lang, date=date)
        return f"{header}\n{polished}\n\n— DailyClaw 🦉"

    return cmd_sharing_export


async def _get_messages(db: object, user_id: int, date: str) -> list[dict]:
    """Fetch today's recorded messages from the messages table."""
    try:
        cursor = await db.conn.execute(
            "SELECT msg_type, content, metadata FROM messages "
            "WHERE user_id = ? AND date(created_at) = ? AND deleted_at IS NULL "
            "ORDER BY created_at",
            (user_id, date),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        logger.warning("messages table unavailable — skipping", exc_info=True)
        return []


async def _get_journal_entries(db: object, user_id: int, date: str) -> list[dict]:
    """Fetch journal entries for the given date."""
    try:
        cursor = await db.conn.execute(
            "SELECT category, content FROM journal_entries "
            "WHERE user_id = ? AND date = ? ORDER BY category",
            (user_id, date),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        logger.warning("journal_entries table unavailable — skipping", exc_info=True)
        return []
