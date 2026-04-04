"""BasePlugin ABC and PluginRegistry for the DailyClaw plugin system."""
from __future__ import annotations

import importlib.util
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from zoneinfo import ZoneInfo

from src.core.bot import Command, ConversationFlow, MessageHandler
from src.core.context import AppContext
from src.core.db import Database, MigrationRunner

logger = logging.getLogger(__name__)


class BasePlugin(ABC):
    """Abstract base class that all plugins must inherit."""

    name: str = ""
    version: str = "0.1.0"
    description: str = ""

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx

    @abstractmethod
    def get_commands(self) -> list[Command]:
        """Return the list of bot commands this plugin provides."""

    def get_handlers(self) -> list[MessageHandler]:
        """Return the list of message handlers this plugin provides."""
        return []

    def get_conversations(self) -> list[ConversationFlow]:
        """Return the list of conversation flows this plugin provides."""
        return []

    async def on_startup(self) -> None:
        """Called once after the plugin is instantiated. Override as needed."""

    async def on_shutdown(self) -> None:
        """Called once before the plugin is unloaded. Override as needed."""


class PluginRegistry:
    """Discovers, loads, and manages plugin lifecycle."""

    def __init__(
        self,
        db: Database,
        llm: object,
        bot: object,
        scheduler: object,
        config: dict,
        tz: ZoneInfo,
    ) -> None:
        self._db = db
        self._llm = llm
        self._bot = bot
        self._scheduler = scheduler
        self._config = config
        self._tz = tz
        self._plugins: list[BasePlugin] = []

    async def discover(self, plugins_dir: str) -> list[BasePlugin]:
        """Scan *plugins_dir* for plugin packages and load them in alphabetical order.

        A plugin package is a subdirectory containing an ``__init__.py``.
        For each package the registry will:

        1. Run any SQL migrations found in a ``migrations/`` sub-directory.
        2. Import the package's ``__init__`` module.
        3. Find the first ``BasePlugin`` subclass defined in that module.
        4. Build an ``AppContext`` with plugin-specific config.
        5. Instantiate the plugin and call ``on_startup()``.

        If migration or loading fails for a plugin, the error is logged and
        that plugin is skipped — other plugins are still loaded.
        """
        root = Path(plugins_dir)
        if not root.is_dir():
            logger.debug("plugins_dir %s does not exist — skipping discovery", plugins_dir)
            return []

        runner = MigrationRunner(self._db)
        loaded: list[BasePlugin] = []

        plugin_dirs = sorted(
            p for p in root.iterdir() if p.is_dir() and (p / "__init__.py").exists()
        )

        for pkg_dir in plugin_dirs:
            pkg_name = pkg_dir.name
            migrations_dir = str(pkg_dir / "migrations")

            # 1. Run migrations
            try:
                await runner.run(pkg_name, migrations_dir)
            except Exception:
                logger.error(
                    "Migration failed for plugin %s — skipping", pkg_name, exc_info=True
                )
                continue

            # 2. Import __init__.py
            init_file = pkg_dir / "__init__.py"
            try:
                spec = importlib.util.spec_from_file_location(
                    f"_dailyclaw_plugin_{pkg_name}", str(init_file)
                )
                if spec is None or spec.loader is None:
                    raise ImportError(f"Cannot load spec from {init_file}")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)  # type: ignore[union-attr]
            except Exception:
                logger.error(
                    "Import failed for plugin %s — skipping", pkg_name, exc_info=True
                )
                continue

            # 3. Find first BasePlugin subclass
            plugin_cls: type[BasePlugin] | None = None
            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, BasePlugin)
                    and obj is not BasePlugin
                ):
                    plugin_cls = obj
                    break

            if plugin_cls is None:
                logger.warning(
                    "No BasePlugin subclass found in plugin %s — skipping", pkg_name
                )
                continue

            # 4. Build plugin-specific AppContext
            plugin_config = self._config.get("plugins", {}).get(plugin_cls.name, {})
            ctx = AppContext(
                db=self._db,
                llm=self._llm,
                bot=self._bot,
                scheduler=self._scheduler,
                config=plugin_config,
                tz=self._tz,
            )

            # 5. Instantiate and start up
            try:
                plugin = plugin_cls(ctx)
                await plugin.on_startup()
                loaded.append(plugin)
                logger.info("Loaded plugin %s v%s", plugin_cls.name, plugin_cls.version)
            except Exception:
                logger.error(
                    "Startup failed for plugin %s — skipping", pkg_name, exc_info=True
                )
                continue

        self._plugins = loaded
        return loaded

    async def shutdown_all(self) -> None:
        """Call ``on_shutdown()`` on all loaded plugins in reverse order."""
        for plugin in reversed(self._plugins):
            try:
                await plugin.on_shutdown()
            except Exception:
                logger.error(
                    "Shutdown error in plugin %s", plugin.name, exc_info=True
                )
