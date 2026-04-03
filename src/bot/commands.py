"""Telegram bot command handlers."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes

from ..llm.client import LLMClient
from ..storage.db import Database
from ..storage.models import CATEGORY_LABELS, JournalCategory

logger = logging.getLogger(__name__)

MAX_JOURNAL_CONTEXT_MESSAGES = 20


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not update.message:
        return
    await update.message.reply_text(
        "🦉 欢迎使用 DailyClaw！\n\n"
        "我是你的个人日记助手。你可以随时发消息给我，我会帮你：\n"
        "• 记录每日所思所想所阅所见\n"
        "• 每晚引导你做曾国藩式反思\n"
        "• 追踪你的学习和锻炼计划\n\n"
        "命令列表：\n"
        "/today - 查看今日记录\n"
        "/journal - 开始今日反思\n"
        "/checkin <标签> <备注> - 计划打卡\n"
        "/plans - 查看计划进度\n"
        "/help - 帮助信息"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not update.message:
        return
    await update.message.reply_text(
        "📖 使用指南：\n\n"
        "💬 直接发消息 → 自动分类记录\n"
        "📷 发图片 → 记录图片和备注\n"
        "🎤 发语音 → 记录语音消息\n\n"
        "📝 /today → 今日所有记录\n"
        "🌙 /journal → 开始曾国藩式反思\n"
        "✅ /checkin ielts 听力30分钟 → 打卡\n"
        "📊 /plans → 查看计划完成情况\n"
    )


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show today's records."""
    if not update.effective_user or not update.message:
        return
    db: Database = context.bot_data["db"]
    tz = context.bot_data["tz"]
    user_id = update.effective_user.id
    today = datetime.now(tz).strftime("%Y-%m-%d")

    messages = await db.get_today_messages(user_id, today)
    journal = await db.get_journal_entries(user_id, today)

    if not messages and not journal:
        await update.message.reply_text("📭 今天还没有记录。随时发消息给我吧！")
        return

    lines = [f"📅 {today} 今日记录\n"]

    if messages:
        lines.append(f"💬 消息 ({len(messages)} 条)：")
        for msg in messages[-10:]:  # show last 10
            preview = msg.content[:60] + ("..." if len(msg.content) > 60 else "")
            lines.append(f"  • {preview}")

    if journal:
        lines.append("\n📝 日记：")
        for entry in journal:
            cat_label = CATEGORY_LABELS.get(entry.category, entry.category.value)
            preview = entry.content[:80] + ("..." if len(entry.content) > 80 else "")
            lines.append(f"  [{cat_label}] {preview}")

    await update.message.reply_text("\n".join(lines))


async def cmd_journal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the evening reflection journal."""
    if not update.effective_user or not update.message:
        return
    db: Database = context.bot_data["db"]
    llm: LLMClient = context.bot_data["llm"]
    tz = context.bot_data["tz"]
    user_id = update.effective_user.id
    today = datetime.now(tz).strftime("%Y-%m-%d")

    messages = await db.get_today_messages(user_id, today)
    existing_journal = await db.get_journal_entries(user_id, today)

    # Build context from today's messages (capped to prevent prompt inflation)
    recent = messages[-MAX_JOURNAL_CONTEXT_MESSAGES:]
    msg_context = ""
    if recent:
        msg_context = "\n".join(f"- {m.content[:100]}" for m in recent)

    existing_context = ""
    if existing_journal:
        existing_context = "\n".join(
            f"- [{CATEGORY_LABELS.get(e.category, '')}] {e.content[:100]}"
            for e in existing_journal
        )

    # System prompt is static; user content goes in user role to prevent injection
    system_prompt = (
        "你是 DailyClaw，用户的每日反思助手。\n"
        "请用温暖、简洁的方式引导用户完成曾国藩式每日四省：\n"
        "1. 晨起：今天几点起？精神状态如何？\n"
        "2. 所阅：今天读了/看了/听了什么？有什么收获？\n"
        "3. 待人接物：今天和谁有印象深刻的交流？\n"
        "4. 反省：今天有什么做得不够好的？明天如何改进？\n\n"
        "如果用户今天已经有记录，结合这些记录来引导，不要重复问已有的内容。\n"
        "用中文回复，语气温暖但不啰嗦。"
    )

    user_content = f"今天是 {today}，开始今天的反思。"
    if msg_context:
        user_content += f"\n\n今天的记录：\n{msg_context}"
    if existing_context:
        user_content += f"\n\n已有的日记条目：\n{existing_context}"

    response = await llm.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
    )

    context.user_data["journal_mode"] = True
    context.user_data["journal_date"] = today

    await update.message.reply_text(f"🌙 {response}")


async def cmd_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plan check-in. Usage: /checkin <tag> [note]"""
    if not update.effective_user or not update.message:
        return
    db: Database = context.bot_data["db"]
    tz = context.bot_data["tz"]
    config = context.bot_data["config"]
    user_id = update.effective_user.id
    today = datetime.now(tz).strftime("%Y-%m-%d")

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "用法: /checkin <标签> [备注]\n"
            "例如: /checkin ielts 听力练习30分钟\n"
            "例如: /checkin workout 跑步5公里"
        )
        return

    tag = args[0]

    # Validate tag against configured plans
    valid_tags = {p["tag"] for p in config.get("plans", [])}
    if valid_tags and tag not in valid_tags:
        await update.message.reply_text(
            f"未知标签: {tag}\n可用标签: {', '.join(sorted(valid_tags))}"
        )
        return

    note = " ".join(args[1:]) if len(args) > 1 else ""

    # Parse duration if mentioned (simple pattern: NNN分钟)
    duration = 0
    duration_match = re.search(r"(\d+)\s*分钟", note)
    if duration_match:
        duration = int(duration_match.group(1))

    await db.save_checkin(user_id, tag, today, note, duration)

    # Get this week's stats for the tag
    week_start = datetime.now(tz) - timedelta(days=datetime.now(tz).weekday())
    checkins = await db.get_checkins_range(
        user_id, tag, week_start.strftime("%Y-%m-%d"), today
    )
    unique_days = len(set(c.date for c in checkins))

    reply = f"✅ 已打卡：{tag}"
    if note:
        reply += f" - {note}"
    reply += f"\n📊 本周已打卡 {unique_days} 天"

    await update.message.reply_text(reply)


async def cmd_plans(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show plan progress overview."""
    if not update.effective_user or not update.message:
        return
    db: Database = context.bot_data["db"]
    tz = context.bot_data["tz"]
    config = context.bot_data["config"]
    user_id = update.effective_user.id
    today = datetime.now(tz).strftime("%Y-%m-%d")

    plans = config.get("plans", [])
    if not plans:
        await update.message.reply_text("📋 还没有配置任何计划。请在 config.yaml 中添加。")
        return

    now = datetime.now(tz)
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")

    lines = ["📊 计划进度\n"]
    for plan in plans:
        tag = plan["tag"]
        name = plan["name"]
        checkins = await db.get_checkins_range(user_id, tag, week_start, today)
        unique_days = len(set(c.date for c in checkins))

        # Determine expected days this week
        schedule = plan.get("schedule", "daily")
        if schedule == "daily":
            expected = now.weekday() + 1
        else:
            days_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
            scheduled_days = [days_map[d.strip()] for d in schedule.split(",") if d.strip() in days_map]
            expected = sum(1 for d in scheduled_days if d <= now.weekday())

        bar = "■" * unique_days + "□" * max(0, expected - unique_days)
        lines.append(f"{name} [{tag}]: {bar} {unique_days}/{expected}")

    await update.message.reply_text("\n".join(lines))
