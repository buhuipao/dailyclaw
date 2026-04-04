"""Journal plugin command handlers."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.bot import Event
    from src.core.context import AppContext

logger = logging.getLogger(__name__)

# Module-level session registry: user_id -> JournalEngine
_sessions: dict[int, object] = {}


def _get_ctx() -> "AppContext":
    from src.plugins.journal import _plugin_ctx
    return _plugin_ctx


def _get_today(ctx: "AppContext") -> str:
    return datetime.now(ctx.tz).strftime("%Y-%m-%d")


async def cmd_journal_start(event: "Event") -> str:
    from .db import JournalDB
    from .engine import JournalEngine

    ctx = _get_ctx()
    user_id = event.user_id

    if user_id in _sessions:
        return "你已经有一个正在进行的反思。请继续回答，或发送 /journal_cancel 取消。"

    journal_db = JournalDB(ctx.db)
    engine = JournalEngine(
        db=journal_db,
        llm=ctx.llm,
        user_id=user_id,
        date=_get_today(ctx),
    )
    _sessions[user_id] = engine
    return await engine.start()


async def cmd_journal_today(event: "Event") -> str:
    from .db import JournalDB

    ctx = _get_ctx()
    journal_db = JournalDB(ctx.db)
    entries = await journal_db.get_journal_entries(event.user_id, _get_today(ctx))

    if not entries:
        return "今天还没有反思记录。发送 /journal_start 开始吧！"

    category_labels = {
        "morning": "晨起",
        "reading": "所阅",
        "social": "待人接物",
        "reflection": "反省",
    }
    lines = [f"📝 今日反思 ({_get_today(ctx)}):\n"]
    for entry in entries:
        label = category_labels.get(entry["category"], entry["category"])
        lines.append(f"【{label}】{entry['content']}")
    return "\n".join(lines)


async def cmd_journal_cancel(event: "Event") -> str:
    user_id = event.user_id
    if user_id in _sessions:
        del _sessions[user_id]
        return "已取消当前反思。随时可以用 /journal_start 重新开始。"
    return "没有进行中的反思。"


async def journal_answer_handler(event: "Event") -> str | None:
    user_id = event.user_id
    engine = _sessions.get(user_id)
    if engine is None:
        return None  # Not in a journal session — pass through

    text = event.text or ""
    response = await engine.answer(text)  # type: ignore[union-attr]

    if engine.is_complete:  # type: ignore[union-attr]
        del _sessions[user_id]

    return response
