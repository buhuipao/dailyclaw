"""Integration tests for full plugin discovery pipeline."""
from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio

from src.core.db import Database
from src.core.plugin import PluginRegistry

# ---------------------------------------------------------------------------
# Fakes (inline — no mocks needed for integration tests)
# ---------------------------------------------------------------------------

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "src" / "plugins"
UTC = ZoneInfo("UTC")


class FakeLLM:
    def supports(self, cap: str) -> bool:
        return True

    async def chat(self, messages: list[dict], **kwargs) -> str:
        return "ok"

    async def classify(self, text: str) -> dict:
        return {"category": "other", "summary": "", "tags": ""}

    async def summarize_text(self, text: str, url: str = "") -> str:
        return "summary"

    async def parse_plan(self, text: str) -> dict:
        return {}

    async def match_checkin(self, text: str, plans: list[dict]) -> dict:
        return {}

    async def analyze_image(self, image_bytes: bytes, prompt: str = "") -> str:
        return "image"


class FakeBot:
    def register_command(self, cmd) -> None:
        pass

    def register_handler(self, handler) -> None:
        pass

    def register_conversation(self, conv) -> None:
        pass


class FakeScheduler:
    async def run_daily(self, *args, **kwargs) -> None:
        pass

    async def run_repeating(self, *args, **kwargs) -> None:
        pass

    async def cancel(self, name: str) -> None:
        pass


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

CORE_MIGRATIONS = str(Path(__file__).resolve().parent.parent / "src" / "core" / "migrations")


@pytest_asyncio.fixture
async def registry_with_plugins(tmp_path):
    """Return (registry, plugins) after full discovery from src/plugins/."""
    from src.core.db import MigrationRunner

    db_path = str(tmp_path / "integration.db")
    db = Database(db_path=db_path)
    await db.connect()

    # Run core migrations first (allowed_users, message_queue)
    runner = MigrationRunner(db)
    await runner.run("core", CORE_MIGRATIONS)

    config = {
        "plugins": {
            "recorder": {},
            "journal": {},
            "planner": {},
        }
    }

    registry = PluginRegistry(
        db=db,
        llm=FakeLLM(),
        bot=FakeBot(),
        scheduler=FakeScheduler(),
        config=config,
        tz=UTC,
    )

    plugins = await registry.discover(str(PLUGINS_DIR))

    yield db, registry, plugins

    await registry.shutdown_all()
    await db.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_plugin_discovery(registry_with_plugins):
    """All 4 built-in plugins load successfully in alphabetical order."""
    _db, _registry, plugins = registry_with_plugins

    assert len(plugins) == 3

    names = [p.name for p in plugins]
    assert names == sorted(names), "Plugins should be loaded in alphabetical order"
    assert set(names) == {"journal", "planner", "recorder"}


@pytest.mark.asyncio
async def test_all_commands_registered(registry_with_plugins):
    """All expected commands are provided by the loaded plugins."""
    _db, _registry, plugins = registry_with_plugins

    all_commands: set[str] = set()
    for plugin in plugins:
        for cmd in plugin.get_commands():
            all_commands.add(cmd.name)

    expected = {
        "recorder_today",
        "recorder_del",
        "recorder_list",
        "journal_start",
        "journal_today",
        "journal_summary",
        "journal_cancel",
        "planner_add",
        "planner_del",
        "planner_checkin",
        "planner_list",
    }

    missing = expected - all_commands
    assert not missing, f"Missing commands: {missing}"


@pytest.mark.asyncio
async def test_migrations_run_for_all_plugins(registry_with_plugins):
    """All expected database tables are created after plugin discovery."""
    db, _registry, _plugins = registry_with_plugins

    cursor = await db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    rows = await cursor.fetchall()
    existing_tables = {row["name"] for row in rows}

    expected_tables = {
        "messages",
        "message_queue",
        "journal_entries",
        "summaries",
        "plans",
        "plan_checkins",
        "schema_versions",
    }

    missing = expected_tables - existing_tables
    assert not missing, f"Missing tables: {missing}"
