"""DailyClaw entry point — Telegram bot for daily journaling and accountability."""
from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from .bot.commands import (
    JOURNAL_ANSWERING,
    cmd_checkin,
    cmd_help,
    cmd_journal,
    cmd_plans,
    cmd_share,
    cmd_start,
    cmd_summary,
    cmd_today,
    journal_answer,
    journal_cancel,
)
from .bot.handlers import handle_photo, handle_text, handle_voice
from .config import load_config
from .journal.scheduler import schedule_evening_journal, schedule_weekly_summary
from .llm.client import LLMClient
from .planner.scheduler import schedule_plan_reminders
from .storage.db import Database

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _build_auth_filter(config: dict) -> filters.BaseFilter:
    """Build a filter that only allows configured user IDs."""
    allowed_ids = config.get("telegram", {}).get("allowed_user_ids", [])
    if not allowed_ids:
        logger.warning(
            "No allowed_user_ids configured — bot is open to ALL users. "
            "Set telegram.allowed_user_ids in config.yaml to restrict access."
        )
        return filters.ALL
    return filters.User(user_id=allowed_ids)


async def post_init(application) -> None:
    """Initialize shared resources after app starts."""
    db = application.bot_data["db"]
    await db.connect()
    logger.info("Database connected")

    config = application.bot_data["config"]
    tz = application.bot_data["tz"]

    # Schedule evening journal prompt
    journal_time = config.get("journal", {}).get("evening_prompt_time", "21:30")
    h, m = (int(x) for x in journal_time.split(":"))
    schedule_evening_journal(application, h, m, tz)

    # Schedule plan reminders
    plans = config.get("plans", [])
    if plans:
        schedule_plan_reminders(application, plans, tz)

    # Schedule weekly summary
    schedule_weekly_summary(application, tz)


async def post_shutdown(application) -> None:
    """Clean up on shutdown."""
    db: Database = application.bot_data["db"]
    await db.close()
    logger.info("Database closed")


def main() -> None:
    config = load_config()

    # Timezone
    tz_name = config.get("timezone", "Asia/Shanghai")
    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:
        raise RuntimeError(
            f"Timezone '{tz_name}' not found. Install 'tzdata': pip install tzdata"
        ) from exc

    # Database
    db = Database()

    # LLM
    llm_config = config["llm"]
    llm = LLMClient(
        base_url=llm_config.get("base_url", "https://api.openai.com/v1"),
        api_key=llm_config["api_key"],
        model=llm_config.get("model", "gpt-4o-mini"),
    )

    # Auth filter
    auth = _build_auth_filter(config)

    # Build Telegram app
    app = ApplicationBuilder().token(config["telegram"]["token"]).build()

    # Store shared resources
    app.bot_data["config"] = config
    app.bot_data["db"] = db
    app.bot_data["llm"] = llm
    app.bot_data["tz"] = tz

    # Register command handlers (with auth)
    app.add_handler(CommandHandler("start", cmd_start, filters=auth))
    app.add_handler(CommandHandler("help", cmd_help, filters=auth))
    app.add_handler(CommandHandler("today", cmd_today, filters=auth))
    journal_conv = ConversationHandler(
        entry_points=[CommandHandler("journal", cmd_journal, filters=auth)],
        states={
            JOURNAL_ANSWERING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & auth, journal_answer),
            ],
        },
        fallbacks=[CommandHandler("cancel", journal_cancel, filters=auth)],
    )
    app.add_handler(journal_conv)
    app.add_handler(CommandHandler("checkin", cmd_checkin, filters=auth))
    app.add_handler(CommandHandler("plans", cmd_plans, filters=auth))
    app.add_handler(CommandHandler("summary", cmd_summary, filters=auth))
    app.add_handler(CommandHandler("share", cmd_share, filters=auth))

    # Register message handlers (with auth)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & auth, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO & auth, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE & auth, handle_voice))

    # Lifecycle hooks
    app.post_init = post_init
    app.post_shutdown = post_shutdown

    logger.info("DailyClaw starting... timezone=%s", tz_name)
    app.run_polling()


if __name__ == "__main__":
    main()
