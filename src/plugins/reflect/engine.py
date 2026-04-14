"""Journal engine — manages multi-turn 曾国藩式 reflection sessions."""
from __future__ import annotations

import logging

from src.core.i18n import t
from src.core.i18n.shared import category_label

import src.plugins.reflect.locale  # noqa: F401

logger = logging.getLogger(__name__)

JOURNAL_FLOW = ["morning", "reading", "social", "reflection"]

SKIP_KEYWORDS = {"跳过", "skip", "无", "没有", "pass"}


class JournalEngine:
    """Drives a single journal session through all four categories."""

    def __init__(
        self,
        db: object,
        llm: object,
        user_id: int,
        date: str,
        today_messages: list[str] | None = None,
        lang: str = "zh",
    ) -> None:
        self._db = db
        self._llm = llm
        self._user_id = user_id
        self._date = date
        self._today_messages = today_messages or []
        self._lang = lang
        self._step = 0
        self._conversation: list[dict[str, str]] = []

    @property
    def current_category(self) -> str | None:
        if self._step < len(JOURNAL_FLOW):
            return JOURNAL_FLOW[self._step]
        return None

    @property
    def is_complete(self) -> bool:
        return self._step >= len(JOURNAL_FLOW)

    async def start(self) -> str:
        category = self.current_category
        if category is None:
            return t("reflect.flow_complete", self._lang)
        system_msg = self._build_system_prompt()
        label = category_label(category, self._lang)
        user_msg = t("reflect.start_section", self._lang, label=label)
        self._conversation = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]
        response = await self._llm.chat(messages=self._conversation, lang=self._lang)
        self._conversation.append({"role": "assistant", "content": response})
        step_header = t(
            "reflect.step_indicator", self._lang,
            step=self._step + 1, total=len(JOURNAL_FLOW), label=label,
        )
        return step_header + response

    async def answer(self, text: str) -> str:
        category = self.current_category
        if category is None:
            return t("reflect.flow_complete", self._lang)
        if text.strip().lower() in SKIP_KEYWORDS:
            self._step += 1
            return await self._next_or_finish()
        await self._db.save_journal_entry(
            user_id=self._user_id,
            date=self._date,
            category=category,
            content=text,
        )
        self._step += 1
        return await self._next_or_finish()

    async def _next_or_finish(self) -> str:
        if self.is_complete:
            return await self._generate_closing()
        category = self.current_category
        label = category_label(category, self._lang)  # type: ignore[arg-type]
        self._conversation.append(
            {"role": "user", "content": t("reflect.continue_section", self._lang, label=label)}
        )
        response = await self._llm.chat(messages=self._conversation[-6:], lang=self._lang)
        self._conversation.append({"role": "assistant", "content": response})
        step_header = t(
            "reflect.step_indicator", self._lang,
            step=self._step + 1, total=len(JOURNAL_FLOW), label=label,
        )
        return step_header + response

    async def _generate_closing(self) -> str:
        entries = await self._db.get_journal_entries(self._user_id, self._date)
        if not entries:
            return t("reflect.closing_fallback", self._lang)
        entry_text = "\n".join(
            f"[{category_label(e['category'], self._lang)}] {e['content'][:150]}"
            for e in entries
        )
        response = await self._llm.chat(
            messages=[
                {
                    "role": "system",
                    "content": t("reflect.closing_system_prompt", self._lang),
                },
                {"role": "user", "content": entry_text},
            ],
            max_tokens=300,
            lang=self._lang,
        )
        header = t("reflect.closing_header", self._lang)
        footer = t("reflect.closing_footer", self._lang)
        return header + response + footer

    def _build_system_prompt(self) -> str:
        context = ""
        if self._today_messages:
            msgs = self._today_messages[-10:]
            context = t("reflect.context_prefix", self._lang) + "\n".join(
                f"- {m[:100]}" for m in msgs
            )
        return t("reflect.system_prompt", self._lang) + context
