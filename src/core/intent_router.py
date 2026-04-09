"""Context-aware intent router — routes natural language to plugin handlers via LLM.

Every text message is ALWAYS recorded by the Recorder.  In parallel the router
asks the LLM whether a plugin action should also fire.  If yes the user sees the
plugin result; if no the user sees the Recorder result plus a gentle hint.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from src.core.bot import Event, IntentDeclaration
from src.core.i18n import t
import src.core.intent_router_locale  # noqa: F401  # register translations

logger = logging.getLogger(__name__)

# Confidence threshold: >= 0.7 dispatches without user confirmation.
CONFIDENCE_AUTO = 0.7

_MAX_EXAMPLES_IN_PROMPT = 3


class _RoutingLLM(Protocol):
    """Minimal interface the router needs from the LLM layer."""

    async def route_intent(
        self,
        text: str,
        intent_descriptions: list[dict[str, str]],
        user_context: str,
        lang: str = ...,
    ) -> list[dict]: ...


@dataclass(frozen=True)
class _RegisteredPlugin:
    intents: tuple[IntentDeclaration, ...]
    context_provider: Callable[[int], Awaitable[str]]


class IntentRouter:
    """Routes non-command text messages to plugin handlers via LLM intent classification.

    Fully initialised via the ``create`` factory; no mutation after construction.

    Flow:
      1. Record the message (Recorder) AND route intents (LLM) **in parallel**
      2. If a high-confidence (>= 0.7) intent matched → show plugin result
      3. Otherwise → show Recorder result + hint about commands
    """

    def __init__(
        self,
        llm: _RoutingLLM,
        recorder_handler: Callable[[Event], Awaitable[str | None]],
        plugins: tuple[_RegisteredPlugin, ...],
        intent_map: dict[str, IntentDeclaration],
    ) -> None:
        self._llm = llm
        self._recorder = recorder_handler
        self._plugins = plugins
        self._intent_map = intent_map

    @classmethod
    def create(
        cls,
        llm: _RoutingLLM,
        recorder_handler: Callable[[Event], Awaitable[str | None]],
        plugin_intents: list[tuple[list[IntentDeclaration], Callable[[int], Awaitable[str]]]],
    ) -> IntentRouter:
        """Build an immutable IntentRouter from a list of (intents, context_provider) pairs."""
        plugins: list[_RegisteredPlugin] = []
        intent_map: dict[str, IntentDeclaration] = {}
        for intents, ctx_provider in plugin_intents:
            plugins.append(_RegisteredPlugin(
                intents=tuple(intents),
                context_provider=ctx_provider,
            ))
            for intent in intents:
                intent_map[intent.name] = intent
        return cls(
            llm=llm,
            recorder_handler=recorder_handler,
            plugins=tuple(plugins),
            intent_map=dict(intent_map),  # defensive copy
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def handle(self, event: Event) -> str | None:
        """Registered as the TEXT MessageHandler.

        Always records via Recorder.  Runs intent routing in parallel.
        """
        text = (event.text or "").strip()

        # No text or no intents configured → just record.
        if not text or not self._intent_map:
            return await self._recorder(event)

        # Run Recorder and intent routing in parallel.
        recorder_result, plugin_result = await asyncio.gather(
            self._recorder(event),
            self._route_to_plugins(event, text),
        )

        if plugin_result is not None:
            return plugin_result

        # No intent matched → show Recorder result + hint.
        hint = t("intent_router.fallback_hint", event.lang)
        if recorder_result:
            return f"{recorder_result}\n\n{hint}"
        return hint

    # ------------------------------------------------------------------
    # Intent routing (runs in parallel with Recorder)
    # ------------------------------------------------------------------

    async def _route_to_plugins(self, event: Event, text: str) -> str | None:
        """Return plugin handler result(s) or None if nothing matched."""
        # 1. Gather user context from all plugins
        user_context = await self._gather_context(event.user_id)

        # 2. Build intent descriptions for LLM (including args schema)
        intent_descs: list[dict[str, str]] = []
        for intent in self._intent_map.values():
            desc: dict[str, str] = {
                "name": intent.name,
                "description": intent.description,
                "examples": ", ".join(
                    f'"{e}"' for e in intent.examples[:_MAX_EXAMPLES_IN_PROMPT]
                ),
            }
            if intent.args_description:
                desc["args"] = intent.args_description
            intent_descs.append(desc)

        # 3. LLM routing
        decisions = await self._llm.route_intent(
            text=text,
            intent_descriptions=intent_descs,
            user_context=user_context,
            lang=event.lang,
        )
        logger.info(
            "[IntentRouter] user=%d text=%.40s decisions=%s",
            event.user_id, text, decisions,
        )

        # 4. Filter by confidence
        matched = [
            d for d in decisions
            if d.get("confidence", 0) >= CONFIDENCE_AUTO
        ]

        if not matched:
            logger.debug("[IntentRouter] no match >= %.1f", CONFIDENCE_AUTO)
            return None

        # 5. Multi-dispatch: run all matched handlers with extracted args.
        results: list[str] = []
        for decision in matched:
            intent = self._intent_map.get(decision["action"])
            if intent is None:
                logger.warning("[IntentRouter] unknown action: %s", decision["action"])
                continue

            extracted_args = decision.get("args", "")
            dispatch_event = self._make_dispatch_event(event, intent, extracted_args)
            try:
                result = await intent.handler(dispatch_event)
                if result:
                    results.append(result)
            except Exception:
                logger.error(
                    "[IntentRouter] handler %s failed", intent.name, exc_info=True,
                )
                results.append(f"⚠️ {intent.name}: internal error")

        return "\n\n---\n\n".join(results) if results else None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _gather_context(self, user_id: int) -> str:
        parts: list[str] = []
        for plugin in self._plugins:
            try:
                ctx_str = await plugin.context_provider(user_id)
                if ctx_str:
                    parts.append(ctx_str)
            except Exception:
                logger.warning("Context provider failed for user=%d", user_id, exc_info=True)
        return "\n".join(parts) if parts else "No active plans or sessions."

    @staticmethod
    def _make_dispatch_event(
        event: Event, intent: IntentDeclaration, extracted_args: str,
    ) -> Event:
        """Build an Event for the handler with LLM-extracted args as text.

        The handler receives ``event.text`` = extracted args, mimicking how
        commands work (``/planner_del 刷牙`` → text="刷牙").
        If no args_description is declared, text is None (no args expected).
        """
        args_text = extracted_args.strip() if extracted_args else None
        if intent.args_description is None:
            # Action takes no arguments.
            args_text = None

        return Event(
            user_id=event.user_id,
            chat_id=event.chat_id,
            text=args_text or None,
            photo_file_id=event.photo_file_id,
            voice_file_id=event.voice_file_id,
            video_file_id=event.video_file_id,
            caption=event.caption,
            is_admin=event.is_admin,
            lang=event.lang,
            raw=event.raw,
        )
