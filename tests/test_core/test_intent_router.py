"""Tests for src/core/intent_router.py — IntentRouter with mocked LLM."""
from __future__ import annotations

import json

import pytest

from src.core.bot import Event, IntentDeclaration
from src.core.intent_router import IntentRouter

from tests.conftest import FakeLLMService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(text: str = "跑了5公里", user_id: int = 1, lang: str = "zh") -> Event:
    return Event(user_id=user_id, chat_id=100, text=text, lang=lang)


async def _handler_checkin(event: Event) -> str:
    return f"checkin:{event.text}"


async def _handler_add(event: Event) -> str:
    return f"add:{event.text}"


async def _handler_list(event: Event) -> str:
    return f"list:{event.text}"


async def _handler_del(event: Event) -> str:
    return f"del:{event.text}"


# Track recorder calls so tests can verify it's always invoked.
_recorder_calls: list[str] = []


async def _recorder(event: Event) -> str:
    _recorder_calls.append(event.text or "")
    return f"recorded:{event.text}"


async def _context_provider(user_id: int) -> str:
    return "Active plans:\n  - run: 每天跑步\n  - brush_teeth: 刷牙"


def _build_router(llm: FakeLLMService) -> IntentRouter:
    intents = [
        IntentDeclaration(
            name="planner_checkin",
            description="User checks in for a plan",
            examples=("跑了5公里", "学了1小时"),
            handler=_handler_checkin,
            args_description="The check-in content",
        ),
        IntentDeclaration(
            name="planner_add",
            description="User creates a new plan",
            examples=("我想每天跑步",),
            handler=_handler_add,
            args_description="The plan description",
        ),
        IntentDeclaration(
            name="planner_list",
            description="User views plans",
            examples=("看看我的计划",),
            handler=_handler_list,
            # No args_description → handler gets text=None
        ),
        IntentDeclaration(
            name="planner_del",
            description="User deletes a plan",
            examples=("删除跑步计划",),
            handler=_handler_del,
            args_description="The TAG of the plan to delete",
        ),
    ]
    return IntentRouter.create(
        llm=llm,
        recorder_handler=_recorder,
        plugin_intents=[(intents, _context_provider)],
    )


@pytest.fixture(autouse=True)
def _clear_recorder_calls():
    _recorder_calls.clear()


# ---------------------------------------------------------------------------
# Tests: Always-record behavior
# ---------------------------------------------------------------------------


class TestAlwaysRecords:
    @pytest.mark.asyncio
    async def test_recorder_called_even_when_intent_matched(self):
        llm = FakeLLMService(responses=[
            json.dumps([{"action": "planner_checkin", "confidence": 0.9, "args": "跑了5公里"}]),
        ])
        router = _build_router(llm)
        await router.handle(_make_event("跑了5公里"))
        assert "跑了5公里" in _recorder_calls

    @pytest.mark.asyncio
    async def test_recorder_called_when_no_intent_matched(self):
        llm = FakeLLMService(responses=[json.dumps([])])
        router = _build_router(llm)
        await router.handle(_make_event("今天天气不错"))
        assert "今天天气不错" in _recorder_calls

    @pytest.mark.asyncio
    async def test_recorder_called_on_empty_text(self):
        llm = FakeLLMService(responses=[])
        router = _build_router(llm)
        await router.handle(_make_event(""))
        assert "" in _recorder_calls


# ---------------------------------------------------------------------------
# Tests: Args extraction (function-call pattern)
# ---------------------------------------------------------------------------


class TestArgsExtraction:
    @pytest.mark.asyncio
    async def test_handler_receives_extracted_args(self):
        """Router extracts 'brush_teeth' tag from noisy message."""
        llm = FakeLLMService(responses=[
            json.dumps([{"action": "planner_del", "confidence": 0.9, "args": "brush_teeth"}]),
        ])
        router = _build_router(llm)
        result = await router.handle(_make_event("帮我删除刷牙的打卡任务吧，录入错了"))
        assert result == "del:brush_teeth"

    @pytest.mark.asyncio
    async def test_checkin_receives_clean_content(self):
        llm = FakeLLMService(responses=[
            json.dumps([{"action": "planner_checkin", "confidence": 0.85, "args": "跑了5公里，感觉不错"}]),
        ])
        router = _build_router(llm)
        result = await router.handle(_make_event("今天跑了5公里，感觉不错"))
        assert result == "checkin:跑了5公里，感觉不错"

    @pytest.mark.asyncio
    async def test_no_args_description_sends_none(self):
        """Actions without args_description receive text=None."""
        llm = FakeLLMService(responses=[
            json.dumps([{"action": "planner_list", "confidence": 0.9, "args": ""}]),
        ])
        router = _build_router(llm)
        result = await router.handle(_make_event("看看我的计划"))
        assert result == "list:None"

    @pytest.mark.asyncio
    async def test_empty_args_for_action_with_args_desc_sends_none(self):
        """If LLM returns empty args but action expects args, text=None."""
        llm = FakeLLMService(responses=[
            json.dumps([{"action": "planner_del", "confidence": 0.9, "args": ""}]),
        ])
        router = _build_router(llm)
        result = await router.handle(_make_event("删除计划"))
        assert result == "del:None"

    @pytest.mark.asyncio
    async def test_missing_args_key_sends_none(self):
        """If LLM omits args key entirely, text=None for actions with args_description."""
        llm = FakeLLMService(responses=[
            json.dumps([{"action": "planner_del", "confidence": 0.9}]),
        ])
        router = _build_router(llm)
        result = await router.handle(_make_event("删除计划"))
        assert result == "del:None"


# ---------------------------------------------------------------------------
# Tests: Dispatch
# ---------------------------------------------------------------------------


class TestIntentRouterDispatch:
    @pytest.mark.asyncio
    async def test_high_confidence_shows_plugin_result(self):
        llm = FakeLLMService(responses=[
            json.dumps([{"action": "planner_checkin", "confidence": 0.9, "args": "跑了5公里"}]),
        ])
        router = _build_router(llm)
        result = await router.handle(_make_event("跑了5公里"))
        assert result == "checkin:跑了5公里"

    @pytest.mark.asyncio
    async def test_low_confidence_shows_recorder_result_with_hint(self):
        llm = FakeLLMService(responses=[
            json.dumps([{"action": "planner_checkin", "confidence": 0.3, "args": ""}]),
        ])
        router = _build_router(llm)
        result = await router.handle(_make_event("今天天气不错"))
        assert "recorded:今天天气不错" in result
        assert "/help" in result

    @pytest.mark.asyncio
    async def test_empty_decisions_shows_recorder_with_hint(self):
        llm = FakeLLMService(responses=[json.dumps([])])
        router = _build_router(llm)
        result = await router.handle(_make_event("随便说说"))
        assert "recorded:随便说说" in result
        assert "/help" in result

    @pytest.mark.asyncio
    async def test_empty_text_no_hint(self):
        """Empty text goes straight to recorder without hint."""
        llm = FakeLLMService(responses=[])
        router = _build_router(llm)
        result = await router.handle(_make_event(""))
        assert result == "recorded:"

    @pytest.mark.asyncio
    async def test_whitespace_only_no_hint(self):
        llm = FakeLLMService(responses=[])
        router = _build_router(llm)
        result = await router.handle(_make_event("   "))
        assert result == "recorded:   "


# ---------------------------------------------------------------------------
# Tests: Multi-dispatch
# ---------------------------------------------------------------------------


class TestMultiDispatch:
    @pytest.mark.asyncio
    async def test_multiple_high_confidence_actions(self):
        llm = FakeLLMService(responses=[
            json.dumps([
                {"action": "planner_checkin", "confidence": 0.9, "args": "跑了5公里"},
                {"action": "planner_add", "confidence": 0.8, "args": "以后每天跑"},
            ]),
        ])
        router = _build_router(llm)
        result = await router.handle(_make_event("跑了5公里，以后每天跑"))
        assert "checkin:跑了5公里" in result
        assert "add:以后每天跑" in result
        assert "---" in result

    @pytest.mark.asyncio
    async def test_mixed_confidence_only_dispatches_high(self):
        llm = FakeLLMService(responses=[
            json.dumps([
                {"action": "planner_checkin", "confidence": 0.85, "args": "跑了5公里"},
                {"action": "planner_add", "confidence": 0.4, "args": ""},
            ]),
        ])
        router = _build_router(llm)
        result = await router.handle(_make_event("跑了5公里"))
        assert result == "checkin:跑了5公里"


# ---------------------------------------------------------------------------
# Tests: Unknown action
# ---------------------------------------------------------------------------


class TestUnknownAction:
    @pytest.mark.asyncio
    async def test_unknown_action_shows_recorder_with_hint(self):
        llm = FakeLLMService(responses=[
            json.dumps([{"action": "nonexistent", "confidence": 0.99, "args": ""}]),
        ])
        router = _build_router(llm)
        result = await router.handle(_make_event("???"))
        assert "recorded:???" in result
        assert "/help" in result


# ---------------------------------------------------------------------------
# Tests: Context gathering
# ---------------------------------------------------------------------------


class TestContextGathering:
    @pytest.mark.asyncio
    async def test_context_provider_called(self):
        calls: list[int] = []

        async def tracking_provider(user_id: int) -> str:
            calls.append(user_id)
            return "plans here"

        llm = FakeLLMService(responses=[json.dumps([])])
        router = IntentRouter.create(
            llm=llm,
            recorder_handler=_recorder,
            plugin_intents=[(
                [IntentDeclaration(
                    name="test", description="test", examples=("x",),
                    handler=_handler_checkin,
                    args_description="test args",
                )],
                tracking_provider,
            )],
        )
        await router.handle(_make_event("hello", user_id=42))
        assert calls == [42]

    @pytest.mark.asyncio
    async def test_context_provider_failure_does_not_crash(self):
        async def broken_provider(user_id: int) -> str:
            raise RuntimeError("db down")

        llm = FakeLLMService(responses=[json.dumps([])])
        router = IntentRouter.create(
            llm=llm,
            recorder_handler=_recorder,
            plugin_intents=[(
                [IntentDeclaration(
                    name="test", description="test", examples=("x",),
                    handler=_handler_checkin,
                    args_description="test args",
                )],
                broken_provider,
            )],
        )
        result = await router.handle(_make_event("hello"))
        assert "recorded:hello" in result


# ---------------------------------------------------------------------------
# Tests: Handler failure
# ---------------------------------------------------------------------------


class TestHandlerFailure:
    @pytest.mark.asyncio
    async def test_handler_error_surfaces_error_note(self):
        async def broken_handler(event: Event) -> str:
            raise RuntimeError("handler crashed")

        llm = FakeLLMService(responses=[
            json.dumps([{"action": "broken", "confidence": 0.95, "args": "x"}]),
        ])
        router = IntentRouter.create(
            llm=llm,
            recorder_handler=_recorder,
            plugin_intents=[(
                [IntentDeclaration(
                    name="broken", description="breaks", examples=("x",),
                    handler=broken_handler,
                    args_description="irrelevant",
                )],
                _context_provider,
            )],
        )
        result = await router.handle(_make_event("trigger"))
        assert "broken" in result
        assert "error" in result


# ---------------------------------------------------------------------------
# Tests: No intents registered
# ---------------------------------------------------------------------------


class TestNoIntentsRegistered:
    @pytest.mark.asyncio
    async def test_no_intents_goes_to_recorder_without_hint(self):
        """When no intents are registered at all, no hint is shown."""
        llm = FakeLLMService(responses=[])
        router = IntentRouter.create(
            llm=llm,
            recorder_handler=_recorder,
            plugin_intents=[],
        )
        result = await router.handle(_make_event("hello"))
        assert result == "recorded:hello"
