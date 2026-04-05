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

        messages = await _get_messages(ctx.db, event.user_id, date)
        journal = await _get_journal_entries(ctx.db, event.user_id, date)

        if not messages and not journal:
            return t("sharing.export_empty", event.lang, date=date)

        lines: list[str] = [t("sharing.export_header", event.lang, date=date)]

        if messages:
            lines.append(t("sharing.export_records_section", event.lang))
            for msg in messages:
                icon = MSG_TYPE_ICONS.get(msg.get("msg_type", ""), DEFAULT_ICON)
                content = (msg.get("content") or "")[:200]
                lines.append(f"{icon} {content}")
                meta_raw = msg.get("metadata") or ""
                if meta_raw:
                    try:
                        meta = json.loads(meta_raw)
                        if meta.get("url_summary"):
                            lines.append(t("sharing.export_summary_label", event.lang, text=meta['url_summary']))
                        if meta.get("vision_analysis"):
                            lines.append(t("sharing.export_vision_label", event.lang, text=meta['vision_analysis']))
                    except json.JSONDecodeError:
                        pass
            lines.append("")

        if journal:
            lines.append(t("sharing.export_journal_section", event.lang))
            for entry in journal:
                cat = entry.get("category", "")
                cat_label = category_label(cat, event.lang)
                lines.append(f"【{cat_label}】{entry.get('content', '')}")
            lines.append("")

        lines.append("— DailyClaw 🦉")
        return "\n".join(lines)

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
