"""Tests for vision analysis via FakeLLMService."""
from __future__ import annotations

import base64

import pytest

from tests.conftest import FakeLLMService


@pytest.mark.asyncio
async def test_analyze_image_returns_response():
    """analyze_image returns the canned response."""
    client = FakeLLMService(responses=["这是一张猫的照片，毛色为橘色。"])
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )
    result = await client.analyze_image(image_bytes, prompt="我的猫")
    assert "猫" in result
    assert len(client.image_calls) == 1
    assert client.image_calls[0]["image_bytes"] == image_bytes
    assert client.image_calls[0]["prompt"] == "我的猫"


@pytest.mark.asyncio
async def test_analyze_image_records_prompt():
    """analyze_image records the prompt in call args."""
    client = FakeLLMService(responses=["照片分析结果"])
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )
    result = await client.analyze_image(image_bytes, prompt="今天的午餐")
    assert result == "照片分析结果"
    assert client.image_calls[0]["prompt"] == "今天的午餐"


@pytest.mark.asyncio
async def test_analyze_image_works_without_prompt():
    """analyze_image works when no prompt is provided."""
    client = FakeLLMService(responses=["一张风景照片"])
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )
    result = await client.analyze_image(image_bytes)
    assert result == "一张风景照片"
    assert client.image_calls[0]["prompt"] == ""
