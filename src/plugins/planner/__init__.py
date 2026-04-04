"""Planner plugin — goal tracking with smart check-ins and reminders."""
from __future__ import annotations

from src.core.plugin import BasePlugin


class PlannerPlugin(BasePlugin):
    name = "planner"
    version = "1.0.0"
    description = "计划与打卡 — 目标跟踪和智能匹配"

    def get_commands(self):
        from .commands import make_commands
        return make_commands(self.ctx)

    async def on_startup(self) -> None:
        from .scheduler import setup_plan_reminders
        await setup_plan_reminders(self.ctx)
