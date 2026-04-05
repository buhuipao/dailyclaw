"""Planner plugin command handlers — plan creation, archival, checkin, progress."""
from __future__ import annotations

import logging
from collections.abc import Callable, Awaitable
from datetime import datetime, timedelta

from src.core.bot import Command, Event
from src.core.i18n import t

import src.plugins.planner.locale  # noqa: F401

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
            return t("planner.add_usage", event.lang)

        db = ctx.db
        llm = ctx.llm
        user_id = event.user_id

        parsed = await llm.parse_plan(event.text, lang=event.lang)
        if not parsed.get("tag") or not parsed.get("name"):
            return t("planner.add_parse_fail", event.lang)

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
            return t("planner.add_duplicate", event.lang, tag=tag)

        await db.conn.execute(
            "INSERT INTO plans (user_id, tag, name, schedule, remind_time) VALUES (?, ?, ?, ?, ?)",
            (user_id, tag, name, schedule, remind_time),
        )
        await db.conn.commit()

        # Register reminder for the new plan immediately
        try:
            from .scheduler import register_plan_reminder
            await register_plan_reminder(ctx, tag, name, schedule, remind_time)
        except Exception:
            logger.warning("Failed to register reminder for plan %s", tag, exc_info=True)

        schedule_label = _format_schedule(schedule, event.lang)
        return t("planner.add_success", event.lang, name=name, tag=tag, schedule=schedule_label, remind=remind_time)

    return handler


def _cmd_planner_del(ctx) -> Callable[[Event], Awaitable[str | None]]:
    async def handler(event: Event) -> str | None:
        if not event.text:
            return t("planner.del_usage", event.lang)

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
            return t("planner.del_no_plans", event.lang)

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
            result = await llm.match_checkin(text, plans, lang=event.lang)
            matched_tag = result.get("tag", "")
            matched_name = next((p["name"] for p in plans if p["tag"] == matched_tag), "")

        if not matched_tag or not matched_name:
            plan_list = "\n".join(f"  • {p['name']} [{p['tag']}]" for p in plans)
            return t("planner.del_no_match", event.lang, list=plan_list)

        result = await db.conn.execute(
            "UPDATE plans SET active = 0 WHERE user_id = ? AND tag = ? AND active = 1",
            (user_id, matched_tag),
        )
        await db.conn.commit()

        if result.rowcount and result.rowcount > 0:
            return t("planner.del_success", event.lang, name=matched_name, tag=matched_tag)
        return t("planner.del_not_found", event.lang, tag=matched_tag)

    return handler


def _cmd_planner_checkin(ctx) -> Callable[[Event], Awaitable[str | None]]:
    async def handler(event: Event) -> str | None:
        if not event.text:
            return t("planner.checkin_usage", event.lang)

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
            return t("planner.checkin_no_plans", event.lang)

        plans = [{"tag": r[0], "name": r[1]} for r in rows]

        # LLM semantic match
        result = await llm.match_checkin(event.text, plans, lang=event.lang)
        tag = result.get("tag", "")
        note = result.get("note", event.text)
        duration = int(result.get("duration_minutes", 0))

        matched_plan = next((p for p in plans if p["tag"] == tag), None)
        if not matched_plan:
            plan_names = ", ".join(f"「{p['name']}」" for p in plans)
            return t("planner.checkin_no_match", event.lang, names=plan_names)

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

        reply = t("planner.checkin_success", event.lang, name=matched_plan['name'])
        if note:
            reply += f" - {note}"
        if duration:
            reply += f" ({t('planner.minutes', event.lang, n=duration)})"
        reply += t("planner.checkin_week_count", event.lang, count=unique_days)

        return reply

    return handler


_DAYS_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

_JOINER: dict[str, str] = {"zh": "、", "en": ", ", "ja": "・"}


def _format_schedule(schedule: str, lang: str = "zh") -> str:
    if schedule == "daily":
        return t("shared.daily", lang)
    parts = [d.strip() for d in schedule.split(",") if d.strip() in _DAYS_MAP]
    if parts:
        joiner = _JOINER.get(lang, "、")
        day_names = joiner.join(t(f"shared.day.{d}", lang) for d in parts)
        return t("shared.weekly_prefix", lang) + day_names
    return schedule


def _cmd_planner_list(ctx) -> Callable[[Event], Awaitable[str | None]]:
    async def handler(event: Event) -> str | None:
        db = ctx.db
        tz = ctx.tz
        user_id = event.user_id
        now = datetime.now(tz)
        today = now.strftime("%Y-%m-%d")
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")

        cursor = await db.conn.execute(
            "SELECT tag, name, schedule, remind_time FROM plans WHERE user_id = ? AND active = 1",
            (user_id,),
        )
        rows = await cursor.fetchall()

        if not rows:
            return t("planner.list_empty", event.lang)

        lines = [t("planner.list_header", event.lang)]

        for row in rows:
            tag, name, schedule, remind_time = row[0], row[1], row[2], row[3]

            # Weekly progress
            checkin_cursor = await db.conn.execute(
                "SELECT DISTINCT date FROM plan_checkins WHERE user_id = ? AND tag = ? AND date >= ? AND date <= ?",
                (user_id, tag, week_start, today),
            )
            checkin_rows = await checkin_cursor.fetchall()
            unique_days = len(checkin_rows)

            if schedule == "daily":
                expected = now.weekday() + 1
            else:
                scheduled_days = [_DAYS_MAP[d.strip()] for d in schedule.split(",") if d.strip() in _DAYS_MAP]
                expected = sum(1 for d in scheduled_days if d <= now.weekday())

            bar = "🟩" * unique_days + "⬜" * max(0, expected - unique_days)

            # Recent check-ins (last 3)
            recent_cursor = await db.conn.execute(
                "SELECT date, note, duration_minutes FROM plan_checkins "
                "WHERE user_id = ? AND tag = ? ORDER BY date DESC, rowid DESC LIMIT 3",
                (user_id, tag),
            )
            recent_rows = await recent_cursor.fetchall()

            schedule_label = _format_schedule(schedule, event.lang)
            lines.append(f"📌 {name} [{tag}]")
            lines.append(t("planner.list_frequency", event.lang, schedule=schedule_label, remind=remind_time))
            lines.append(t("planner.list_week_bar", event.lang, bar=bar, done=unique_days, expected=expected))

            if recent_rows:
                lines.append(t("planner.list_recent_header", event.lang))
                for r in recent_rows:
                    date_str, note, duration = r[0], r[1], r[2]
                    entry = f"     {date_str}"
                    if note:
                        entry += f" — {note}"
                    if duration:
                        entry += f" ({t('planner.minutes', event.lang, n=duration)})"
                    lines.append(entry)
            else:
                lines.append(t("planner.list_no_checkins", event.lang))

            lines.append("")  # blank line between plans

        return "\n".join(lines).rstrip()

    return handler
