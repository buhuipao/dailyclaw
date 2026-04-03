"""OpenAI-compatible LLM client for DailyClaw."""
from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    """Thin wrapper around OpenAI-compatible API."""

    def __init__(self, base_url: str, api_key: str, model: str):
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self._model = model

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Send a chat completion request and return the response text."""
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    async def classify(self, text: str) -> dict[str, str]:
        """Classify a user message into category and extract key info.

        Returns dict with keys: category (morning/reading/social/reflection/idea/other),
        summary (one-line summary), tags (comma-separated).
        """
        system_prompt = """你是 DailyClaw 的消息分类助手。用户会发送各种消息，你需要分类并提取信息。

返回严格的 JSON 格式（不要 markdown 包裹）：
{
  "category": "morning|reading|social|reflection|idea|other",
  "summary": "一句话概括",
  "tags": "tag1,tag2"
}

分类说明：
- morning: 早起、作息、早晨状态相关
- reading: 阅读文章、书籍、视频、播客等内容的记录或感悟
- social: 与人交流、社交、待人接物相关
- reflection: 反省、自省、改进想法
- idea: 灵感、想法、创意
- other: 其他日常记录"""

        # Truncate input to prevent excessive token usage
        truncated = text[:500]

        response = await self.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": truncated},
            ],
            temperature=0.3,
            max_tokens=200,
        )

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.warning("LLM classify returned non-JSON: %r", response[:200])
            return {"category": "other", "summary": text[:50], "tags": ""}
