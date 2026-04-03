# DailyClaw Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build DailyClaw — a self-hosted Telegram bot for structured daily journaling (曾国藩式), plan accountability with passive reminders, and a static sharing page. Deployed via Docker on Ubuntu with configurable LLM.

**Architecture:** Telegram ConversationHandler drives the multi-turn journal flow. python-telegram-bot's `JobQueue` schedules evening journal prompts and passive plan reminders. Jinja2 renders journal entries into a static HTML site for sharing. All state lives in SQLite; LLM calls use the existing `LLMClient` wrapper.

**Tech Stack:** Python 3.9+, python-telegram-bot 21.10 (with job-queue), aiosqlite, openai SDK, Jinja2

---

## File Map

### P0 — Bot Skeleton + Storage + LLM + Docker (DONE)

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/config.py` | YAML config loader with `${ENV_VAR}` resolution |
| Create | `src/storage/models.py` | Frozen dataclasses: `Message`, `JournalEntry`, `PlanCheckIn`, `Summary`, `JournalCategory`, `CATEGORY_LABELS` |
| Create | `src/storage/db.py` | Async SQLite CRUD with `_conn` guard property |
| Create | `src/llm/client.py` | OpenAI-compatible wrapper: `chat()`, `classify()` |
| Create | `src/bot/handlers.py` | Text/photo/voice message handlers with LLM classification |
| Create | `src/bot/commands.py` | `/start`, `/help`, `/today`, `/journal`, `/checkin`, `/plans` |
| Create | `src/main.py` | Entry point: config, auth filter, handler registration, lifecycle |
| Create | `config.example.yaml` | Example config with `allowed_user_ids`, LLM, plans, journal settings |
| Create | `Dockerfile` | Python 3.12-slim image |
| Create | `docker-compose.yml` | Single service with volume mounts for config + data |
| Create | `.env.example` | Template for secrets |
| Create | `requirements.txt` | python-telegram-bot, openai, pyyaml, aiosqlite, jinja2, tzdata |
| Create | `.gitignore` | Ignore .env, config.yaml, data/, caches |

### P1 — Journal Engine + Evening Reflection

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/journal/engine.py` | Multi-turn journal conversation logic: prompts per category, LLM-assisted follow-up, saves entries to DB |
| Create | `src/journal/scheduler.py` | Register evening journal job with `JobQueue` |
| Modify | `src/bot/commands.py` | Replace naive `cmd_journal` with `ConversationHandler` entry point |
| Modify | `src/main.py` | Wire `ConversationHandler` + register scheduled jobs |
| Create | `tests/test_journal_engine.py` | Unit tests for journal engine logic |
| Create | `tests/conftest.py` | Shared pytest fixtures (in-memory DB, mock LLM) |

### P2 — Plan Tracker + Passive Reminders

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/planner/reminder.py` | Check if user checked in today; send reminder if not |
| Create | `src/planner/scheduler.py` | Register per-plan reminder jobs with `JobQueue` |
| Modify | `src/main.py` | Wire plan reminder scheduler |
| Create | `tests/test_planner_reminder.py` | Unit tests for reminder logic |

### P3 — Periodic Summaries + Static Sharing

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/journal/summary.py` | Generate weekly/monthly/quarterly/yearly summaries via LLM |
| Create | `src/sharing/generator.py` | Render journal + summaries to static HTML via Jinja2 |
| Create | `templates/share.html` | Jinja2 template for the sharing page |
| Modify | `src/bot/commands.py` | Add `/summary` and `/share` commands |
| Modify | `src/main.py` | Register new commands + weekly summary job |
| Create | `tests/test_summary.py` | Unit tests for summary generation |
| Create | `tests/test_sharing_generator.py` | Unit tests for static HTML output |

---

## Phase 0: Bot Skeleton + Storage + LLM + Docker (COMPLETE)

### ~~Task 0a: Project scaffolding~~ DONE

**Files:**
- Create: `requirements.txt`, `config.example.yaml`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `.gitignore`
- Create: `src/__init__.py`, `src/bot/__init__.py`, `src/journal/__init__.py`, `src/planner/__init__.py`, `src/sharing/__init__.py`, `src/llm/__init__.py`, `src/storage/__init__.py`

- [x] **Step 1: Create all project files and package structure**
- [x] **Step 2: Verify directory structure**

---

### ~~Task 0b: Storage layer (SQLite)~~ DONE

**Files:**
- Create: `src/storage/models.py` — `MessageType`, `JournalCategory`, `CATEGORY_LABELS`, frozen dataclasses (`Message`, `JournalEntry`, `PlanCheckIn`, `Summary`)
- Create: `src/storage/db.py` — `Database` class with `_conn` guard, async CRUD for messages, journal entries, checkins, summaries

- [x] **Step 1: Implement models with frozen dataclasses**
- [x] **Step 2: Implement Database class with schema auto-creation**
- [x] **Step 3: Verify DB operations (save + query round-trip)**

---

### ~~Task 0c: LLM client~~ DONE

**Files:**
- Create: `src/llm/client.py` — `LLMClient` wrapping OpenAI-compatible API with `chat()` and `classify()`

- [x] **Step 1: Implement LLMClient with chat() and classify()**
- [x] **Step 2: Add input truncation (500 chars) and JSON parse error logging**

---

### ~~Task 0d: Telegram bot handlers~~ DONE

**Files:**
- Create: `src/bot/handlers.py` — `handle_text`, `handle_photo`, `handle_voice` with null guards and LLM classification
- Create: `src/bot/commands.py` — `/start`, `/help`, `/today`, `/journal`, `/checkin`, `/plans` with null guards and tag validation

- [x] **Step 1: Implement message handlers with LLM auto-classification**
- [x] **Step 2: Implement all command handlers**
- [x] **Step 3: Add null guards for update.effective_user and update.message**
- [x] **Step 4: Add tag validation in /checkin against configured plans**

---

### ~~Task 0e: Main entry point + config + auth + Docker~~ DONE

**Files:**
- Create: `src/config.py` — YAML loader with `${ENV_VAR}` resolution and validation
- Create: `src/main.py` — entry point with auth filter (`allowed_user_ids`), handler registration, lifecycle hooks

- [x] **Step 1: Implement config loader with env var resolution**
- [x] **Step 2: Implement auth filter using telegram.allowed_user_ids**
- [x] **Step 3: Wire all handlers with auth filter**
- [x] **Step 4: Add timezone error handling with tzdata fallback**
- [x] **Step 5: Verify all imports pass**
- [x] **Step 6: Code review — fixed 4 CRITICAL + 4 HIGH issues**

---

## Phase 1: Journal Engine + Evening Reflection

### Task 1: Test fixtures (conftest.py)

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [x] **Step 1: Create shared test fixtures**

```python
# tests/conftest.py
"""Shared pytest fixtures for DailyClaw tests."""
from __future__ import annotations

import asyncio
import os
import tempfile

import pytest

from src.storage.db import Database


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
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
```

```python
# tests/__init__.py
```

- [x] **Step 2: Verify fixtures load**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && pip install -q pytest pytest-asyncio && python -m pytest tests/ --collect-only`
Expected: `no tests ran` (collected 0 items, no errors)

- [x] **Step 3: Commit**

```bash
git add tests/__init__.py tests/conftest.py
git commit -m "test: add shared pytest fixtures (in-memory DB, FakeLLM)"
```

---

### Task 2: Journal engine — core logic

**Files:**
- Create: `src/journal/engine.py`
- Create: `tests/test_journal_engine.py`

- [x] **Step 1: Write failing tests for JournalEngine**

```python
# tests/test_journal_engine.py
"""Tests for the journal engine."""
from __future__ import annotations

import pytest
import pytest_asyncio

from src.journal.engine import JournalEngine
from src.storage.db import Database
from src.storage.models import JournalCategory


@pytest.mark.asyncio
async def test_start_session_returns_first_prompt(db, fake_llm):
    llm = fake_llm(["今天几点起床的？精神状态怎么样？"])
    engine = JournalEngine(db=db, llm=llm, user_id=1, date="2026-04-03")

    result = await engine.start()

    assert result  # non-empty prompt
    assert engine.current_category == JournalCategory.MORNING


@pytest.mark.asyncio
async def test_answer_saves_entry_and_advances(db, fake_llm):
    llm = fake_llm([
        "早起 prompt",          # start()
        "今天读了什么好文章？",   # answer() for MORNING -> advance to READING
    ])
    engine = JournalEngine(db=db, llm=llm, user_id=1, date="2026-04-03")
    await engine.start()

    result = await engine.answer("7点起的，精神不错")

    # Should have saved a MORNING entry
    entries = await db.get_journal_entries(1, "2026-04-03")
    assert len(entries) == 1
    assert entries[0].category == JournalCategory.MORNING
    assert "7点起的" in entries[0].content

    # Should have advanced to READING
    assert engine.current_category == JournalCategory.READING
    assert result  # next prompt


@pytest.mark.asyncio
async def test_full_session_completes_all_four(db, fake_llm):
    llm = fake_llm([
        "晨起 prompt",
        "所阅 prompt",
        "待人接物 prompt",
        "反省 prompt",
        "今日总结：做得不错！",
    ])
    engine = JournalEngine(db=db, llm=llm, user_id=1, date="2026-04-03")
    await engine.start()

    await engine.answer("7点起床")
    await engine.answer("看了一篇分布式系统文章")
    await engine.answer("和同事讨论了架构")
    result = await engine.answer("今天有点拖延")

    assert engine.is_complete
    entries = await db.get_journal_entries(1, "2026-04-03")
    assert len(entries) == 4
    categories = [e.category for e in entries]
    assert JournalCategory.MORNING in categories
    assert JournalCategory.READING in categories
    assert JournalCategory.SOCIAL in categories
    assert JournalCategory.REFLECTION in categories


@pytest.mark.asyncio
async def test_skip_category(db, fake_llm):
    llm = fake_llm([
        "晨起 prompt",
        "所阅 prompt",  # skipped MORNING, advance to READING
    ])
    engine = JournalEngine(db=db, llm=llm, user_id=1, date="2026-04-03")
    await engine.start()

    result = await engine.answer("跳过")

    # MORNING should NOT be saved
    entries = await db.get_journal_entries(1, "2026-04-03")
    assert len(entries) == 0
    assert engine.current_category == JournalCategory.READING
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -m pytest tests/test_journal_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.journal.engine'` (or `cannot import name 'JournalEngine'`)

- [x] **Step 3: Implement JournalEngine**

```python
# src/journal/engine.py
"""Journal engine — manages multi-turn 曾国藩式 reflection sessions."""
from __future__ import annotations

import logging

from ..llm.client import LLMClient
from ..storage.db import Database
from ..storage.models import CATEGORY_LABELS, JournalCategory

logger = logging.getLogger(__name__)

# Ordered categories for the reflection flow
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
    ):
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
        """Begin the journal session. Returns the first prompt."""
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
        """Process user's answer for current category, advance to next."""
        category = self.current_category
        if category is None:
            return "今日反思已完成。"

        # Check for skip
        if text.strip().lower() in SKIP_KEYWORDS:
            self._step += 1
            return await self._next_or_finish()

        # Save journal entry
        await self._db.save_journal_entry(
            user_id=self._user_id,
            date=self._date,
            category=category,
            content=text,
        )

        self._step += 1
        return await self._next_or_finish()

    async def _next_or_finish(self) -> str:
        """Move to next category or generate closing summary."""
        if self.is_complete:
            return await self._generate_closing()

        category = self.current_category
        label = CATEGORY_LABELS[category]

        self._conversation.append(
            {"role": "user", "content": f"继续，请引导「{label}」部分。"}
        )
        response = await self._llm.chat(
            messages=self._conversation[-6:]  # keep context bounded
        )
        self._conversation.append({"role": "assistant", "content": response})
        return response

    async def _generate_closing(self) -> str:
        """Generate a brief closing summary for the day."""
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
        """Build system prompt with today's context."""
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
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -m pytest tests/test_journal_engine.py -v`
Expected: 4 passed

- [x] **Step 5: Commit**

```bash
git add src/journal/engine.py tests/test_journal_engine.py
git commit -m "feat(P1): add JournalEngine with multi-turn reflection flow"
```

---

### Task 3: Wire journal ConversationHandler into the bot

**Files:**
- Modify: `src/bot/commands.py` — replace `cmd_journal` with ConversationHandler callbacks
- Modify: `src/main.py` — register ConversationHandler instead of plain CommandHandler for `/journal`

- [x] **Step 1: Rewrite journal commands in `src/bot/commands.py`**

Replace the existing `cmd_journal` function (lines 89-143) with three callbacks that work with Telegram's `ConversationHandler`:

```python
# Add to imports at top of src/bot/commands.py:
from telegram.ext import ConversationHandler

from ..journal.engine import JournalEngine

# Add state constant:
JOURNAL_ANSWERING = 0
```

Replace `cmd_journal` (lines 89-143) with:

```python
async def cmd_journal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the evening reflection journal. Entry point for ConversationHandler."""
    if not update.effective_user or not update.message:
        return ConversationHandler.END
    db: Database = context.bot_data["db"]
    llm: LLMClient = context.bot_data["llm"]
    tz = context.bot_data["tz"]
    user_id = update.effective_user.id
    today = datetime.now(tz).strftime("%Y-%m-%d")

    messages = await db.get_today_messages(user_id, today)
    today_texts = [m.content for m in messages[-20:]]

    engine = JournalEngine(
        db=db, llm=llm, user_id=user_id, date=today, today_messages=today_texts,
    )
    context.user_data["journal_engine"] = engine

    prompt = await engine.start()
    await update.message.reply_text(f"🌙 {prompt}")
    return JOURNAL_ANSWERING


async def journal_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user's answer during journal session."""
    if not update.effective_user or not update.message:
        return ConversationHandler.END

    engine: JournalEngine = context.user_data.get("journal_engine")
    if engine is None:
        await update.message.reply_text("没有进行中的反思。用 /journal 开始。")
        return ConversationHandler.END

    response = await engine.answer(update.message.text)

    if engine.is_complete:
        context.user_data.pop("journal_engine", None)
        await update.message.reply_text(f"✨ {response}")
        return ConversationHandler.END

    await update.message.reply_text(response)
    return JOURNAL_ANSWERING


async def journal_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the journal session."""
    if not update.message:
        return ConversationHandler.END
    context.user_data.pop("journal_engine", None)
    await update.message.reply_text("反思已取消。随时可以用 /journal 重新开始。")
    return ConversationHandler.END
```

- [x] **Step 2: Update `src/main.py` to use ConversationHandler**

Replace the journal command registration (line 93) and add the ConversationHandler. In `src/main.py`, add to imports:

```python
from telegram.ext import ConversationHandler
from .bot.commands import journal_answer, journal_cancel, JOURNAL_ANSWERING
```

Replace the line:
```python
    app.add_handler(CommandHandler("journal", cmd_journal, filters=auth))
```

With:
```python
    journal_conv = ConversationHandler(
        entry_points=[CommandHandler("journal", cmd_journal, filters=auth)],
        states={
            JOURNAL_ANSWERING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & auth, journal_answer),
            ],
        },
        fallbacks=[CommandHandler("cancel", journal_cancel, filters=auth)],
    )
    app.add_handler(journal_conv)
```

- [x] **Step 3: Update `/help` text to mention `/cancel`**

In `cmd_help` (line 43-52 of `src/bot/commands.py`), add `🚫 /cancel → 取消进行中的反思\n` to the help text.

- [x] **Step 4: Run all tests**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All pass

- [x] **Step 5: Verify imports**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -c "from src.main import main; print('OK')"`
Expected: `OK`

- [x] **Step 6: Commit**

```bash
git add src/bot/commands.py src/main.py
git commit -m "feat(P1): wire journal ConversationHandler for multi-turn reflection"
```

---

### Task 4: Evening journal scheduler

**Files:**
- Create: `src/journal/scheduler.py`
- Modify: `src/main.py` — call scheduler setup in `post_init`

- [x] **Step 1: Write the scheduler**

```python
# src/journal/scheduler.py
"""Schedule the evening journal prompt."""
from __future__ import annotations

import logging
from datetime import time

from telegram.ext import Application

logger = logging.getLogger(__name__)


async def evening_journal_callback(context) -> None:
    """Send journal reminder to all allowed users."""
    config = context.bot_data["config"]
    allowed_ids = config.get("telegram", {}).get("allowed_user_ids", [])

    for user_id in allowed_ids:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🌙 今天过得怎么样？用 /journal 开始今日反思吧。",
            )
        except Exception:
            logger.exception("Failed to send journal reminder to user %s", user_id)


def schedule_evening_journal(app: Application, hour: int, minute: int, tz) -> None:
    """Register a daily job to send the journal prompt."""
    job_time = time(hour=hour, minute=minute, tzinfo=tz)
    app.job_queue.run_daily(
        evening_journal_callback,
        time=job_time,
        name="evening_journal",
    )
    logger.info("Scheduled evening journal at %02d:%02d %s", hour, minute, tz)
```

- [x] **Step 2: Wire scheduler in `src/main.py`**

Add to imports:
```python
from .journal.scheduler import schedule_evening_journal
```

In `post_init`, after `logger.info("Database connected")`, add:
```python
    config = application.bot_data["config"]
    tz = application.bot_data["tz"]

    # Schedule evening journal prompt
    journal_time = config.get("journal", {}).get("evening_prompt_time", "21:30")
    h, m = (int(x) for x in journal_time.split(":"))
    schedule_evening_journal(application, h, m, tz)
```

- [x] **Step 3: Verify imports**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -c "from src.journal.scheduler import schedule_evening_journal; print('OK')"`
Expected: `OK`

- [x] **Step 4: Commit**

```bash
git add src/journal/scheduler.py src/main.py
git commit -m "feat(P1): schedule evening journal reminder via JobQueue"
```

---

## Phase 2: Plan Tracker + Passive Reminders

### Task 5: Passive reminder logic

**Files:**
- Create: `src/planner/reminder.py`
- Create: `tests/test_planner_reminder.py`

- [x] **Step 1: Write failing tests**

```python
# tests/test_planner_reminder.py
"""Tests for passive plan reminders."""
from __future__ import annotations

import pytest

from src.planner.reminder import check_needs_reminder
from src.storage.models import MessageType


@pytest.mark.asyncio
async def test_needs_reminder_when_no_checkin(db):
    result = await check_needs_reminder(db, user_id=1, tag="ielts", date="2026-04-03")
    assert result is True


@pytest.mark.asyncio
async def test_no_reminder_when_already_checked_in(db):
    await db.save_checkin(user_id=1, tag="ielts", date="2026-04-03", note="done")
    result = await check_needs_reminder(db, user_id=1, tag="ielts", date="2026-04-03")
    assert result is False


@pytest.mark.asyncio
async def test_needs_reminder_different_tag(db):
    await db.save_checkin(user_id=1, tag="workout", date="2026-04-03", note="ran")
    result = await check_needs_reminder(db, user_id=1, tag="ielts", date="2026-04-03")
    assert result is True
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -m pytest tests/test_planner_reminder.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Implement reminder logic**

```python
# src/planner/reminder.py
"""Passive plan reminder — only remind if user hasn't checked in."""
from __future__ import annotations

import logging

from ..storage.db import Database

logger = logging.getLogger(__name__)


async def check_needs_reminder(db: Database, user_id: int, tag: str, date: str) -> bool:
    """Return True if user has NOT checked in for this tag today."""
    checkins = await db.get_checkins_for_date(user_id, tag, date)
    return len(checkins) == 0
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -m pytest tests/test_planner_reminder.py -v`
Expected: 3 passed

- [x] **Step 5: Commit**

```bash
git add src/planner/reminder.py tests/test_planner_reminder.py
git commit -m "feat(P2): add check_needs_reminder for passive plan tracking"
```

---

### Task 6: Schedule plan reminders

**Files:**
- Create: `src/planner/scheduler.py`
- Modify: `src/main.py`

- [x] **Step 1: Implement plan scheduler**

```python
# src/planner/scheduler.py
"""Schedule passive plan reminders via JobQueue."""
from __future__ import annotations

import logging
from datetime import datetime, time

from telegram.ext import Application

from .reminder import check_needs_reminder

logger = logging.getLogger(__name__)

# Map config schedule day names to Python weekday ints
DAYS_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


async def plan_reminder_callback(context) -> None:
    """Check if user needs a reminder and send it."""
    db = context.bot_data["db"]
    tz = context.bot_data["tz"]
    plan = context.job.data  # the plan config dict
    tag = plan["tag"]
    name = plan["name"]
    today = datetime.now(tz).strftime("%Y-%m-%d")

    allowed_ids = context.bot_data["config"].get("telegram", {}).get("allowed_user_ids", [])
    for user_id in allowed_ids:
        needs = await check_needs_reminder(db, user_id, tag, today)
        if needs:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📖 今天的「{name}」还没打卡哦，还在计划中吗？\n用 /checkin {tag} <备注> 来打卡",
                )
            except Exception:
                logger.exception("Failed to send plan reminder to user %s", user_id)


def _parse_schedule_days(schedule: str) -> tuple[int, ...] | None:
    """Parse schedule string. Returns None for daily, tuple of weekday ints otherwise."""
    if schedule == "daily":
        return None  # every day
    days = []
    for d in schedule.split(","):
        d = d.strip().lower()
        if d in DAYS_MAP:
            days.append(DAYS_MAP[d])
    return tuple(days) if days else None


def schedule_plan_reminders(app: Application, plans: list[dict], tz) -> None:
    """Register reminder jobs for each configured plan."""
    for plan in plans:
        tag = plan["tag"]
        remind_time_str = plan.get("remind_time", "20:00")
        h, m = (int(x) for x in remind_time_str.split(":"))
        job_time = time(hour=h, minute=m, tzinfo=tz)
        schedule = plan.get("schedule", "daily")
        days = _parse_schedule_days(schedule)

        if days is None:
            # Daily
            app.job_queue.run_daily(
                plan_reminder_callback,
                time=job_time,
                name=f"plan_reminder_{tag}",
                data=plan,
            )
        else:
            # Specific days
            app.job_queue.run_daily(
                plan_reminder_callback,
                time=job_time,
                days=days,
                name=f"plan_reminder_{tag}",
                data=plan,
            )

        logger.info("Scheduled reminder for '%s' at %s (schedule: %s)", tag, remind_time_str, schedule)
```

- [x] **Step 2: Wire in `src/main.py`**

Add to imports:
```python
from .planner.scheduler import schedule_plan_reminders
```

In `post_init`, after the evening journal scheduling block, add:
```python
    # Schedule plan reminders
    plans = config.get("plans", [])
    if plans:
        schedule_plan_reminders(application, plans, tz)
```

- [x] **Step 3: Verify imports**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -c "from src.planner.scheduler import schedule_plan_reminders; print('OK')"`
Expected: `OK`

- [x] **Step 4: Run all tests**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All pass (7 total)

- [x] **Step 5: Commit**

```bash
git add src/planner/scheduler.py src/main.py
git commit -m "feat(P2): schedule passive plan reminders via JobQueue"
```

---

## Phase 3: Periodic Summaries + Static Sharing

### Task 7: Summary generation

**Files:**
- Create: `src/journal/summary.py`
- Create: `tests/test_summary.py`

- [x] **Step 1: Write failing tests**

```python
# tests/test_summary.py
"""Tests for summary generation."""
from __future__ import annotations

import pytest

from src.journal.summary import generate_summary
from src.storage.models import JournalCategory


@pytest.mark.asyncio
async def test_generate_weekly_summary(db, fake_llm):
    # Seed some journal entries
    for day in range(1, 4):
        date = f"2026-04-0{day}"
        await db.save_journal_entry(1, date, JournalCategory.MORNING, f"Day {day} morning")
        await db.save_journal_entry(1, date, JournalCategory.REFLECTION, f"Day {day} reflection")

    llm = fake_llm(["本周你坚持了3天早起，反思认真。继续保持！"])
    result = await generate_summary(
        db=db, llm=llm, user_id=1,
        period_type="week",
        start_date="2026-04-01",
        end_date="2026-04-07",
    )

    assert "本周" in result
    # Should also be saved to DB
    # (generate_summary saves via db.save_summary)


@pytest.mark.asyncio
async def test_generate_summary_no_entries(db, fake_llm):
    llm = fake_llm(["这段时间没有记录。"])
    result = await generate_summary(
        db=db, llm=llm, user_id=1,
        period_type="week",
        start_date="2026-04-01",
        end_date="2026-04-07",
    )

    assert result  # should still return something
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -m pytest tests/test_summary.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Implement summary generation**

```python
# src/journal/summary.py
"""Generate periodic summaries (weekly/monthly/quarterly/yearly) via LLM."""
from __future__ import annotations

import logging

from ..llm.client import LLMClient
from ..storage.db import Database
from ..storage.models import CATEGORY_LABELS

logger = logging.getLogger(__name__)

PERIOD_LABELS = {
    "week": "本周",
    "month": "本月",
    "quarter": "本季度",
    "year": "本年",
}


async def generate_summary(
    db: Database,
    llm: LLMClient,
    user_id: int,
    period_type: str,
    start_date: str,
    end_date: str,
) -> str:
    """Generate and save a summary for the given period."""
    entries = await db.get_journal_range(user_id, start_date, end_date)
    checkins = []
    # Gather checkin data for all tags
    cursor = await db._conn.execute(
        "SELECT tag, date, note, duration_minutes FROM plan_checkins "
        "WHERE user_id = ? AND date BETWEEN ? AND ? ORDER BY date",
        (user_id, start_date, end_date),
    )
    rows = await cursor.fetchall()
    checkin_lines = [f"- {r['date']} [{r['tag']}] {r['note']}" for r in rows]

    period_label = PERIOD_LABELS.get(period_type, period_type)

    if not entries and not checkin_lines:
        return f"{period_label}没有记录。开始用 /journal 记录每天的反思吧！"

    entry_text = ""
    if entries:
        entry_text = "\n".join(
            f"- {e.date} [{CATEGORY_LABELS.get(e.category, '')}] {e.content[:120]}"
            for e in entries
        )

    checkin_text = "\n".join(checkin_lines) if checkin_lines else "无打卡记录"

    response = await llm.chat(
        messages=[
            {
                "role": "system",
                "content": (
                    f"你是 DailyClaw 的总结助手。请为用户生成{period_label}总结。\n"
                    "包含：1) 整体评价 2) 做得好的地方 3) 需要改进的地方 4) 一句鼓励\n"
                    "简洁有力，用中文，300字以内。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"时间范围：{start_date} ~ {end_date}\n\n"
                    f"日记条目：\n{entry_text or '无'}\n\n"
                    f"计划打卡：\n{checkin_text}"
                ),
            },
        ],
        max_tokens=500,
    )

    await db.save_summary(user_id, period_type, start_date, end_date, response)
    return response
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -m pytest tests/test_summary.py -v`
Expected: 2 passed

- [x] **Step 5: Commit**

```bash
git add src/journal/summary.py tests/test_summary.py
git commit -m "feat(P3): add LLM-powered periodic summary generation"
```

---

### Task 8: Static sharing page generator

**Files:**
- Create: `src/sharing/generator.py`
- Create: `templates/share.html`
- Create: `tests/test_sharing_generator.py`

- [x] **Step 1: Write failing tests**

```python
# tests/test_sharing_generator.py
"""Tests for static sharing page generator."""
from __future__ import annotations

import os

import pytest

from src.sharing.generator import generate_share_page
from src.storage.models import JournalCategory


@pytest.mark.asyncio
async def test_generate_share_page(db, tmp_path):
    # Seed entries
    await db.save_journal_entry(1, "2026-04-03", JournalCategory.MORNING, "7点起床")
    await db.save_journal_entry(1, "2026-04-03", JournalCategory.READING, "读了分布式系统文章")

    output_dir = str(tmp_path / "site")
    result = await generate_share_page(
        db=db, user_id=1, date="2026-04-03",
        output_dir=output_dir, site_title="Test Claw",
    )

    assert os.path.exists(result)
    with open(result) as f:
        html = f.read()
    assert "7点起床" in html
    assert "分布式系统" in html
    assert "Test Claw" in html


@pytest.mark.asyncio
async def test_generate_share_page_empty(db, tmp_path):
    output_dir = str(tmp_path / "site")
    result = await generate_share_page(
        db=db, user_id=1, date="2026-04-03",
        output_dir=output_dir, site_title="Test",
    )

    assert os.path.exists(result)
    with open(result) as f:
        html = f.read()
    assert "暂无记录" in html
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -m pytest tests/test_sharing_generator.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Create the Jinja2 template**

```html
<!-- templates/share.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ site_title }} - {{ date }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, "Noto Sans SC", "PingFang SC", sans-serif;
            max-width: 680px;
            margin: 0 auto;
            padding: 2rem 1rem;
            color: #333;
            background: #fafafa;
            line-height: 1.7;
        }
        h1 { font-size: 1.4rem; margin-bottom: 0.5rem; }
        .date { color: #888; font-size: 0.9rem; margin-bottom: 2rem; }
        .category { margin-bottom: 1.5rem; }
        .category-label {
            font-weight: 600;
            color: #555;
            border-left: 3px solid #4a9;
            padding-left: 0.6rem;
            margin-bottom: 0.4rem;
        }
        .category-content {
            padding-left: 1rem;
            color: #444;
            white-space: pre-wrap;
        }
        .empty { color: #aaa; font-style: italic; }
        .summary {
            margin-top: 2rem;
            padding: 1rem;
            background: #f0f7f4;
            border-radius: 8px;
        }
        footer {
            margin-top: 3rem;
            color: #bbb;
            font-size: 0.8rem;
            text-align: center;
        }
    </style>
</head>
<body>
    <h1>{{ site_title }}</h1>
    <div class="date">{{ date }}</div>

    {% if entries %}
        {% for cat_label, content in entries %}
        <div class="category">
            <div class="category-label">{{ cat_label }}</div>
            <div class="category-content">{{ content }}</div>
        </div>
        {% endfor %}
    {% else %}
        <p class="empty">暂无记录</p>
    {% endif %}

    {% if summary %}
    <div class="summary">
        <div class="category-label">总结</div>
        <div class="category-content">{{ summary }}</div>
    </div>
    {% endif %}

    <footer>Powered by DailyClaw</footer>
</body>
</html>
```

- [x] **Step 4: Implement the generator**

```python
# src/sharing/generator.py
"""Generate static HTML sharing pages from journal entries."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..storage.db import Database
from ..storage.models import CATEGORY_LABELS

logger = logging.getLogger(__name__)

# Resolve templates dir relative to project root
_TEMPLATES_DIR = str(Path(__file__).resolve().parent.parent.parent / "templates")


async def generate_share_page(
    db: Database,
    user_id: int,
    date: str,
    output_dir: str,
    site_title: str = "My Daily Claw",
) -> str:
    """Generate a static HTML page for one day's journal. Returns output file path."""
    entries_raw = await db.get_journal_entries(user_id, date)

    entries = [
        (CATEGORY_LABELS.get(e.category, e.category.value), e.content)
        for e in entries_raw
    ]

    env = Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=True,
    )
    template = env.get_template("share.html")

    html = template.render(
        site_title=site_title,
        date=date,
        entries=entries,
        summary=None,
    )

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{date}.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Generated share page: %s", output_path)
    return output_path
```

- [x] **Step 5: Run tests to verify they pass**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -m pytest tests/test_sharing_generator.py -v`
Expected: 2 passed

- [x] **Step 6: Commit**

```bash
git add src/sharing/generator.py templates/share.html tests/test_sharing_generator.py
git commit -m "feat(P3): add static HTML sharing page generator with Jinja2"
```

---

### Task 9: Add `/summary` and `/share` commands

**Files:**
- Modify: `src/bot/commands.py` — add `cmd_summary` and `cmd_share`
- Modify: `src/main.py` — register new commands

- [x] **Step 1: Add commands to `src/bot/commands.py`**

Add to imports:
```python
from ..journal.summary import generate_summary
from ..sharing.generator import generate_share_page
```

Add at bottom of the file:

```python
async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a summary. Usage: /summary [week|month]"""
    if not update.effective_user or not update.message:
        return
    db: Database = context.bot_data["db"]
    llm: LLMClient = context.bot_data["llm"]
    tz = context.bot_data["tz"]
    user_id = update.effective_user.id
    now = datetime.now(tz)

    args = context.args or []
    period_type = args[0] if args else "week"

    if period_type == "week":
        start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")
    elif period_type == "month":
        start = now.strftime("%Y-%m-01")
        end = now.strftime("%Y-%m-%d")
    else:
        await update.message.reply_text("用法: /summary [week|month]")
        return

    await update.message.reply_text(f"正在生成{period_type}总结...")
    result = await generate_summary(
        db=db, llm=llm, user_id=user_id,
        period_type=period_type, start_date=start, end_date=end,
    )
    await update.message.reply_text(f"📊 {result}")


async def cmd_share(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a sharing page for today. Usage: /share [YYYY-MM-DD]"""
    if not update.effective_user or not update.message:
        return
    db: Database = context.bot_data["db"]
    config = context.bot_data["config"]
    tz = context.bot_data["tz"]
    user_id = update.effective_user.id

    args = context.args or []
    date = args[0] if args else datetime.now(tz).strftime("%Y-%m-%d")

    sharing_config = config.get("sharing", {})
    output_dir = sharing_config.get("output_dir", "./data/site")
    site_title = sharing_config.get("site_title", "My Daily Claw")

    path = await generate_share_page(
        db=db, user_id=user_id, date=date,
        output_dir=output_dir, site_title=site_title,
    )
    await update.message.reply_text(f"📄 分享页已生成: {path}\n(部署到 web 服务器后可通过链接分享)")
```

- [x] **Step 2: Register commands in `src/main.py`**

Add to imports:
```python
from .bot.commands import cmd_summary, cmd_share
```

Add after the existing command registrations:
```python
    app.add_handler(CommandHandler("summary", cmd_summary, filters=auth))
    app.add_handler(CommandHandler("share", cmd_share, filters=auth))
```

- [x] **Step 3: Update help text**

In `cmd_help`, add:
```
"📊 /summary [week|month] → 生成周/月总结\n"
"📄 /share [日期] → 生成分享页\n"
```

- [x] **Step 4: Verify imports**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -c "from src.main import main; print('OK')"`
Expected: `OK`

- [x] **Step 5: Run all tests**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All pass (11 total)

- [x] **Step 6: Commit**

```bash
git add src/bot/commands.py src/main.py
git commit -m "feat(P3): add /summary and /share commands"
```

---

### Task 10: Weekly summary scheduler

**Files:**
- Modify: `src/journal/scheduler.py`
- Modify: `src/main.py`

- [x] **Step 1: Add weekly summary job to `src/journal/scheduler.py`**

Add at bottom of the file:

```python
async def weekly_summary_callback(context) -> None:
    """Generate and send weekly summary every Sunday evening."""
    from .summary import generate_summary

    db = context.bot_data["db"]
    llm = context.bot_data["llm"]
    tz = context.bot_data["tz"]
    config = context.bot_data["config"]
    allowed_ids = config.get("telegram", {}).get("allowed_user_ids", [])

    now = datetime.now(tz)
    end = now.strftime("%Y-%m-%d")
    start = (now - timedelta(days=6)).strftime("%Y-%m-%d")

    for user_id in allowed_ids:
        try:
            result = await generate_summary(
                db=db, llm=llm, user_id=user_id,
                period_type="week", start_date=start, end_date=end,
            )
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📊 本周总结\n\n{result}",
            )
        except Exception:
            logger.exception("Failed to send weekly summary to user %s", user_id)


def schedule_weekly_summary(app: Application, tz) -> None:
    """Register weekly summary job for Sunday 22:00."""
    job_time = time(hour=22, minute=0, tzinfo=tz)
    app.job_queue.run_daily(
        weekly_summary_callback,
        time=job_time,
        days=(6,),  # Sunday
        name="weekly_summary",
    )
    logger.info("Scheduled weekly summary for Sunday 22:00 %s", tz)
```

Also add missing imports at top of `src/journal/scheduler.py`:
```python
from datetime import datetime, time, timedelta
```

- [x] **Step 2: Wire in `src/main.py`**

Update import:
```python
from .journal.scheduler import schedule_evening_journal, schedule_weekly_summary
```

In `post_init`, after plan reminders:
```python
    schedule_weekly_summary(application, tz)
```

- [x] **Step 3: Verify imports**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -c "from src.main import main; print('OK')"`
Expected: `OK`

- [x] **Step 4: Run all tests**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All pass

- [x] **Step 5: Commit**

```bash
git add src/journal/scheduler.py src/main.py
git commit -m "feat(P3): schedule automatic weekly summary on Sundays"
```

---

### Task 11: Final integration verification

**Files:** None (verification only)

- [x] **Step 1: Run full test suite**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -m pytest tests/ -v --tb=short`
Expected: 11 tests passed

- [x] **Step 2: Verify all imports cleanly**

Run: `cd /Users/chhua/github/dailyclaw && source .venv/bin/activate && python -c "from src.main import main; print('All modules loaded OK')"`
Expected: `All modules loaded OK`

- [x] **Step 3: Verify Docker builds**

Run: `cd /Users/chhua/github/dailyclaw && docker build -t dailyclaw:latest .`
Expected: Build succeeds

- [x] **Step 4: Final commit with all remaining files**

```bash
git add -A
git status
# Only commit if there are unstaged changes
git commit -m "chore: final P1-P3 cleanup"
```
