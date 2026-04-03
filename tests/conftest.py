"""Shared pytest fixtures for DailyClaw tests."""
from __future__ import annotations

import asyncio
import os
import tempfile

import pytest
import pytest_asyncio

from src.storage.db import Database


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


class FakeLLM:
    """Deterministic LLM stub for testing."""

    def __init__(self, responses: list[str] | None = None):
        self._responses = list(responses or [])
        self._call_index = 0
        self.calls: list[list[dict[str, str]]] = []

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        self.calls.append(messages)
        if self._call_index < len(self._responses):
            resp = self._responses[self._call_index]
            self._call_index += 1
            return resp
        return "default LLM response"

    async def classify(self, text: str) -> dict[str, str]:
        return {"category": "other", "summary": text[:50], "tags": ""}


@pytest.fixture
def fake_llm():
    """Provide a FakeLLM factory."""
    def _factory(responses: list[str] | None = None) -> FakeLLM:
        return FakeLLM(responses)
    return _factory
