"""Tests for src/core/llm.py — no real API calls."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.core.llm import (
    Capability,
    CapabilityNotConfigured,
    LLMProvider,
    LLMService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_provider(
    capability: Capability = Capability.TEXT,
    *,
    base_url: str = "https://api.example.com/v1",
    api_key: str = "test-key",
    model: str = "test-model",
) -> LLMProvider:
    return LLMProvider(
        capability=capability,
        base_url=base_url,
        api_key=api_key,
        model=model,
    )


def make_chunk(content: str) -> MagicMock:
    """Build a fake streaming chunk with the given content."""
    chunk = MagicMock()
    delta = MagicMock()
    delta.content = content
    choice = MagicMock()
    choice.delta = delta
    chunk.choices = [choice]
    return chunk


async def fake_stream(chunks: list[str]):
    """Async generator that yields fake stream chunks."""
    for text in chunks:
        yield make_chunk(text)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestCapabilityEnum:
    def test_values(self):
        assert Capability.TEXT == "text"
        assert Capability.VISION == "vision"
        assert Capability.AUDIO == "audio"
        assert Capability.VIDEO == "video"


class TestLLMProviderDefaults:
    def test_defaults(self):
        p = make_provider()
        assert p.max_tokens == 2000
        assert p.temperature == 0.7
        assert p.timeout == 60.0

    def test_frozen(self):
        p = make_provider()
        with pytest.raises((AttributeError, TypeError)):
            p.model = "other"  # type: ignore[misc]


class TestSupports:
    def test_returns_true_for_configured_capability(self):
        svc = LLMService({Capability.TEXT: make_provider(Capability.TEXT)})
        assert svc.supports(Capability.TEXT) is True

    def test_returns_false_for_unconfigured_capability(self):
        svc = LLMService({Capability.TEXT: make_provider(Capability.TEXT)})
        assert svc.supports(Capability.VISION) is False

    def test_multiple_providers(self):
        svc = LLMService(
            {
                Capability.TEXT: make_provider(Capability.TEXT),
                Capability.VISION: make_provider(Capability.VISION),
            }
        )
        assert svc.supports(Capability.TEXT) is True
        assert svc.supports(Capability.VISION) is True
        assert svc.supports(Capability.AUDIO) is False
        assert svc.supports(Capability.VIDEO) is False


class TestChatCapabilityNotConfigured:
    @pytest.mark.asyncio
    async def test_raises_when_text_not_configured(self):
        svc = LLMService({Capability.VISION: make_provider(Capability.VISION)})
        with pytest.raises(CapabilityNotConfigured):
            await svc.chat([{"role": "user", "content": "hi"}])


class TestAnalyzeImageCapabilityNotConfigured:
    @pytest.mark.asyncio
    async def test_raises_when_vision_not_configured(self):
        svc = LLMService({Capability.TEXT: make_provider(Capability.TEXT)})
        with pytest.raises(CapabilityNotConfigured):
            await svc.analyze_image(b"fakeimage")


class TestChatStreaming:
    @pytest.mark.asyncio
    async def test_chat_assembles_streamed_chunks(self):
        provider = make_provider(Capability.TEXT)
        svc = LLMService({Capability.TEXT: provider})

        # Patch the internal AsyncOpenAI client's create method
        mock_create = AsyncMock(return_value=fake_stream(["Hello", ", ", "world!"]))
        svc._clients[Capability.TEXT].chat.completions.create = mock_create

        result = await svc.chat([{"role": "user", "content": "hi"}])

        assert result == "Hello, world!"
        mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_injects_safety_suffix_into_system_prompt(self):
        provider = make_provider(Capability.TEXT)
        svc = LLMService({Capability.TEXT: provider})

        mock_create = AsyncMock(return_value=fake_stream(["ok"]))
        svc._clients[Capability.TEXT].chat.completions.create = mock_create

        await svc.chat(
            [
                {"role": "system", "content": "You are a helper."},
                {"role": "user", "content": "hello"},
            ]
        )

        call_kwargs = mock_create.call_args
        messages_sent = call_kwargs.kwargs["messages"]
        system_msg = next(m for m in messages_sent if m["role"] == "system")
        assert "安全规则" in system_msg["content"]
        assert system_msg["content"].startswith("You are a helper.")

    @pytest.mark.asyncio
    async def test_chat_uses_provider_defaults_when_no_overrides(self):
        provider = LLMProvider(
            capability=Capability.TEXT,
            base_url="https://api.example.com/v1",
            api_key="key",
            model="gpt-test",
            temperature=0.5,
            max_tokens=500,
        )
        svc = LLMService({Capability.TEXT: provider})

        mock_create = AsyncMock(return_value=fake_stream(["resp"]))
        svc._clients[Capability.TEXT].chat.completions.create = mock_create

        await svc.chat([{"role": "user", "content": "test"}])

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.5
        assert call_kwargs["max_tokens"] == 500

    @pytest.mark.asyncio
    async def test_chat_override_temperature_and_max_tokens(self):
        provider = make_provider(Capability.TEXT)
        svc = LLMService({Capability.TEXT: provider})

        mock_create = AsyncMock(return_value=fake_stream(["resp"]))
        svc._clients[Capability.TEXT].chat.completions.create = mock_create

        await svc.chat(
            [{"role": "user", "content": "test"}],
            temperature=0.1,
            max_tokens=100,
        )

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["max_tokens"] == 100


class TestNotImplemented:
    @pytest.mark.asyncio
    async def test_transcribe_audio_raises(self):
        svc = LLMService({Capability.AUDIO: make_provider(Capability.AUDIO)})
        with pytest.raises(NotImplementedError):
            await svc.transcribe_audio(b"audio")

    @pytest.mark.asyncio
    async def test_analyze_video_raises(self):
        svc = LLMService({Capability.VIDEO: make_provider(Capability.VIDEO)})
        with pytest.raises(NotImplementedError):
            await svc.analyze_video(b"video")
