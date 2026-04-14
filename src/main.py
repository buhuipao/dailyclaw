"""DailyClaw entry point — plugin-based Telegram bot for daily journaling."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .adapters.telegram import TelegramAdapter
from .config import load_config
from .core.bot import Command, Event, MessageHandler, MessageType
from .core.db import Database, MigrationRunner
from .core.i18n import t, SUPPORTED_LANGS
from .core.intent_router import IntentRouter
from .core.llm import Capability, LLMProvider, LLMService
from .core.plugin import PluginRegistry

import src.main_locale  # noqa: F401

# Initial logging setup — reconfigured in main() after config is loaded
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
)
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def _configure_logging(config: dict) -> None:
    """Set log level from config > env var > default (DEBUG).

    config.yaml example:
        log_level: INFO
    """
    level_str = (
        config.get("log_level")
        or os.environ.get("LOG_LEVEL")
        or "DEBUG"
    ).upper()
    level = getattr(logging, level_str, logging.DEBUG)
    logging.getLogger().setLevel(level)
    logger.info("Log level: %s", level_str)

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


_PLUGIN_EMOJI: dict[str, str] = {
    "reflect": "🌙",
    "track": "📊",
    "memo": "📝",
    "wiki": "🧠",
}


def _generate_help_text(plugins: list, lang: str = "en", is_admin: bool = False) -> str:
    """Build /help text from all loaded plugin commands."""
    lines: list[str] = [t("main.help_header", lang)]
    for plugin in plugins:
        cmds = plugin.get_commands()
        if not cmds:
            continue
        emoji = _PLUGIN_EMOJI.get(plugin.name, "📌")
        # Use localized plugin description from locale file
        desc = t(f"{plugin.name}.description", lang)
        # Fallback to plugin.description if no locale key found
        if desc == f"{plugin.name}.description":
            desc = plugin.description or plugin.name
        lines.append(f"{emoji} *{desc}*")
        for cmd in cmds:
            # Use localized command description from locale file
            cmd_key = cmd.name.replace(f"{plugin.name}_", "")
            localized_desc = t(f"{plugin.name}.cmd.{cmd_key}", lang)
            if localized_desc == f"{plugin.name}.cmd.{cmd_key}":
                localized_desc = cmd.description
            prefix = t("main.admin_suffix", lang) if cmd.admin_only else ""
            lines.append(f"  /{cmd.name} — {localized_desc}{prefix}")
        lines.append("")
    lines.append(t("main.help_general_section", lang))
    lines.append(t("main.help_lang", lang))
    lines.append("")
    if is_admin:
        lines.append(t("main.help_admin_section", lang))
        lines.append(t("main.help_invite", lang))
        lines.append(t("main.help_kick", lang))
        lines.append(t("main.help_stats", lang))
        lines.append("")
    lines.append(t("main.help_footer", lang))
    return "\n".join(lines)


def _make_start_handler() -> Command:
    async def handler(event: Event) -> str:
        return t("main.welcome", event.lang)

    return Command(name="start", description=t("main.cmd.start"), handler=handler)


def _make_help_handlers(plugins: list) -> list[Command]:
    async def handler(event: Event) -> str:
        return _generate_help_text(plugins, event.lang, is_admin=event.is_admin)

    return [
        Command(name="help", description=t("main.cmd.help"), handler=handler),
        Command(name="h", description=t("main.cmd.help"), handler=handler),
    ]


def _make_invite_handler(db: Database) -> Command:
    async def handler(event: Event) -> str:
        if not event.text:
            return t("main.invite_usage", event.lang)
        parts = event.text.strip().split()
        # parts[0] is the command itself; user_id is the argument
        args = [p for p in parts if not p.startswith("/")]
        if not args:
            return t("main.invite_usage", event.lang)
        try:
            target_id = int(args[0])
        except ValueError:
            return t("main.invalid_user_id", event.lang, id=args[0])
        await db.conn.execute(
            "INSERT OR IGNORE INTO allowed_users (user_id, added_by) VALUES (?, ?)",
            (target_id, event.user_id),
        )
        await db.conn.commit()
        logger.info("User %d invited by admin %d", target_id, event.user_id)
        return t("main.invite_success", event.lang, id=target_id)

    return Command(name="invite", description=t("main.cmd.invite"), handler=handler, admin_only=True)


def _make_kick_handler(db: Database) -> Command:
    async def handler(event: Event) -> str:
        if not event.text:
            return t("main.kick_usage", event.lang)
        parts = event.text.strip().split()
        args = [p for p in parts if not p.startswith("/")]
        if not args:
            return t("main.kick_usage", event.lang)
        try:
            target_id = int(args[0])
        except ValueError:
            return t("main.invalid_user_id", event.lang, id=args[0])
        await db.conn.execute(
            "DELETE FROM allowed_users WHERE user_id = ?",
            (target_id,),
        )
        await db.conn.commit()
        logger.info("User %d kicked by admin %d", target_id, event.user_id)
        return t("main.kick_success", event.lang, id=target_id)

    return Command(name="kick", description=t("main.cmd.kick"), handler=handler, admin_only=True)


def _make_stats_handler(db: Database) -> Command:
    async def handler(event: Event) -> str:
        lang = event.lang
        today = datetime.now().strftime("%Y-%m-%d")

        # All invited users
        cursor = await db.conn.execute(
            "SELECT user_id, created_at FROM allowed_users ORDER BY created_at",
        )
        invited = await cursor.fetchall()
        invited_ids = {row[0] for row in invited}

        # Per-user message counts (today + total + first seen)
        cursor = await db.conn.execute(
            "SELECT user_id, "
            "  COUNT(*) AS total, "
            "  SUM(CASE WHEN date(created_at) = ? THEN 1 ELSE 0 END) AS today, "
            "  MIN(created_at) AS first_seen "
            "FROM messages WHERE deleted_at IS NULL "
            "GROUP BY user_id ORDER BY total DESC",
            (today,),
        )
        stats = await cursor.fetchall()
        stat_map = {row[0]: (row[1], row[2], row[3]) for row in stats}

        # Users from message_queue who aren't in messages yet
        cursor = await db.conn.execute(
            "SELECT user_id, MIN(created_at) AS first_seen FROM message_queue "
            "WHERE user_id NOT IN (SELECT DISTINCT user_id FROM messages WHERE deleted_at IS NULL) "
            "GROUP BY user_id",
        )
        extra_users = await cursor.fetchall()

        lines = [t("main.user_list_header", lang)]

        # Invited users
        if invited:
            lines.append(t("main.user_list_invited", lang))
            for row in invited:
                uid = row[0]
                total, today_count, first_seen = stat_map.pop(uid, (0, 0, None))
                joined = row[1][:10] if row[1] else (first_seen[:10] if first_seen else "?")
                lines.append(f"  {uid} — {t('main.user_list_stats', lang, today=today_count, total=total, joined=joined)}")
            lines.append("")

        # Trial users (have messages but not invited)
        trial_entries = [
            (uid, total, today_count, first_seen)
            for uid, (total, today_count, first_seen) in stat_map.items()
        ]
        trial_extra = [
            (row[0], 0, 0, row[1])
            for row in extra_users if row[0] not in stat_map
        ]
        trial_all = trial_entries + trial_extra

        if trial_all:
            lines.append(t("main.user_list_trial", lang))
            for uid, total, today_count, first_seen in sorted(trial_all, key=lambda x: -x[1]):
                joined = first_seen[:10] if first_seen else "?"
                lines.append(f"  {uid} — {t('main.user_list_stats', lang, today=today_count, total=total, joined=joined)}")

        if not invited and not trial_all:
            lines.append(t("main.user_list_empty", lang))

        return "\n".join(lines)

    return Command(name="stats", description=t("main.cmd.stats"), handler=handler, admin_only=True)


def _make_lang_handler(db: Database, adapter: TelegramAdapter) -> Command:
    async def handler(event: Event) -> str:
        text = (event.text or "").strip().lower()
        if not text:
            return t("main.lang_usage", event.lang, current=event.lang)
        if text not in SUPPORTED_LANGS:
            return t("main.lang_invalid", event.lang, lang=text)
        await db.conn.execute(
            "UPDATE allowed_users SET lang = ? WHERE user_id = ?",
            (text, event.user_id),
        )
        await db.conn.commit()
        # Refresh lang cache immediately so next message uses new lang
        adapter._auth.update_lang_cache(
            {**adapter._auth._user_langs, event.user_id: text}
        )
        lang_name = t(f"shared.lang_name.{text}", text)
        return t("main.lang_success", text, lang_name=lang_name)

    return Command(name="lang", description="Switch language / 切换语言 / 言語切替", handler=handler)


class _LazyScheduler:
    """Buffers job registrations until the real scheduler is ready.

    Problem: plugins call scheduler.run_daily() during on_startup(), but
    the final Telegram Application (with its JobQueue) isn't built yet.
    This class records all calls, then replays them onto the real scheduler.
    After replay, it delegates all future calls directly.
    """

    def __init__(self) -> None:
        self._pending: list[tuple[str, tuple, dict]] = []
        self._delegate: object | None = None

    def set_delegate(self, scheduler: object) -> None:
        self._delegate = scheduler

    async def run_daily(self, callback, time, name, **kwargs) -> None:
        if self._delegate is not None:
            await self._delegate.run_daily(callback, time=time, name=name, **kwargs)
        else:
            self._pending.append(("run_daily", (callback, time, name), kwargs))

    async def run_repeating(self, callback, interval, name, **kwargs) -> None:
        if self._delegate is not None:
            await self._delegate.run_repeating(callback, interval=interval, name=name, **kwargs)
        else:
            self._pending.append(("run_repeating", (callback, interval, name), kwargs))

    async def cancel(self, name: str) -> None:
        if self._delegate is not None:
            await self._delegate.cancel(name)

    async def replay_onto(self, scheduler: object) -> None:
        """Replay all buffered calls onto the real scheduler."""
        for method_name, args, kwargs in self._pending:
            method = getattr(scheduler, method_name)
            if method_name == "run_daily":
                await method(args[0], time=args[1], name=args[2], **kwargs)
            elif method_name == "run_repeating":
                await method(args[0], interval=args[1], name=args[2], **kwargs)
        logger.info("Replayed %d deferred scheduler jobs", len(self._pending))
        self._pending.clear()


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

    # 4. Telegram adapter with trial-user rate limiting
    from .core.rate_limit import RateLimiter

    token = config["telegram"]["token"]
    admin_ids: list[int] = config.get("telegram", {}).get("allowed_user_ids", [])
    trial_cfg = config.get("trial", {})
    rate_limiter = RateLimiter(
        rate_per_minute=trial_cfg.get("rate_per_minute", 10),
        daily_quota=trial_cfg.get("daily_quota", 50),
    )
    adapter = TelegramAdapter(
        token=token, admin_ids=admin_ids, db=db, rate_limiter=rate_limiter,
    )

    # 5. Use a lazy scheduler that defers job registration until the final
    #    Application is built.  This is needed because adapter.build() creates
    #    a new Application (and a new JobQueue) each time it's called.
    from .adapters.telegram import TelegramScheduler
    lazy_scheduler = _LazyScheduler()

    # 6. Plugin discovery (plugins register jobs on the lazy scheduler)
    registry = PluginRegistry(
        db=db,
        llm=llm,
        bot=adapter,
        scheduler=lazy_scheduler,
        config=config,
        tz=tz,
    )
    plugins = await registry.discover(_PLUGINS_DIR)
    logger.info("Loaded %d plugin(s)", len(plugins))

    # Wire wiki nudge hook if wiki plugin is loaded
    wiki_plugin = next((p for p in plugins if p.name == "wiki"), None)
    if wiki_plugin:
        from src.plugins.wiki.db import WikiDB
        from src.plugins.wiki.nudge import check_nudge

        wiki_config = config.get("plugins", {}).get("wiki", {})
        nudge_enabled = wiki_config.get("nudge_enabled", True)
        nudge_threshold = wiki_config.get("nudge_threshold", 0.85)
        nudge_max = wiki_config.get("nudge_max_per_day", 3)

        if nudge_enabled:
            async def _wiki_nudge(user_id: int, content: str, lang: str) -> str | None:
                wiki_db = WikiDB(db)
                return await check_nudge(
                    llm, wiki_db, user_id, content, lang,
                    threshold=nudge_threshold, max_per_day=nudge_max,
                )

            # Rebuild memo plugin's AppContext with the nudge hook
            for plugin in plugins:
                if plugin.name == "memo":
                    from src.core.context import AppContext as _AC
                    plugin.ctx = _AC(
                        db=plugin.ctx.db,
                        llm=plugin.ctx.llm,
                        bot=plugin.ctx.bot,
                        scheduler=plugin.ctx.scheduler,
                        config=plugin.ctx.config,
                        tz=plugin.ctx.tz,
                        wiki_nudge=_wiki_nudge,
                    )
                    break
            logger.info("Wiki nudge hook wired to memo plugin")

    # 7. Register plugin commands/handlers/conversations
    #    For TEXT handlers, intercept and wrap with IntentRouter so that
    #    natural language is routed to the right plugin before falling
    #    back to the Recorder.
    text_fallback = None
    intent_plugins: list[tuple] = []

    for plugin in plugins:
        for cmd in plugin.get_commands():
            adapter.register_command(cmd)

        for mh in plugin.get_handlers():
            if mh.msg_type == MessageType.TEXT:
                text_fallback = mh.handler  # Recorder's text handler
            else:
                adapter.register_handler(mh)

        for conv in plugin.get_conversations():
            adapter.register_conversation(conv)

        intents = plugin.get_intents()
        if intents:
            intent_plugins.append((plugin, intents))

    if intent_plugins and text_fallback is not None:
        router = IntentRouter.create(
            llm=llm,
            recorder_handler=text_fallback,
            plugin_intents=[
                (intents, plugin.get_intent_context)
                for plugin, intents in intent_plugins
            ],
        )
        adapter.register_handler(MessageHandler(
            msg_type=MessageType.TEXT,
            handler=router.handle,
            priority=0,
        ))
        logger.info(
            "IntentRouter active with %d intent(s) from %d plugin(s)",
            sum(len(i) for _, i in intent_plugins),
            len(intent_plugins),
        )
    elif text_fallback is not None:
        # No intents declared — register Recorder's text handler directly
        adapter.register_handler(MessageHandler(
            msg_type=MessageType.TEXT,
            handler=text_fallback,
            priority=0,
        ))

    # 8. Register framework commands (help is generated dynamically per-request)
    adapter.register_command(_make_start_handler())
    for cmd in _make_help_handlers(plugins):
        adapter.register_command(cmd)
    adapter.register_command(_make_invite_handler(db))
    adapter.register_command(_make_kick_handler(db))
    adapter.register_command(_make_stats_handler(db))
    adapter.register_command(_make_lang_handler(db, adapter))

    # Sync config admin IDs into allowed_users table so that scheduled
    # jobs, /lang, and other DB-based lookups work for config-defined users.
    for uid in admin_ids:
        await db.conn.execute(
            "INSERT OR IGNORE INTO allowed_users (user_id, added_by) VALUES (?, ?)",
            (uid, 0),
        )
    await db.conn.commit()

    # Populate initial lang cache
    async def _refresh_lang_cache() -> None:
        try:
            cursor = await db.conn.execute("SELECT user_id, lang FROM allowed_users")
            rows = await cursor.fetchall()
            user_langs = {row[0]: row[1] for row in rows}
            adapter._auth.update_lang_cache(user_langs)
        except Exception:
            pass

    await _refresh_lang_cache()

    # 9. Build FINAL app with all handlers, then replay deferred jobs
    app = adapter.build()
    real_scheduler = TelegramScheduler(app.job_queue)
    await lazy_scheduler.replay_onto(real_scheduler)
    # Update the ctx.scheduler reference for runtime use (e.g. /planner_add)
    lazy_scheduler.set_delegate(real_scheduler)

    logger.info("DailyClaw starting with %d plugin(s)...", len(plugins))

    # Retry startup — network may be flaky (proxy not yet ready, etc.)
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            await adapter.start()
            break
        except Exception as exc:
            logger.warning(
                "Startup failed (attempt %d/%d): %s", attempt, max_attempts, exc,
            )
            if attempt == max_attempts:
                logger.error("Giving up after %d startup attempts", max_attempts)
                await registry.shutdown_all()
                await db.close()
                raise
            await asyncio.sleep(3)
            # Rebuild app for fresh connection pool, re-register jobs
            app = adapter.build()
            real_scheduler = TelegramScheduler(app.job_queue)
            await lazy_scheduler.replay_onto(real_scheduler)
            lazy_scheduler.set_delegate(real_scheduler)

    try:
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


def _log_startup_banner(config: dict, tz_name: str) -> None:
    """Log configuration summary at startup."""
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    db_path = config.get("database", {}).get("path", "data/dailyclaw.db")
    admin_ids = config.get("telegram", {}).get("allowed_user_ids", [])
    config_path = os.environ.get("CONFIG_PATH", "config.yaml")

    logger.info("=" * 50)
    logger.info("DailyClaw starting")
    logger.info("  config:   %s", config_path)
    logger.info("  timezone: %s", tz_name)
    logger.info("  database: %s", db_path)
    logger.info("  proxy:    %s", proxy or "(direct)")
    logger.info("  admins:   %s", admin_ids or "(none — open to all)")

    llm_cfg = config.get("llm", {})
    for cap in ("text", "vision", "audio", "video"):
        section = llm_cfg.get(cap)
        if section and section.get("api_key"):
            logger.info("  llm.%-6s %s @ %s", cap + ":", section.get("model", "?"), section.get("base_url", "?"))

    plugins_cfg = config.get("plugins", {})
    if plugins_cfg:
        logger.info("  plugins:  %s", ", ".join(sorted(plugins_cfg.keys())))
    logger.info("=" * 50)


def main() -> None:
    """Entry point: load config, set up timezone, and run the async loop."""
    config = load_config()
    _configure_logging(config)

    tz_name = config.get("timezone", "Asia/Shanghai")
    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:
        raise RuntimeError(
            f"Timezone '{tz_name}' not found. Install 'tzdata': pip install tzdata"
        ) from exc

    _log_startup_banner(config, tz_name)

    asyncio.run(_run(config, tz))


if __name__ == "__main__":
    main()
