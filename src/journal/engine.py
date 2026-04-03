"""Journal engine — manages multi-turn 曾国藩式 reflection sessions."""
from __future__ import annotations

import logging

from ..llm.client import LLMClient
from ..storage.db import Database
from ..storage.models import CATEGORY_LABELS, JournalCategory

logger = logging.getLogger(__name__)

JOURNAL_FLOW = [
    JournalCategory.MORNING,
    JournalCategory.READING,
    JournalCategory.SOCIAL,
    JournalCategory.REFLECTION,
]

SKIP_KEYWORDS = {"跳过", "skip", "无", "没有", "pass"}

CATEGORY_PROMPTS = {
    JournalCategory.MORNING: "引导用户回顾今天的晨起情况：几点起床？精神状态如何？有没有按时起床？",
    JournalCategory.READING: "引导用户回顾今天的所阅所学：读了什么文章/书？看了什么视频？听了什么播客？有什么收获？",
    JournalCategory.SOCIAL: "引导用户回顾今天的待人接物：和谁有印象深刻的交流？有没有帮助到别人？",
    JournalCategory.REFLECTION: "引导用户做今日反省：今天有什么做得不够好的？有什么遗憾？明天打算如何改进？",
}


class JournalEngine:
    """Drives a single journal session through all four categories."""

    def __init__(
        self,
        db: Database,
        llm: LLMClient,
        user_id: int,
        date: str,
        today_messages: list[str] | None = None,
    ) -> None:
        self._db = db
        self._llm = llm
        self._user_id = user_id
        self._date = date
        self._today_messages = today_messages or []
        self._step = 0
        self._conversation: list[dict[str, str]] = []

    @property
    def current_category(self) -> JournalCategory | None:
        if self._step < len(JOURNAL_FLOW):
            return JOURNAL_FLOW[self._step]
        return None

    @property
    def is_complete(self) -> bool:
        return self._step >= len(JOURNAL_FLOW)

    async def start(self) -> str:
        category = self.current_category
        if category is None:
            return "今日反思已完成。"
        system_msg = self._build_system_prompt()
        user_msg = f"请开始「{CATEGORY_LABELS[category]}」部分的引导。"
        self._conversation = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]
        response = await self._llm.chat(messages=self._conversation)
        self._conversation.append({"role": "assistant", "content": response})
        return response

    async def answer(self, text: str) -> str:
        category = self.current_category
        if category is None:
            return "今日反思已完成。"
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
        label = CATEGORY_LABELS[category]
        self._conversation.append(
            {"role": "user", "content": f"继续，请引导「{label}」部分。"}
        )
        response = await self._llm.chat(messages=self._conversation[-6:])
        self._conversation.append({"role": "assistant", "content": response})
        return response

    async def _generate_closing(self) -> str:
        entries = await self._db.get_journal_entries(self._user_id, self._date)
        if not entries:
            return "今天的反思结束了。明天继续加油！"
        entry_text = "\n".join(
            f"[{CATEGORY_LABELS.get(e.category, '')}] {e.content[:150]}"
            for e in entries
        )
        response = await self._llm.chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是 DailyClaw。用户刚完成今日四省反思。"
                        "请用 2-3 句温暖的话总结今天，给出一句鼓励。用中文，简洁。"
                    ),
                },
                {"role": "user", "content": f"今日反思内容：\n{entry_text}"},
            ],
            max_tokens=300,
        )
        return response

    def _build_system_prompt(self) -> str:
        context = ""
        if self._today_messages:
            msgs = self._today_messages[-10:]
            context = "\n用户今天发过的消息（供参考）：\n" + "\n".join(
                f"- {m[:100]}" for m in msgs
            )
        return (
            "你是 DailyClaw，用户的每日反思助手。\n"
            "你正在引导用户完成曾国藩式每日四省。\n"
            "每次只引导一个部分，用 1-2 个简短问题，语气温暖但不啰嗦。\n"
            "用中文回复。"
            f"{context}"
        )
