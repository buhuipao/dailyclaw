"""Tests for src/core/bot.py — frozen dataclasses and BotAdapter ABC."""
from __future__ import annotations

import dataclasses
import pytest

from src.core.bot import (
    BotAdapter,
    Command,
    ConversationFlow,
    Event,
    MessageHandler,
    MessageRef,
    MessageType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _dummy_handler(event: Event) -> str | None:
    return None


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

class TestEvent:
    def test_defaults_are_none_or_false(self) -> None:
        event = Event(user_id=1, chat_id=100)
        assert event.text is None
        assert event.photo_file_id is None
        assert event.voice_file_id is None
        assert event.video_file_id is None
        assert event.caption is None
        assert event.is_admin is False
        assert event.raw is None

    def test_required_fields_set_correctly(self) -> None:
        event = Event(user_id=42, chat_id=999, text="hello")
        assert event.user_id == 42
        assert event.chat_id == 999
        assert event.text == "hello"

    def test_is_frozen(self) -> None:
        event = Event(user_id=1, chat_id=100)
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.text = "mutated"  # type: ignore[misc]

    def test_is_admin_can_be_set(self) -> None:
        event = Event(user_id=1, chat_id=100, is_admin=True)
        assert event.is_admin is True

    def test_raw_can_hold_arbitrary_value(self) -> None:
        payload = {"key": "value"}
        event = Event(user_id=1, chat_id=100, raw=payload)
        assert event.raw == payload


# ---------------------------------------------------------------------------
# MessageRef
# ---------------------------------------------------------------------------

class TestMessageRef:
    def test_fields_set_correctly(self) -> None:
        ref = MessageRef(chat_id=10, message_id=20)
        assert ref.chat_id == 10
        assert ref.message_id == 20

    def test_is_frozen(self) -> None:
        ref = MessageRef(chat_id=10, message_id=20)
        with pytest.raises(dataclasses.FrozenInstanceError):
            ref.message_id = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class TestCommand:
    def test_creation_with_defaults(self) -> None:
        cmd = Command(name="start", description="Start bot", handler=_dummy_handler)
        assert cmd.name == "start"
        assert cmd.description == "Start bot"
        assert cmd.handler is _dummy_handler
        assert cmd.admin_only is False

    def test_admin_only_flag(self) -> None:
        cmd = Command(
            name="admin",
            description="Admin command",
            handler=_dummy_handler,
            admin_only=True,
        )
        assert cmd.admin_only is True

    def test_is_frozen(self) -> None:
        cmd = Command(name="start", description="Start", handler=_dummy_handler)
        with pytest.raises(dataclasses.FrozenInstanceError):
            cmd.name = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# MessageHandler
# ---------------------------------------------------------------------------

class TestMessageHandler:
    def test_creation_with_default_priority(self) -> None:
        mh = MessageHandler(msg_type=MessageType.TEXT, handler=_dummy_handler)
        assert mh.msg_type == MessageType.TEXT
        assert mh.handler is _dummy_handler
        assert mh.priority == 0

    def test_custom_priority(self) -> None:
        mh = MessageHandler(
            msg_type=MessageType.PHOTO, handler=_dummy_handler, priority=10
        )
        assert mh.priority == 10

    def test_is_frozen(self) -> None:
        mh = MessageHandler(msg_type=MessageType.TEXT, handler=_dummy_handler)
        with pytest.raises(dataclasses.FrozenInstanceError):
            mh.priority = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ConversationFlow
# ---------------------------------------------------------------------------

class TestConversationFlow:
    def test_default_cancel_command(self) -> None:
        flow = ConversationFlow(
            name="onboarding",
            entry_command="start",
            entry_handler=_dummy_handler,
            states={0: _dummy_handler},
        )
        assert flow.cancel_command == "cancel"

    def test_custom_cancel_command(self) -> None:
        flow = ConversationFlow(
            name="onboarding",
            entry_command="start",
            entry_handler=_dummy_handler,
            states={0: _dummy_handler},
            cancel_command="quit",
        )
        assert flow.cancel_command == "quit"

    def test_is_frozen(self) -> None:
        flow = ConversationFlow(
            name="onboarding",
            entry_command="start",
            entry_handler=_dummy_handler,
            states={0: _dummy_handler},
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            flow.name = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# MessageType
# ---------------------------------------------------------------------------

class TestMessageType:
    def test_enum_values(self) -> None:
        assert MessageType.TEXT == "text"
        assert MessageType.PHOTO == "photo"
        assert MessageType.VOICE == "voice"
        assert MessageType.VIDEO == "video"
        assert MessageType.COMMAND == "command"

    def test_is_string_subclass(self) -> None:
        assert isinstance(MessageType.TEXT, str)


# ---------------------------------------------------------------------------
# BotAdapter
# ---------------------------------------------------------------------------

class TestBotAdapter:
    def test_cannot_be_instantiated_directly(self) -> None:
        with pytest.raises(TypeError):
            BotAdapter()  # type: ignore[abstract]

    def test_concrete_subclass_without_all_methods_raises(self) -> None:
        class PartialAdapter(BotAdapter):
            async def start(self) -> None: ...
            # Missing the rest of the abstract methods

        with pytest.raises(TypeError):
            PartialAdapter()  # type: ignore[abstract]

    def test_concrete_subclass_with_all_methods_instantiates(self) -> None:
        class FullAdapter(BotAdapter):
            async def start(self) -> None: ...
            async def stop(self) -> None: ...
            async def send_message(self, chat_id: int, text: str) -> MessageRef:
                return MessageRef(chat_id=chat_id, message_id=0)
            async def edit_message(self, chat_id: int, message_id: int, text: str) -> None: ...
            async def reply(self, event: Event, text: str) -> MessageRef:
                return MessageRef(chat_id=event.chat_id, message_id=0)
            async def download_file(self, file_id: str) -> bytes:
                return b""
            def register_command(self, cmd: Command) -> None: ...
            def register_handler(self, handler: MessageHandler) -> None: ...
            def register_conversation(self, conv: ConversationFlow) -> None: ...

        adapter = FullAdapter()
        assert isinstance(adapter, BotAdapter)
