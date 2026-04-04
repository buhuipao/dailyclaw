"""Tests for the sharing plugin."""
from __future__ import annotations

import pytest
from zoneinfo import ZoneInfo

from src.core.context import AppContext
from src.plugins.sharing import SharingPlugin


@pytest.fixture
def ctx(fake_llm, fake_bot, fake_scheduler, db):
    return AppContext(
        db=db,
        llm=fake_llm(),
        bot=fake_bot,
        scheduler=fake_scheduler,
        config={},
        tz=ZoneInfo("Asia/Shanghai"),
    )


@pytest.fixture
def plugin(ctx):
    return SharingPlugin(ctx)


class TestSharingPluginMetadata:
    def test_name(self, plugin):
        assert plugin.name == "sharing"

    def test_version(self, plugin):
        assert plugin.version == "1.0.0"

    def test_description(self, plugin):
        assert "分享" in plugin.description or "总结" in plugin.description


class TestSharingPluginCommands:
    def test_get_commands_returns_two_commands(self, plugin):
        commands = plugin.get_commands()
        assert len(commands) == 2

    def test_sharing_summary_command_registered(self, plugin):
        commands = plugin.get_commands()
        names = [cmd.name for cmd in commands]
        assert "sharing_summary" in names

    def test_sharing_export_command_registered(self, plugin):
        commands = plugin.get_commands()
        names = [cmd.name for cmd in commands]
        assert "sharing_export" in names

    def test_commands_have_handlers(self, plugin):
        commands = plugin.get_commands()
        for cmd in commands:
            assert callable(cmd.handler), f"{cmd.name} has no callable handler"
