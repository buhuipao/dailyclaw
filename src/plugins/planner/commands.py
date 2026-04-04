"""Planner plugin command handlers — plan creation, archival, checkin, progress."""
from __future__ import annotations

import logging
from collections.abc import Callable, Awaitable
from datetime import datetime, timedelta

from src.core.bot import Command, Event

logger = logging.getLogger(__name__)


def make_commands(ctx) -> list[Command]:
    """Return Command list with handlers bound to ctx via closures."""
    return [
        Command(name="planner_add", description="创建新计划", handler=_cmd_planner_add(ctx)),
        Command(name="planner_del", description="归档计划", handler=_cmd_planner_del(ctx)),
        Command(name="planner_checkin", description="智能打卡", handler=_cmd_planner_checkin(ctx)),
        Command(name="planner_list", description="查看计划进度", handler=_cmd_planner_list(ctx)),
    ]


def _cmd_planner_add(ctx) -> Callable[[Event], Awaitable[str | None]]:
    async def handler(event: Event) -> str | None:
        if not event.text:
            return (
                "用法: /planner_add <描述>\n"
                "例如: /planner_add 每天学雅思，晚上8点提醒\n"
                "例如: /planner_add 每周一三五锻炼，7点提醒"
            )

        db = ctx.db
        llm = ctx.llm
        user_id = event.user_id

        parsed = await llm.parse_plan(event.text)
        if not parsed.get("tag") or not parsed.get("name"):
            return "没有理解你的计划，请再描述一下？"

        tag = parsed["tag"]
        name = parsed["name"]
        schedule = parsed.get("schedule", "daily")
        remind_time = parsed.get("remind_time", "20:00")

        # Check for duplicate active tag
        cursor = await db.conn.execute(
            "SELECT 1 FROM plans WHERE user_id = ? AND tag = ? AND active = 1 LIMIT 1",
            (user_id, tag),
        )
        if await cursor.fetchone() is not None:
            return f"已存在同名计划 [{tag}]，请换个描述或先 /planner_del 旧的。"

        await db.conn.execute(
            "INSERT INTO plans (user_id, tag, name, schedule, remind_time) VALUES (?, ?, ?, ?, ?)",
            (user_id, tag, name, schedule, remind_time),
        )
        await db.conn.commit()

        schedule_label = "每天" if schedule == "daily" else f"每周 {schedule}"
        return (
            f"已创建计划「{name}」\n"
            f"标签: {tag}\n"
            f"频率: {schedule_label}\n"
            f"提醒: {remind_time}\n\n"
            f"用自然语言打卡: /planner_checkin 今天练了30分钟听力"
        )

    return handler


def _cmd_planner_del(ctx) -> Callable[[Event], Awaitable[str | None]]:
    async def handler(event: Event) -> str | None:
        if not event.text:
            return "用法: /planner_del <计划名称或标签>"

        db = ctx.db
        llm = ctx.llm
        user_id = event.user_id
        text = event.text.strip()

        cursor = await db.conn.execute(
            "SELECT tag, name FROM plans WHERE user_id = ? AND active = 1",
            (user_id,),
        )
        rows = await cursor.fetchall()

        if not rows:
            return "你还没有任何计划。"

        plans = [{"tag": r[0], "name": r[1]} for r in rows]

        # Try exact match first
        matched_tag = ""
        matched_name = ""
        for p in plans:
            if p["tag"] == text or p["name"] == text:
                matched_tag = p["tag"]
                matched_name = p["name"]
                break

        if not matched_tag:
            # LLM semantic match
            result = await llm.match_checkin(text, plans)
            matched_tag = result.get("tag", "")
            matched_name = next((p["name"] for p in plans if p["tag"] == matched_tag), "")

        if not matched_tag or not matched_name:
            plan_list = "\n".join(f"  • {p['name']} [{p['tag']}]" for p in plans)
            return f"没有匹配到计划。你的计划：\n{plan_list}"

        result = await db.conn.execute(
            "UPDATE plans SET active = 0 WHERE user_id = ? AND tag = ? AND active = 1",
            (user_id, matched_tag),
        )
        await db.conn.commit()

        if result.rowcount and result.rowcount > 0:
            return f"已归档计划「{matched_name}」[{matched_tag}]"
        return f"未找到活跃的计划 [{matched_tag}]"

    return handler


def _cmd_planner_checkin(ctx) -> Callable[[Event], Awaitable[str | None]]:
    async def handler(event: Event) -> str | None:
        if not event.text:
            return (
                "用法: /planner_checkin <描述>\n"
                "例如: /planner_checkin 今天练了半小时雅思听力\n"
                "例如: /planner_checkin 跑了5公里"
            )

        db = ctx.db
        llm = ctx.llm
        tz = ctx.tz
        user_id = event.user_id
        today = datetime.now(tz).strftime("%Y-%m-%d")

        cursor = await db.conn.execute(
            "SELECT tag, name FROM plans WHERE user_id = ? AND active = 1",
            (user_id,),
        )
        rows = await cursor.fetchall()

        if not rows:
            return "你还没有计划。用 /planner_add 创建一个吧！"

        plans = [{"tag": r[0], "name": r[1]} for r in rows]

        # LLM semantic match
        result = await llm.match_checkin(event.text, plans)
        tag = result.get("tag", "")
        note = result.get("note", event.text)
        duration = int(result.get("duration_minutes", 0))

        matched_plan = next((p for p in plans if p["tag"] == tag), None)
        if not matched_plan:
            plan_names = ", ".join(f"「{p['name']}」" for p in plans)
            return f"没有匹配到计划。你的计划有：{plan_names}\n请再描述一下？"

        await db.conn.execute(
            "INSERT INTO plan_checkins (user_id, tag, date, note, duration_minutes) VALUES (?, ?, ?, ?, ?)",
            (user_id, tag, today, note, duration),
        )
        await db.conn.commit()

        # Get this week's unique check-in days
        now = datetime.now(tz)
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        cursor = await db.conn.execute(
            "SELECT DISTINCT date FROM plan_checkins WHERE user_id = ? AND tag = ? AND date >= ? AND date <= ?",
            (user_id, tag, week_start, today),
        )
        week_rows = await cursor.fetchall()
        unique_days = len(week_rows)

        reply = f"已打卡：{matched_plan['name']}"
        if note:
            reply += f" - {note}"
        if duration:
            reply += f" ({duration}分钟)"
        reply += f"\n本周已打卡 {unique_days} 天"

        return reply

    return handler


def _cmd_planner_list(ctx) -> Callable[[Event], Awaitable[str | None]]:
    async def handler(event: Event) -> str | None:
        db = ctx.db
        tz = ctx.tz
        user_id = event.user_id
        now = datetime.now(tz)
        today = now.strftime("%Y-%m-%d")
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")

        cursor = await db.conn.execute(
            "SELECT tag, name, schedule FROM plans WHERE user_id = ? AND active = 1",
            (user_id,),
        )
        rows = await cursor.fetchall()

        if not rows:
            return "还没有计划。用 /planner_add 创建一个吧！"

        days_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
        lines = ["计划进度\n"]

        for row in rows:
            tag, name, schedule = row[0], row[1], row[2]

            checkin_cursor = await db.conn.execute(
                "SELECT DISTINCT date FROM plan_checkins WHERE user_id = ? AND tag = ? AND date >= ? AND date <= ?",
                (user_id, tag, week_start, today),
            )
            checkin_rows = await checkin_cursor.fetchall()
            unique_days = len(checkin_rows)

            if schedule == "daily":
                expected = now.weekday() + 1
            else:
                scheduled_days = [days_map[d.strip()] for d in schedule.split(",") if d.strip() in days_map]
                expected = sum(1 for d in scheduled_days if d <= now.weekday())

            bar = "🟩" * unique_days + "⬜" * max(0, expected - unique_days)
            lines.append(f"📌 {name}\n   {bar} {unique_days}/{expected}")

        return "\n".join(lines)

    return handler
