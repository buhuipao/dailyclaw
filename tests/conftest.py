"""Shared pytest fixtures for DailyClaw tests."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import time
from typing import Any

import pytest
import pytest_asyncio

from src.core.bot import BotAdapter, Command, Event, MessageHandler, MessageRef, ConversationFlow
from src.core.db import Database
from src.core.llm import Capability
from src.core.scheduler import Scheduler


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db(tmp_path):
    """Provide an in-memory Database instance with schema initialized."""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path=db_path)
    await database.connect()
    yield database
    await database.close()


class FakeLLMService:
    """Deterministic LLM stub for testing. Implements the LLMService interface."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or [])
        self._call_index = 0
        self.calls: list[list[dict[str, str]]] = []
        self.image_calls: list[dict] = []

    def supports(self, capability: Capability) -> bool:
        return True

    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        lang: str = "en",
    ) -> str:
        self.calls.append(messages)
        if self._call_index < len(self._responses):
            resp = self._responses[self._call_index]
            self._call_index += 1
            return resp
        return "default LLM response"

    async def analyze_image(self, image_bytes: bytes, prompt: str = "", lang: str = "en") -> str:
        self.image_calls.append({"image_bytes": image_bytes, "prompt": prompt})
        if self._call_index < len(self._responses):
            resp = self._responses[self._call_index]
            self._call_index += 1
            return resp
        return "default vision response"

    async def classify(self, text: str, lang: str = "en") -> dict[str, str]:
        return {"category": "other", "summary": text[:50], "tags": ""}

    async def summarize_text(self, text: str, url: str = "", lang: str = "en") -> str:
        return "default summary"

    async def parse_plan(self, text: str, lang: str = "en") -> dict[str, str]:
        return {"tag": "test", "name": text[:20], "schedule": "daily", "remind_time": "20:00"}

    async def match_checkin(self, text: str, plans: list[dict[str, str]], lang: str = "en") -> dict[str, str]:
        tag = plans[0]["tag"] if plans else ""
        return {"tag": tag, "note": text, "duration_minutes": 0}


class FakeBotAdapter(BotAdapter):
    """Deterministic BotAdapter stub for testing."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.edits: list[dict] = []
        self.replies: list[dict] = []
        self.downloaded: dict[str, bytes] = {}
        self._commands: list[Command] = []
        self._handlers: list[MessageHandler] = []
        self._conversations: list[ConversationFlow] = []
        self._message_counter = 0

    def _next_message_id(self) -> int:
        self._message_counter += 1
        return self._message_counter

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def send_message(self, chat_id: int, text: str) -> MessageRef:
        ref = MessageRef(chat_id=chat_id, message_id=self._next_message_id())
        self.sent.append({"chat_id": chat_id, "text": text, "ref": ref})
        return ref

    async def edit_message(self, chat_id: int, message_id: int, text: str) -> None:
        self.edits.append({"chat_id": chat_id, "message_id": message_id, "text": text})

    async def reply(self, event: Event, text: str) -> MessageRef:
        ref = MessageRef(chat_id=event.chat_id, message_id=self._next_message_id())
        self.replies.append({"event": event, "text": text, "ref": ref})
        return ref

    async def download_file(self, file_id: str) -> bytes:
        return self.downloaded.get(file_id, b"fake-file-bytes")

    def register_command(self, cmd: Command) -> None:
        self._commands.append(cmd)

    def register_handler(self, handler: MessageHandler) -> None:
        self._handlers.append(handler)

    def register_conversation(self, conv: ConversationFlow) -> None:
        self._conversations.append(conv)


class FakeScheduler(Scheduler):
    """Deterministic Scheduler stub for testing. Stores jobs in a dict."""

    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}

    async def run_daily(
        self,
        callback: Callable,
        time: time,
        name: str,
        *,
        days: tuple[int, ...] | None = None,
        data: Any = None,
    ) -> None:
        self.jobs[name] = {
            "type": "daily",
            "callback": callback,
            "time": time,
            "days": days,
            "data": data,
        }

    async def run_repeating(
        self,
        callback: Callable,
        interval: float,
        name: str,
        *,
        first: float = 0,
    ) -> None:
        self.jobs[name] = {
            "type": "repeating",
            "callback": callback,
            "interval": interval,
            "first": first,
        }

    async def cancel(self, name: str) -> None:
        self.jobs.pop(name, None)


@pytest.fixture
def fake_llm():
    """Provide a FakeLLMService factory."""
    def _factory(responses: list[str] | None = None) -> FakeLLMService:
        return FakeLLMService(responses)
    return _factory


@pytest.fixture
def fake_bot():
    """Provide a FakeBotAdapter instance."""
    return FakeBotAdapter()


@pytest.fixture
def fake_scheduler():
    """Provide a FakeScheduler instance."""
    return FakeScheduler()
