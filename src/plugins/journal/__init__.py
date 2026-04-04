"""Journal plugin — 曾国藩式每日四省反思."""
from __future__ import annotations

from src.core.bot import Command, ConversationFlow
from src.core.plugin import BasePlugin

# Module-level context reference — set during on_startup so command handlers can access it.
_plugin_ctx = None  # type: ignore[assignment]


class JournalPlugin(BasePlugin):
    name = "journal"
    version = "1.0.0"
    description = "曾国藩式每日四省反思"

    def get_commands(self) -> list[Command]:
        from .commands import cmd_journal_cancel, cmd_journal_start, cmd_journal_today
        return [
            Command(name="journal_start", description="开始今日反思", handler=cmd_journal_start),
            Command(name="journal_today", description="查看今日记录", handler=cmd_journal_today),
            Command(name="journal_cancel", description="取消进行中的反思", handler=cmd_journal_cancel),
        ]

    def get_conversations(self) -> list[ConversationFlow]:
        from .commands import journal_answer_handler
        return [ConversationFlow(
            name="journal_reflection",
            entry_command="journal_start",
            states={0: journal_answer_handler},
            cancel_command="journal_cancel",
        )]

    async def on_startup(self) -> None:
        global _plugin_ctx
        _plugin_ctx = self.ctx
        from .scheduler import setup_journal_schedules
        await setup_journal_schedules(self.ctx)
