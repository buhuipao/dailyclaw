"""DailyClaw entry point — plugin-based Telegram bot for daily journaling."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from .adapters.telegram import TelegramAdapter
from .config import load_config
from .core.bot import Command, Event
from .core.db import Database, MigrationRunner
from .core.llm import Capability, LLMProvider, LLMService
from .core.plugin import PluginRegistry

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Directory where plugins live (relative to this file's package)
_PLUGINS_DIR = str(Path(__file__).parent / "plugins")

# Directory for core framework migrations
_CORE_MIGRATIONS_DIR = str(Path(__file__).parent / "core" / "migrations")

# Map config section keys to Capability enum values
_CAPABILITY_MAP: dict[str, Capability] = {
    "text": Capability.TEXT,
    "vision": Capability.VISION,
    "audio": Capability.AUDIO,
    "video": Capability.VIDEO,
}


def _build_llm_service(llm_config: dict) -> LLMService:
    """Iterate over text/vision/audio/video sub-sections and build LLMService."""
    providers: dict[Capability, LLMProvider] = {}
    for section_key, capability in _CAPABILITY_MAP.items():
        section = llm_config.get(section_key)
        if not section:
            continue
        api_key = section.get("api_key", "")
        base_url = section.get("base_url", "https://api.openai.com/v1")
        model = section.get("model", "gpt-4o-mini")
        if not api_key:
            logger.warning("llm.%s.api_key is missing — skipping capability %s", section_key, capability)
            continue
        providers[capability] = LLMProvider(
            capability=capability,
            base_url=base_url,
            api_key=api_key,
            model=model,
        )
    return LLMService(providers)


def _generate_help_text(plugins: list) -> str:
    """Build /help text from all loaded plugin commands."""
    lines: list[str] = ["*DailyClaw 指令列表*\n"]
    for plugin in plugins:
        cmds = plugin.get_commands()
        if not cmds:
            continue
        lines.append(f"*{plugin.description or plugin.name}*")
        for cmd in cmds:
            prefix = " (管理员)" if cmd.admin_only else ""
            lines.append(f"  /{cmd.name} — {cmd.description}{prefix}")
    lines.append("\n框架指令")
    lines.append("  /start — 欢迎消息")
    lines.append("  /help — 显示帮助")
    lines.append("  /invite <user_id> — 邀请用户 (管理员)")
    lines.append("  /kick <user_id> — 踢出用户 (管理员)")
    return "\n".join(lines)


def _make_start_handler() -> Command:
    async def handler(event: Event) -> str:
        return "欢迎使用 DailyClaw！发送 /help 查看指令列表。"

    return Command(name="start", description="欢迎消息", handler=handler)


def _make_help_handler(help_text: str) -> Command:
    async def handler(event: Event) -> str:
        return help_text

    return Command(name="help", description="显示帮助", handler=handler)


def _make_invite_handler(db: Database) -> Command:
    async def handler(event: Event) -> str:
        if not event.text:
            return "用法: /invite <user_id>"
        parts = event.text.strip().split()
        # parts[0] is the command itself; user_id is the argument
        args = [p for p in parts if not p.startswith("/")]
        if not args:
            return "用法: /invite <user_id>"
        try:
            target_id = int(args[0])
        except ValueError:
            return f"无效的 user_id: {args[0]}"
        await db.conn.execute(
            "INSERT OR IGNORE INTO allowed_users (user_id, added_by) VALUES (?, ?)",
            (target_id, event.user_id),
        )
        await db.conn.commit()
        logger.info("User %d invited by admin %d", target_id, event.user_id)
        return f"已邀请用户 {target_id}"

    return Command(name="invite", description="邀请用户", handler=handler, admin_only=True)


def _make_kick_handler(db: Database) -> Command:
    async def handler(event: Event) -> str:
        if not event.text:
            return "用法: /kick <user_id>"
        parts = event.text.strip().split()
        args = [p for p in parts if not p.startswith("/")]
        if not args:
            return "用法: /kick <user_id>"
        try:
            target_id = int(args[0])
        except ValueError:
            return f"无效的 user_id: {args[0]}"
        await db.conn.execute(
            "DELETE FROM allowed_users WHERE user_id = ?",
            (target_id,),
        )
        await db.conn.commit()
        logger.info("User %d kicked by admin %d", target_id, event.user_id)
        return f"已踢出用户 {target_id}"

    return Command(name="kick", description="踢出用户", handler=handler, admin_only=True)


async def _run(config: dict, tz: ZoneInfo) -> None:
    """Async main — sets up all components and starts the bot."""
    # 1. Database
    db = Database()
    await db.connect()
    logger.info("Database connected")

    # 2. Core migrations (allowed_users, etc.)
    runner = MigrationRunner(db)
    await runner.run("core", _CORE_MIGRATIONS_DIR)
    logger.info("Core migrations applied")

    # 3. LLM service
    llm = _build_llm_service(config["llm"])
    logger.info(
        "LLMService built with capabilities: %s",
        [c.value for c in llm._providers],
    )

    # 4. Telegram adapter
    token = config["telegram"]["token"]
    admin_ids: list[int] = config.get("telegram", {}).get("allowed_user_ids", [])
    adapter = TelegramAdapter(token=token, admin_ids=admin_ids)

    # 5. Scheduler from adapter (build app first to get job_queue)
    app = adapter.build()
    from .adapters.telegram import TelegramScheduler
    scheduler = TelegramScheduler(app.job_queue)

    # 6. Plugin discovery
    registry = PluginRegistry(
        db=db,
        llm=llm,
        bot=adapter,
        scheduler=scheduler,
        config=config,
        tz=tz,
    )
    plugins = await registry.discover(_PLUGINS_DIR)
    logger.info("Loaded %d plugin(s)", len(plugins))

    # 7. Register plugin commands/handlers/conversations
    for plugin in plugins:
        for cmd in plugin.get_commands():
            adapter.register_command(cmd)
        for mh in plugin.get_handlers():
            adapter.register_handler(mh)
        for conv in plugin.get_conversations():
            adapter.register_conversation(conv)

    # 8. Generate /help text and register framework commands
    help_text = _generate_help_text(plugins)
    adapter.register_command(_make_start_handler())
    adapter.register_command(_make_help_handler(help_text))
    adapter.register_command(_make_invite_handler(db))
    adapter.register_command(_make_kick_handler(db))

    # 9. Rebuild app with all handlers registered
    app = adapter.build()

    logger.info("DailyClaw starting with %d plugin(s)...", len(plugins))

    try:
        await adapter.start()
        # Keep running until interrupted
        stop_event = asyncio.Event()
        try:
            await stop_event.wait()
        except asyncio.CancelledError:
            pass
    finally:
        await registry.shutdown_all()
        await adapter.stop()
        await db.close()
        logger.info("DailyClaw stopped cleanly")


def main() -> None:
    """Entry point: load config, set up timezone, and run the async loop."""
    config = load_config()

    tz_name = config.get("timezone", "Asia/Shanghai")
    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:
        raise RuntimeError(
            f"Timezone '{tz_name}' not found. Install 'tzdata': pip install tzdata"
        ) from exc

    logger.info("DailyClaw starting... timezone=%s", tz_name)

    asyncio.run(_run(config, tz))


if __name__ == "__main__":
    main()
