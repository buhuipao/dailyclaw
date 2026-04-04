"""Recorder plugin — auto-classify, dedup, URL summary."""
from __future__ import annotations

from src.core.bot import Command, Event, MessageHandler, MessageType
from src.core.plugin import BasePlugin


class RecorderPlugin(BasePlugin):
    name = "recorder"
    version = "1.0.0"
    description = "消息记录 — 自动分类、去重、URL摘要"

    def get_commands(self) -> list[Command]:
        db = self.ctx.db
        tz = self.ctx.tz

        async def _del_handler(event: Event) -> str | None:
            from .commands import recorder_del
            return await recorder_del(db, event)

        async def _today_handler(event: Event) -> str | None:
            from .commands import recorder_today
            return await recorder_today(db, tz, event)

        return [
            Command(name="recorder_today", description="查看今日记录", handler=_today_handler),
            Command(name="recorder_del", description="删除一条记录", handler=_del_handler),
        ]

    def get_handlers(self) -> list[MessageHandler]:
        from .handlers import make_handlers
        return make_handlers(self.ctx)

    async def on_startup(self) -> None:
        from .retry import make_retry_callback
        cb = make_retry_callback(self.ctx)
        await self.ctx.scheduler.run_repeating(
            cb,
            interval=10,
            name="retry_failed_messages",
            first=10,
        )
