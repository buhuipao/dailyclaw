"""Reflect plugin — 曾国藩式每日四省反思."""
from __future__ import annotations

from src.core.bot import Command, ConversationFlow
from src.core.plugin import BasePlugin

import src.plugins.reflect.locale  # noqa: F401

# Module-level context reference — set during on_startup so command handlers can access it.
_plugin_ctx = None  # type: ignore[assignment]


class ReflectPlugin(BasePlugin):
    name = "reflect"
    version = "1.1.0"
    description = "曾国藩式每日四省反思"

    def get_commands(self) -> list[Command]:
        from .commands import (
            cmd_cancel,
            cmd_review,
            cmd_reflect,
        )
        return [
            Command(name="reflect", description="开始今日反思", handler=cmd_reflect),
            Command(name="review", description="回顾日记", handler=cmd_review),
            Command(name="cancel", description="取消进行中的反思", handler=cmd_cancel),
        ]

    def get_conversations(self) -> list[ConversationFlow]:
        from .commands import cmd_reflect, reflect_answer_handler
        return [ConversationFlow(
            name="reflect_session",
            entry_command="reflect",
            entry_handler=cmd_reflect,
            states={0: reflect_answer_handler},
            cancel_command="cancel",
        )]

    async def on_startup(self) -> None:
        global _plugin_ctx
        _plugin_ctx = self.ctx
        from .scheduler import setup_reflect_schedules
        await setup_reflect_schedules(self.ctx)
