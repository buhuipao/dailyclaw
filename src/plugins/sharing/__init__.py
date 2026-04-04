from src.core.bot import Command, Event
from src.core.plugin import BasePlugin


class SharingPlugin(BasePlugin):
    name = "sharing"
    version = "1.0.0"
    description = "分享与总结 — 周/月总结和内容导出"

    def get_commands(self) -> list[Command]:
        from .commands import make_commands
        return make_commands(self.ctx)
