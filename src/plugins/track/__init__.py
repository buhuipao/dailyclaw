"""Track plugin — goal tracking with smart check-ins and reminders."""
from __future__ import annotations

import logging

from src.core.bot import IntentDeclaration
from src.core.plugin import BasePlugin

import src.plugins.track.locale  # noqa: F401

logger = logging.getLogger(__name__)


class TrackPlugin(BasePlugin):
    name = "track"
    version = "1.1.0"
    description = "计划与打卡 — 目标跟踪和智能匹配"

    def get_commands(self):
        from .commands import make_commands
        return make_commands(self.ctx)

    def get_intents(self) -> list[IntentDeclaration]:
        from .commands import cmd_goal, cmd_checkin, cmd_drop, cmd_goals

        return [
            IntentDeclaration(
                name="track_checkin",
                description="User reports progress or checks in for an existing plan/goal",
                examples=(
                    "跑了5公里", "今天背了30个单词", "学了1小时雅思",
                    "practiced piano for 30 minutes",
                ),
                handler=cmd_checkin(self.ctx),
                args_description="The check-in content: what was done, duration, notes. Keep the user's original wording.",
            ),
            IntentDeclaration(
                name="track_add",
                description="User wants to create a NEW plan or set a NEW goal",
                examples=(
                    "我想每天跑步", "开始学雅思计划", "每周读一本书",
                    "I want to start a daily reading habit",
                ),
                handler=cmd_goal(self.ctx),
                args_description="The plan description: what to do, how often, when. Keep the user's original wording.",
            ),
            IntentDeclaration(
                name="track_list",
                description="User wants to see their current plans and progress overview",
                examples=(
                    "看看我的计划", "计划进度怎么样", "我有哪些计划",
                    "show my plans",
                ),
                handler=cmd_goals(self.ctx),
                # No args_description → handler receives text=None
            ),
            IntentDeclaration(
                name="track_del",
                description="User explicitly wants to delete, stop, or archive a plan",
                examples=(
                    "删除跑步计划", "不想练雅思了", "取消读书计划",
                    "remove the workout plan",
                ),
                handler=cmd_drop(self.ctx),
                args_description="The TAG of the plan to delete. Must be one of the user's active plan tags from the context.",
            ),
        ]

    async def get_intent_context(self, user_id: int) -> str:
        try:
            cursor = await self.ctx.db.conn.execute(
                "SELECT tag, name FROM plans WHERE user_id = ? AND active = 1",
                (user_id,),
            )
            rows = await cursor.fetchall()
        except Exception:
            logger.warning("Failed to fetch plans for intent context", exc_info=True)
            return ""
        if not rows:
            return "User has no active plans."
        plans = "\n".join(f"  - {r[0]}: {r[1]}" for r in rows)
        return f"Active plans:\n{plans}"

    async def on_startup(self) -> None:
        from .scheduler import setup_plan_reminders
        await setup_plan_reminders(self.ctx)
