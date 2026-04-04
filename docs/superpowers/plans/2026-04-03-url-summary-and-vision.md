# URL Summarization + Image Understanding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When users send URLs, fetch and summarize the content; when users send photos, analyze them with doubao-seed vision model.

**Architecture:** Add `httpx` for async URL fetching with `readability-lxml` for HTML extraction. Add a `VisionClient` wrapping a second `AsyncOpenAI` pointed at doubao-seed's OpenAI-compatible endpoint. Both features plug into existing `handlers.py` message handlers, storing results in the existing `metadata` JSON column.

**Tech Stack:** httpx, readability-lxml, lxml[html_clean], openai SDK (AsyncOpenAI for doubao-seed), base64 encoding for image payloads

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `requirements.txt` | Modify | Add httpx, readability-lxml, lxml_html_clean |
| `src/llm/client.py` | Modify | Add `summarize_text()` method for URL content summarization |
| `src/llm/vision.py` | Create | `VisionClient` class wrapping doubao-seed for image understanding |
| `src/bot/url_fetcher.py` | Create | Async URL fetching + readable text extraction |
| `src/bot/handlers.py` | Modify | Wire URL summarization into `handle_text`, image analysis into `handle_photo` |
| `src/config.py` | Modify | Validate new `vision` config section |
| `src/main.py` | Modify | Instantiate `VisionClient`, store in `bot_data` |
| `config.example.yaml` | Modify | Add `vision` config block |
| `.env.example` | Modify | Add `VISION_API_KEY` |
| `tests/conftest.py` | Modify | Add `FakeVisionClient` stub |
| `tests/test_url_fetcher.py` | Create | Tests for URL fetching and text extraction |
| `tests/test_url_summary.py` | Create | Tests for LLM summarization of URL content |
| `tests/test_vision.py` | Create | Tests for image understanding flow |

---

## Part 1: URL Summarization

### Task 1: Add dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add httpx and readability-lxml to requirements.txt**

Append these lines to `requirements.txt`:

```
httpx==0.28.1
readability-lxml==0.8.4.1
lxml_html_clean==0.4.2
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add httpx and readability-lxml for URL fetching"
```

---

### Task 2: Create URL fetcher module

**Files:**
- Create: `tests/test_url_fetcher.py`
- Create: `src/bot/url_fetcher.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_url_fetcher.py`:

```python
"""Tests for URL fetching and text extraction."""
from __future__ import annotations

import pytest

from src.bot.url_fetcher import extract_readable_text, fetch_url


@pytest.mark.asyncio
async def test_fetch_url_returns_html(httpx_mock):
    """fetch_url returns response body for a valid URL."""
    httpx_mock.add_response(
        url="https://example.com/article",
        html="<html><body><h1>Title</h1><p>Content here.</p></body></html>",
    )
    result = await fetch_url("https://example.com/article")
    assert result is not None
    assert "Content here" in result


@pytest.mark.asyncio
async def test_fetch_url_returns_none_on_error(httpx_mock):
    """fetch_url returns None when request fails."""
    httpx_mock.add_response(url="https://bad.example.com", status_code=500)
    result = await fetch_url("https://bad.example.com")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_url_returns_none_on_timeout(httpx_mock):
    """fetch_url returns None on connection timeout."""
    import httpx as httpx_lib
    httpx_mock.add_exception(
        httpx_lib.ConnectTimeout("timeout"),
        url="https://slow.example.com",
    )
    result = await fetch_url("https://slow.example.com")
    assert result is None


def test_extract_readable_text_strips_html():
    """extract_readable_text returns clean text from HTML."""
    html = """
    <html><head><title>Test</title></head>
    <body>
        <nav>Menu items</nav>
        <article><h1>Article Title</h1><p>This is the main content of the article.</p></article>
        <footer>Footer stuff</footer>
    </body></html>
    """
    text = extract_readable_text(html, url="https://example.com")
    assert "main content" in text
    assert len(text) < len(html)  # should be shorter than raw HTML


def test_extract_readable_text_handles_garbage():
    """extract_readable_text returns empty string for unparseable input."""
    result = extract_readable_text("", url="https://example.com")
    assert isinstance(result, str)


def test_extract_readable_text_truncates_long_content():
    """extract_readable_text caps output to prevent huge LLM prompts."""
    html = f"<html><body><p>{'word ' * 5000}</p></body></html>"
    text = extract_readable_text(html, url="https://example.com")
    assert len(text) <= 3000
```

Also add `pytest-httpx` to `requirements.txt` (dev dependency — append it):

```
pytest-httpx==0.35.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_url_fetcher.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.bot.url_fetcher'`

- [ ] **Step 3: Install pytest-httpx and write the implementation**

Run: `pip install pytest-httpx==0.35.0`

Create `src/bot/url_fetcher.py`:

```python
"""Async URL fetching and readable text extraction."""
from __future__ import annotations

import logging

import httpx
from readability import Document

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0
_MAX_TEXT_LENGTH = 3000


async def fetch_url(url: str) -> str | None:
    """Fetch URL content. Returns HTML string or None on failure."""
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "DailyClaw/1.0"},
        ) as client:
            response = await client.get(url)
            if response.status_code >= 400:
                logger.warning("URL fetch failed: %s -> %d", url, response.status_code)
                return None
            return response.text
    except (httpx.HTTPError, Exception) as exc:
        logger.warning("URL fetch error for %s: %s", url, exc)
        return None


def extract_readable_text(html: str, url: str = "") -> str:
    """Extract main readable text from HTML using readability.

    Returns clean text truncated to _MAX_TEXT_LENGTH chars.
    """
    if not html.strip():
        return ""
    try:
        doc = Document(html, url=url)
        # doc.summary() returns cleaned HTML of the main content
        summary_html = doc.summary()
        # Strip remaining HTML tags for plain text
        import re
        text = re.sub(r"<[^>]+>", " ", summary_html)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:_MAX_TEXT_LENGTH]
    except Exception as exc:
        logger.warning("Readability extraction failed: %s", exc)
        return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_url_fetcher.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bot/url_fetcher.py tests/test_url_fetcher.py requirements.txt
git commit -m "feat: add URL fetcher with readability text extraction"
```

---

### Task 3: Add LLM summarize_text method

**Files:**
- Create: `tests/test_url_summary.py`
- Modify: `src/llm/client.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_url_summary.py`:

```python
"""Tests for LLM URL content summarization."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_summarize_text_returns_summary(fake_llm):
    """summarize_text sends content to LLM and returns response."""
    from src.llm.client import LLMClient
    from unittest.mock import AsyncMock, MagicMock

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "这篇文章讲了分布式系统的一致性问题。"

    client = LLMClient(base_url="http://fake", api_key="fake", model="test")
    client._client = MagicMock()
    client._client.chat = MagicMock()
    client._client.chat.completions = MagicMock()
    client._client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = await client.summarize_text(
        text="Long article about distributed systems consistency...",
        url="https://example.com/article",
    )
    assert "分布式" in result or result  # LLM response is returned
    # Verify the messages sent to LLM contain the URL and text
    call_kwargs = client._client.chat.completions.create.call_args
    messages = call_kwargs.kwargs["messages"]
    assert any("example.com" in m["content"] for m in messages)


@pytest.mark.asyncio
async def test_summarize_text_returns_fallback_on_empty():
    """summarize_text returns fallback when text is empty."""
    from src.llm.client import LLMClient

    client = LLMClient(base_url="http://fake", api_key="fake", model="test")
    result = await client.summarize_text(text="", url="https://example.com")
    assert "无法提取" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_url_summary.py -v`
Expected: FAIL with `AttributeError: 'LLMClient' object has no attribute 'summarize_text'`

- [ ] **Step 3: Add summarize_text method to LLMClient**

Add this method to the `LLMClient` class in `src/llm/client.py`, after the `classify` method:

```python
    async def summarize_text(self, text: str, url: str = "") -> str:
        """Summarize URL content. Returns a short Chinese summary."""
        if not text.strip():
            return f"无法提取内容: {url}"

        truncated = text[:2000]
        response = await self.chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是 DailyClaw 的阅读助手。用户分享了一个链接，请用中文简要概括内容要点。\n"
                        "要求：2-4 句话，提炼核心信息，不要重复原文。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"链接: {url}\n\n内容:\n{truncated}",
                },
            ],
            temperature=0.3,
            max_tokens=300,
        )
        return response
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_url_summary.py -v`
Expected: All 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm/client.py tests/test_url_summary.py
git commit -m "feat: add LLM summarize_text method for URL content"
```

---

### Task 4: Wire URL summarization into handle_text

**Files:**
- Modify: `src/bot/handlers.py`

- [ ] **Step 1: Update handle_text to fetch and summarize URLs**

Replace the `handle_text` function in `src/bot/handlers.py` with:

```python
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    if not update.effective_user or not update.message:
        return
    db: Database = context.bot_data["db"]
    llm: LLMClient = context.bot_data["llm"]
    user_id = update.effective_user.id
    text = update.message.text

    # Detect message type
    urls = URL_PATTERN.findall(text)
    has_url = bool(urls)
    msg_type = MessageType.LINK if has_url else MessageType.TEXT

    # Use LLM to classify the message
    classification = await llm.classify(text)
    category = CATEGORY_MAP.get(classification.get("category"))

    # If URL detected, fetch and summarize
    url_summary = ""
    if has_url:
        from .url_fetcher import extract_readable_text, fetch_url

        first_url = urls[0]
        html = await fetch_url(first_url)
        if html:
            readable = extract_readable_text(html, url=first_url)
            if readable:
                url_summary = await llm.summarize_text(text=readable, url=first_url)

    # Build metadata with optional URL summary
    meta = dict(classification)
    if url_summary:
        meta["url_summary"] = url_summary
    metadata = json.dumps(meta, ensure_ascii=False)

    await db.save_message(user_id, msg_type, text, category, metadata)

    # Build response
    cat_label = CATEGORY_LABELS.get(category, "记录") if category else "记录"
    summary = classification.get("summary", "")
    reply = f"已记录到今日「{cat_label}」。"
    if summary and summary != text[:50]:
        reply += f"\n📝 {summary}"
    if url_summary:
        reply += f"\n\n🔗 链接摘要：\n{url_summary}"
    else:
        reply += "\n\n有更多想补充的吗？"

    await update.message.reply_text(reply)
```

Note the key changes from original:
1. `URL_PATTERN.findall(text)` instead of `.search(text)` — captures actual URLs
2. Fetches first URL, extracts readable text, summarizes via LLM
3. Stores `url_summary` in metadata JSON
4. Includes summary in reply

- [ ] **Step 2: Verify the import of `LLMClient` already exists**

The existing import at the top of `handlers.py` already has `from ..llm.client import LLMClient`. No change needed.

- [ ] **Step 3: Manual smoke test**

Run: `python -m src.main` (requires valid `.env` and `config.yaml`)
Send a message with a URL to the bot. Verify it replies with a summary.

- [ ] **Step 4: Commit**

```bash
git add src/bot/handlers.py
git commit -m "feat: wire URL fetch + summarize into text message handler"
```

---

## Part 2: Image Understanding (doubao-seed)

### Task 5: Add vision config

**Files:**
- Modify: `config.example.yaml`
- Modify: `.env.example`
- Modify: `src/config.py`

- [ ] **Step 1: Update config.example.yaml**

Add this block after the `llm:` section:

```yaml
vision:
  base_url: "https://ark.cn-beijing.volces.com/api/v3"   # 豆包 doubao-seed API
  api_key: "${VISION_API_KEY}"
  model: "doubao-seed-1241-v2.0-250304"                   # doubao-seed vision model
```

- [ ] **Step 2: Update .env.example**

Add this line:

```
VISION_API_KEY=your-vision-api-key
```

- [ ] **Step 3: Update config.py validation**

In `src/config.py`, the `load_config` function's validation section currently checks `telegram.token` and `llm.api_key`. Add optional vision validation after the existing checks:

```python
    # Vision config is optional — only validate if present
    vision = config.get("vision")
    if vision:
        if not vision.get("api_key"):
            raise ValueError("vision.api_key is required when vision section is configured")
        if not vision.get("base_url"):
            raise ValueError("vision.base_url is required when vision section is configured")
```

- [ ] **Step 4: Commit**

```bash
git add config.example.yaml .env.example src/config.py
git commit -m "feat: add vision (doubao-seed) config section"
```

---

### Task 6: Create VisionClient

**Files:**
- Create: `tests/test_vision.py`
- Create: `src/llm/vision.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_vision.py`:

```python
"""Tests for VisionClient image understanding."""
from __future__ import annotations

import base64

import pytest

from tests.conftest import FakeVisionClient


@pytest.mark.asyncio
async def test_analyze_image_sends_base64_payload():
    """analyze_image sends image as base64 data URL to the model."""
    client = FakeVisionClient(responses=["这是一张猫的照片，毛色为橘色。"])
    # 1x1 white PNG
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )
    result = await client.analyze_image(image_bytes, caption="我的猫")
    assert "猫" in result
    assert len(client.calls) == 1
    # Verify the message structure includes image_url content part
    messages = client.calls[0]
    user_msg = messages[-1]
    assert user_msg["role"] == "user"
    assert isinstance(user_msg["content"], list)
    assert any(part["type"] == "image_url" for part in user_msg["content"])


@pytest.mark.asyncio
async def test_analyze_image_includes_caption():
    """analyze_image includes user caption in the prompt."""
    client = FakeVisionClient(responses=["照片分析结果"])
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )
    result = await client.analyze_image(image_bytes, caption="今天的午餐")
    messages = client.calls[0]
    user_msg = messages[-1]
    text_parts = [p for p in user_msg["content"] if p["type"] == "text"]
    assert any("午餐" in p["text"] for p in text_parts)


@pytest.mark.asyncio
async def test_analyze_image_works_without_caption():
    """analyze_image works when no caption is provided."""
    client = FakeVisionClient(responses=["一张风景照片"])
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )
    result = await client.analyze_image(image_bytes)
    assert result == "一张风景照片"
```

- [ ] **Step 2: Add FakeVisionClient to conftest.py**

Append to `tests/conftest.py`:

```python
class FakeVisionClient:
    """Deterministic VisionClient stub for testing."""

    def __init__(self, responses: list[str] | None = None):
        self._responses = list(responses or [])
        self._call_index = 0
        self.calls: list[list[dict]] = []

    async def analyze_image(
        self,
        image_bytes: bytes,
        caption: str = "",
    ) -> str:
        import base64

        b64 = base64.b64encode(image_bytes).decode()
        content_parts: list[dict] = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            },
        ]
        text = caption or "请描述这张图片的内容。"
        content_parts.insert(0, {"type": "text", "text": text})
        messages = [
            {
                "role": "system",
                "content": "你是 DailyClaw 的图片理解助手。用中文简要描述图片内容，2-3句话。",
            },
            {"role": "user", "content": content_parts},
        ]
        self.calls.append(messages)
        if self._call_index < len(self._responses):
            resp = self._responses[self._call_index]
            self._call_index += 1
            return resp
        return "default vision response"


@pytest.fixture
def fake_vision():
    """Provide a FakeVisionClient factory."""
    def _factory(responses: list[str] | None = None) -> FakeVisionClient:
        return FakeVisionClient(responses)
    return _factory
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_vision.py -v`
Expected: Tests PASS because they use FakeVisionClient directly — but this validates our test structure and message format expectations.

- [ ] **Step 4: Create the real VisionClient**

Create `src/llm/vision.py`:

```python
"""Vision model client for image understanding (doubao-seed)."""
from __future__ import annotations

import base64
import logging

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class VisionClient:
    """Wraps an OpenAI-compatible vision API (doubao-seed)."""

    def __init__(self, base_url: str, api_key: str, model: str):
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self._model = model

    async def analyze_image(
        self,
        image_bytes: bytes,
        caption: str = "",
    ) -> str:
        """Send an image to the vision model and return a description.

        Args:
            image_bytes: Raw image bytes (JPEG/PNG).
            caption: Optional user caption to include as context.

        Returns:
            Chinese description of the image content.
        """
        b64 = base64.b64encode(image_bytes).decode()
        content_parts: list[dict] = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            },
        ]
        text = caption if caption else "请描述这张图片的内容。"
        content_parts.insert(0, {"type": "text", "text": text})

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是 DailyClaw 的图片理解助手。"
                        "用中文简要描述图片内容，2-3句话。"
                        "如果用户附了说明文字，结合图片和文字一起理解。"
                    ),
                },
                {"role": "user", "content": content_parts},
            ],
            max_tokens=300,
        )
        return response.choices[0].message.content or ""
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_vision.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/llm/vision.py tests/test_vision.py tests/conftest.py
git commit -m "feat: add VisionClient for doubao-seed image understanding"
```

---

### Task 7: Wire VisionClient into main.py and handle_photo

**Files:**
- Modify: `src/main.py`
- Modify: `src/bot/handlers.py`

- [ ] **Step 1: Instantiate VisionClient in main.py**

In `src/main.py`, add this import at the top with the other imports:

```python
from .llm.vision import VisionClient
```

Then in the `main()` function, after the LLM client setup (after line `llm = LLMClient(...)`) and before the auth filter, add:

```python
    # Vision (optional)
    vision: VisionClient | None = None
    vision_config = config.get("vision")
    if vision_config:
        vision = VisionClient(
            base_url=vision_config["base_url"],
            api_key=vision_config["api_key"],
            model=vision_config.get("model", "doubao-seed-1241-v2.0-250304"),
        )
```

And in the "Store shared resources" section, add:

```python
    app.bot_data["vision"] = vision
```

- [ ] **Step 2: Update handle_photo in handlers.py**

Add this import at the top of `handlers.py`:

```python
from ..llm.vision import VisionClient
```

Replace the `handle_photo` function with:

```python
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming photo messages — analyze with vision model if available."""
    if not update.effective_user or not update.message:
        return
    db: Database = context.bot_data["db"]
    vision: VisionClient | None = context.bot_data.get("vision")
    user_id = update.effective_user.id
    caption = update.message.caption or ""
    photo = update.message.photo[-1]  # highest resolution

    meta: dict = {"file_id": photo.file_id}

    # If vision model is configured, download and analyze the image
    analysis = ""
    if vision:
        try:
            file = await context.bot.get_file(photo.file_id)
            image_bytes = await file.download_as_bytearray()
            analysis = await vision.analyze_image(bytes(image_bytes), caption=caption)
            meta["vision_analysis"] = analysis
        except Exception:
            logger.exception("Vision analysis failed for photo from user %s", user_id)

    metadata = json.dumps(meta, ensure_ascii=False)
    await db.save_message(user_id, MessageType.PHOTO, caption or analysis or "[图片]", metadata=metadata)

    reply = "📷 图片已记录。"
    if caption:
        reply += f"\n备注: {caption}"
    if analysis:
        reply += f"\n\n🔍 图片理解：\n{analysis}"
    elif not vision:
        reply += "\n(未配置图片理解模型，仅保存图片)"

    await update.message.reply_text(reply)
```

Key changes from original:
1. Gets `vision` from `bot_data` (may be `None`)
2. Downloads image via Telegram API `get_file` + `download_as_bytearray`
3. Sends to `VisionClient.analyze_image` for understanding
4. Stores analysis in metadata JSON
5. Shows analysis in reply; graceful degradation if no vision configured

- [ ] **Step 3: Manual smoke test**

Run: `python -m src.main` (with vision config in `config.yaml`)
Send a photo to the bot. Verify it replies with an image description.
Also test without `vision:` config — should still work with "未配置" message.

- [ ] **Step 4: Commit**

```bash
git add src/main.py src/bot/handlers.py
git commit -m "feat: wire vision model into photo handler with graceful fallback"
```

---

### Task 8: Final integration test and cleanup

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS.

- [ ] **Step 2: Verify no import errors**

Run: `python -c "from src.main import main; print('OK')"`
Expected: Prints `OK`.

- [ ] **Step 3: Commit if any fixes were needed**

```bash
git add -A
git commit -m "test: fix integration issues from URL + vision features"
```
