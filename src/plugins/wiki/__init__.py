"""Wiki plugin — personal LLM-maintained knowledge wiki."""
from __future__ import annotations

from src.core.bot import Command, IntentDeclaration
from src.core.plugin import BasePlugin

import src.plugins.wiki.locale  # noqa: F401


class WikiPlugin(BasePlugin):
    name = "wiki"
    version = "1.0.0"
    description = "个人知识维基 — 自动整理、查询、洞察"

    def get_commands(self) -> list[Command]:
        from .commands import cmd_ask, cmd_digest, cmd_topic, cmd_topics

        return [
            Command(name="ask", description="向知识库提问", handler=cmd_ask(self.ctx)),
            Command(name="topics", description="查看所有主题", handler=cmd_topics(self.ctx)),
            Command(name="topic", description="查看具体主题内容", handler=cmd_topic(self.ctx)),
            Command(name="digest", description="生成本周知识摘要", handler=cmd_digest(self.ctx)),
        ]

    def get_intents(self) -> list[IntentDeclaration]:
        from .commands import cmd_ask

        return [
            IntentDeclaration(
                name="wiki_ask",
                description="User is asking a question about their life, habits, patterns, or past thoughts",
                examples=(
                    "我最近在读什么书？",
                    "我的作息规律是什么？",
                    "上个月我都在忙什么？",
                    "What have I been working on lately?",
                    "What are my reading habits?",
                ),
                handler=cmd_ask(self.ctx),
                args_description="The user's question, as-is",
            ),
        ]

    async def on_startup(self) -> None:
        from .scheduler import setup_wiki_schedules
        await setup_wiki_schedules(self.ctx)
