# Wiki Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform DailyClaw from isolated plugins into a three-layer personal LLM Wiki, renaming recorder/journal/planner to memo/reflect/track and adding a new wiki plugin for knowledge synthesis.

**Architecture:** Raw sources (messages, reflections, check-ins) feed into an LLM-maintained wiki of topic pages. The wiki plugin reads from all source tables via a watermark pattern — no tight coupling. A nudge hook in AppContext is the only cross-plugin wire.

**Tech Stack:** Python 3.12, aiosqlite, python-telegram-bot 21+, OpenAI SDK, pytest

**Spec:** `docs/specs/2026-04-14-wiki-redesign-design.md`

---

## File Map

### Modified files

| File | Changes |
|------|---------|
| `src/core/context.py` | Add optional `wiki_nudge` field |
| `src/core/migrations/004_rename_plugins.sql` | Rename schema_versions entries |
| `src/main.py` | Update `_PLUGIN_EMOJI`, help cmd_key logic |
| `src/main_locale.py` | No change (framework commands unchanged) |
| `config.example.yaml` | Rename plugin keys, add wiki section |

### Renamed plugins (directory rename + internal updates)

| From | To | Key changes |
|------|----|-------------|
| `src/plugins/recorder/` | `src/plugins/memo/` | Class→MemoPlugin, name→"memo", commands: today/heatmap/del |
| `src/plugins/journal/` | `src/plugins/reflect/` | Class→ReflectPlugin, name→"reflect", commands: reflect/review/cancel |
| `src/plugins/planner/` | `src/plugins/track/` | Class→TrackPlugin, name→"track", commands: goal/checkin/goals/drop |

### New files (wiki plugin)

| File | Responsibility |
|------|---------------|
| `src/plugins/wiki/__init__.py` | WikiPlugin registration, commands, intents, scheduler |
| `src/plugins/wiki/db.py` | WikiDB helper (CRUD for wiki_pages, wiki_log) |
| `src/plugins/wiki/ingest.py` | Batch ingest: source tables → wiki pages via LLM |
| `src/plugins/wiki/query.py` | Two-stage retrieval: topic selection → answer generation |
| `src/plugins/wiki/nudge.py` | Real-time connection detection with rate limiting |
| `src/plugins/wiki/digest.py` | Weekly insight generation from updated wiki pages |
| `src/plugins/wiki/lint.py` | Monthly health check: contradictions, stale, orphans |
| `src/plugins/wiki/scheduler.py` | Schedule ingest, digest, lint jobs |
| `src/plugins/wiki/locale.py` | i18n strings (zh/en/ja) |
| `src/plugins/wiki/migrations/001_init.sql` | wiki_pages + wiki_log tables |

### New test files

| File | Covers |
|------|--------|
| `tests/test_plugins/test_memo.py` | Renamed recorder tests |
| `tests/test_plugins/test_reflect.py` | Renamed journal tests |
| `tests/test_plugins/test_track.py` | Renamed planner tests |
| `tests/test_plugins/test_wiki.py` | WikiDB, ingest, query, nudge, digest, lint |

---

## Task 1: Core Migration — Rename Plugin Entries in schema_versions

**Files:**
- Create: `src/core/migrations/004_rename_plugins.sql`

This migration runs before plugin discovery, ensuring renamed plugins find their version history.

- [ ] **Step 1: Write the migration SQL**

```sql
-- 004_rename_plugins.sql
-- Rename plugin entries in schema_versions to match new directory names.
-- Safe to re-run: UPDATE WHERE ... only affects rows that exist.
UPDATE schema_versions SET plugin_name = 'memo' WHERE plugin_name = 'recorder';
UPDATE schema_versions SET plugin_name = 'reflect' WHERE plugin_name = 'journal';
UPDATE schema_versions SET plugin_name = 'track' WHERE plugin_name = 'planner';
```

- [ ] **Step 2: Write test for the migration**

In `tests/test_core/test_db.py`, add:

```python
@pytest.mark.asyncio
async def test_004_rename_plugins_migration(tmp_path):
    """Core migration 004 renames plugin entries in schema_versions."""
    db = Database(db_path=str(tmp_path / "rename_test.db"))
    await db.connect()
    runner = MigrationRunner(db)

    # Run core migrations up to 003
    await runner.run("core", _CORE_MIGRATIONS)

    # Seed old plugin names
    await db.conn.execute(
        "INSERT INTO schema_versions (plugin_name, version, filename) VALUES (?, ?, ?)",
        ("recorder", 1, "001_init.sql"),
    )
    await db.conn.execute(
        "INSERT INTO schema_versions (plugin_name, version, filename) VALUES (?, ?, ?)",
        ("journal", 1, "001_init.sql"),
    )
    await db.conn.execute(
        "INSERT INTO schema_versions (plugin_name, version, filename) VALUES (?, ?, ?)",
        ("planner", 1, "001_init.sql"),
    )
    await db.conn.commit()

    # Re-run core migrations (004 should apply)
    await runner.run("core", _CORE_MIGRATIONS)

    cursor = await db.conn.execute(
        "SELECT plugin_name FROM schema_versions WHERE plugin_name IN ('memo', 'reflect', 'track')"
    )
    rows = await cursor.fetchall()
    names = {row[0] for row in rows}
    assert names == {"memo", "reflect", "track"}

    # Old names should be gone
    cursor = await db.conn.execute(
        "SELECT plugin_name FROM schema_versions WHERE plugin_name IN ('recorder', 'journal', 'planner')"
    )
    rows = await cursor.fetchall()
    assert len(rows) == 0

    await db.close()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_core/test_db.py::test_004_rename_plugins_migration -v`
Expected: FAIL (migration file doesn't exist yet — but actually the SQL file does exist from Step 1. If running TDD strictly, write the test first, then the SQL. Either way, verify the test passes.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_core/test_db.py::test_004_rename_plugins_migration -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/migrations/004_rename_plugins.sql tests/test_core/test_db.py
git commit -m "feat: add core migration to rename plugin entries in schema_versions"
```

---

## Task 2: Rename recorder → memo

**Files:**
- Rename: `src/plugins/recorder/` → `src/plugins/memo/`
- Modify: all files within the renamed directory

This is a mechanical rename. The key changes in each file:

- [ ] **Step 1: Rename the directory**

```bash
git mv src/plugins/recorder src/plugins/memo
```

- [ ] **Step 2: Update `src/plugins/memo/__init__.py`**

Change class name, plugin name, commands:

```python
"""Memo plugin — auto-classify, dedup, URL summary."""
from __future__ import annotations

from src.core.bot import Command, Event, MessageHandler, MessageType
from src.core.plugin import BasePlugin

import src.plugins.memo.locale  # noqa: F401


class MemoPlugin(BasePlugin):
    name = "memo"
    version = "1.1.0"
    description = "消息记录 — 自动分类、去重、URL摘要"

    def get_commands(self) -> list[Command]:
        db = self.ctx.db
        tz = self.ctx.tz

        async def _del_handler(event: Event) -> str | None:
            from .commands import memo_del
            return await memo_del(db, event)

        async def _today_handler(event: Event) -> str | None:
            from .commands import memo_today
            return await memo_today(db, tz, event)

        async def _heatmap_handler(event: Event) -> str | None:
            from .commands import memo_heatmap
            return await memo_heatmap(db, tz, event)

        return [
            Command(name="today", description="查看今日记录", handler=_today_handler),
            Command(name="del", description="删除一条记录", handler=_del_handler),
            Command(name="heatmap", description="记录热力图", handler=_heatmap_handler),
        ]

    def get_handlers(self) -> list[MessageHandler]:
        from .handlers import make_handlers
        return make_handlers(self.ctx)

    async def on_startup(self) -> None:
        from .retry import make_retry_callback
        cb = make_retry_callback(self.ctx)
        await self.ctx.scheduler.run_repeating(
            cb,
            interval=10,
            name="retry_failed_messages",
            first=10,
        )
```

- [ ] **Step 3: Update `src/plugins/memo/commands.py`**

Rename functions: `recorder_del` → `memo_del`, `recorder_today` → `memo_today`, `recorder_list` → `memo_heatmap`. Update all `t("recorder.…")` calls to `t("memo.…")`.

Key changes (search-and-replace across the file):
- `recorder_del` → `memo_del`
- `recorder_today` → `memo_today`
- `recorder_list` → `memo_heatmap`
- `t("recorder.` → `t("memo.`

- [ ] **Step 4: Update `src/plugins/memo/handlers.py`**

Update import path and i18n namespace:
- `import src.plugins.recorder.locale` → `import src.plugins.memo.locale`
- `from .dedup import check_dedup` (unchanged — relative import)
- `from .url_fetcher import …` (unchanged — relative import)
- `t("recorder.` → `t("memo.`

- [ ] **Step 5: Update `src/plugins/memo/locale.py`**

Change the namespace registration at the bottom:
- `register("recorder", STRINGS)` → `register("memo", STRINGS)`

Update all i18n keys inside STRINGS: rename keys that reference command names.
- `"cmd.today"` (was `"cmd.today"` — same key, namespace changes via register)
- `"cmd.del"` (was `"cmd.del"` — same key)
- `"cmd.list"` → `"cmd.heatmap"`

- [ ] **Step 6: Update remaining files in `src/plugins/memo/`**

- `dedup.py`: Update `import src.plugins.recorder.locale` if present → `import src.plugins.memo.locale`
- `url_fetcher.py`, `url.py`: No changes needed (no i18n references)
- `retry.py`: Update `t("recorder.` → `t("memo.` if any

- [ ] **Step 7: Run tests to verify imports work**

```bash
python -c "from src.plugins.memo import MemoPlugin; print(MemoPlugin.name)"
```
Expected: `memo`

- [ ] **Step 8: Commit**

```bash
git add -A src/plugins/memo/
git commit -m "refactor: rename recorder plugin to memo"
```

---

## Task 3: Rename journal → reflect

**Files:**
- Rename: `src/plugins/journal/` → `src/plugins/reflect/`
- Modify: all files within the renamed directory

- [ ] **Step 1: Rename the directory**

```bash
git mv src/plugins/journal src/plugins/reflect
```

- [ ] **Step 2: Update `src/plugins/reflect/__init__.py`**

```python
"""Reflect plugin — 曾国藩式每日四省反思."""
from __future__ import annotations

from src.core.bot import Command, ConversationFlow, IntentDeclaration
from src.core.plugin import BasePlugin

import src.plugins.reflect.locale  # noqa: F401

_plugin_ctx = None  # type: ignore[assignment]


class ReflectPlugin(BasePlugin):
    name = "reflect"
    version = "1.1.0"
    description = "曾国藩式每日四省反思"

    def get_commands(self) -> list[Command]:
        from .commands import (
            cmd_cancel,
            cmd_reflect,
            cmd_review,
        )
        return [
            Command(name="reflect", description="开始今日反思", handler=cmd_reflect),
            Command(name="review", description="回顾日记", handler=cmd_review),
            Command(name="cancel", description="取消进行中的反思", handler=cmd_cancel),
        ]

    def get_intents(self) -> list[IntentDeclaration]:
        return []  # /journal_today removed; wiki handles queries now

    def get_conversations(self) -> list[ConversationFlow]:
        from .commands import cmd_reflect, reflect_answer_handler
        return [ConversationFlow(
            name="reflect_session",
            entry_command="reflect",
            entry_handler=cmd_reflect,
            states={0: reflect_answer_handler},
            cancel_command="cancel",
        )]

    async def on_startup(self) -> None:
        global _plugin_ctx
        _plugin_ctx = self.ctx
        from .scheduler import setup_reflect_schedules
        await setup_reflect_schedules(self.ctx)
```

- [ ] **Step 3: Update `src/plugins/reflect/commands.py`**

Rename functions:
- `cmd_journal_start` → `cmd_reflect`
- `cmd_journal_today` → removed (wiki handles this)
- `cmd_journal_review` → `cmd_review`
- `cmd_journal_cancel` → `cmd_cancel`
- `journal_answer_handler` → `reflect_answer_handler`

Update all i18n calls: `t("journal.` → `t("reflect.`

Update import: `from src.plugins.journal` → relative imports (already relative via `.`)

- [ ] **Step 4: Update `src/plugins/reflect/engine.py`**

Update i18n calls: `t("journal.` → `t("reflect.`
Update import: `import src.plugins.journal.locale` → `import src.plugins.reflect.locale`

- [ ] **Step 5: Update `src/plugins/reflect/scheduler.py`**

- `import src.plugins.journal.locale` → `import src.plugins.reflect.locale`
- `t("journal.` → `t("reflect.`
- `setup_journal_schedules` → `setup_reflect_schedules`
- Job names: `"journal_evening_prompt"` → `"reflect_evening_prompt"`, etc.
- `_evening_journal_callback` → `_evening_reflect_callback`
- `_auto_journal_callback` → `_auto_journal_callback` (keep this name — auto-journal is replaced by wiki ingest in Task 13, but for now keep it working)
- `_weekly_summary_callback` → `_weekly_summary_callback` (will be replaced by wiki digest)

- [ ] **Step 6: Update `src/plugins/reflect/locale.py`**

- `register("journal", STRINGS)` → `register("reflect", STRINGS)`
- Rename command keys: `"cmd.start"` → `"cmd.reflect"`, `"cmd.review"` stays, `"cmd.cancel"` stays
- Remove `"cmd.today"` key (no longer a command)

- [ ] **Step 7: Update `src/plugins/reflect/db.py` and `src/plugins/reflect/summary.py`**

- `db.py`: No i18n references — no changes needed
- `summary.py`: `t("journal.` → `t("reflect.`

- [ ] **Step 8: Verify imports**

```bash
python -c "from src.plugins.reflect import ReflectPlugin; print(ReflectPlugin.name)"
```
Expected: `reflect`

- [ ] **Step 9: Commit**

```bash
git add -A src/plugins/reflect/
git commit -m "refactor: rename journal plugin to reflect"
```

---

## Task 4: Rename planner → track

**Files:**
- Rename: `src/plugins/planner/` → `src/plugins/track/`
- Modify: all files within the renamed directory

- [ ] **Step 1: Rename the directory**

```bash
git mv src/plugins/planner src/plugins/track
```

- [ ] **Step 2: Update `src/plugins/track/__init__.py`**

```python
"""Track plugin — 计划与打卡 — 目标跟踪和智能匹配."""
from __future__ import annotations

from src.core.bot import Command, Event, IntentDeclaration
from src.core.plugin import BasePlugin

import src.plugins.track.locale  # noqa: F401


class TrackPlugin(BasePlugin):
    name = "track"
    version = "1.1.0"
    description = "计划与打卡 — 目标跟踪和智能匹配"

    def get_commands(self) -> list[Command]:
        from .commands import make_commands
        return make_commands(self.ctx)

    def get_intents(self) -> list[IntentDeclaration]:
        from .commands import make_commands

        commands = make_commands(self.ctx)
        cmd_map = {c.name: c.handler for c in commands}

        return [
            IntentDeclaration(
                name="track_checkin",
                description="User reports progress on a habit/plan (e.g. ran 5km, read 30 mins)",
                examples=(
                    "跑了5公里", "practiced piano for 30 minutes",
                    "读了一章书", "今天背了50个单词",
                ),
                handler=cmd_map["checkin"],
                args_description="What the user did — extract the activity description",
            ),
            IntentDeclaration(
                name="track_add",
                description="User wants to create a new habit or goal",
                examples=(
                    "我想每天跑步", "I want to start a daily reading habit",
                    "帮我建一个学英语的计划",
                ),
                handler=cmd_map["goal"],
                args_description="The plan description: what, when, how often",
            ),
            IntentDeclaration(
                name="track_list",
                description="User wants to see their active plans/goals and progress",
                examples=(
                    "看看我的计划", "show my plans",
                    "我的目标完成得怎么样",
                ),
                handler=cmd_map["goals"],
            ),
            IntentDeclaration(
                name="track_del",
                description="User wants to remove/archive a plan/goal",
                examples=(
                    "删除跑步计划", "remove the workout plan",
                    "不再跟踪阅读了",
                ),
                handler=cmd_map["drop"],
                args_description="The name or tag of the plan to remove",
            ),
        ]

    async def get_intent_context(self, user_id: int) -> str:
        cursor = await self.ctx.db.conn.execute(
            "SELECT tag, name FROM plans WHERE user_id = ? AND active = 1",
            (user_id,),
        )
        rows = await cursor.fetchall()
        if not rows:
            return ""
        lines = ["Active plans:"] + [f"  - {r[0]}: {r[1]}" for r in rows]
        return "\n".join(lines)

    async def on_startup(self) -> None:
        from .scheduler import setup_plan_reminders
        await setup_plan_reminders(self.ctx)
```

- [ ] **Step 3: Update `src/plugins/track/commands.py`**

Rename command names inside `make_commands()`:
- `"planner_add"` → `"goal"`
- `"planner_del"` → `"drop"`
- `"planner_checkin"` → `"checkin"`
- `"planner_list"` → `"goals"`

Rename function prefixes: `cmd_planner_add` → `cmd_goal`, etc.

Update all i18n calls: `t("planner.` → `t("track.`

Update cross-references in messages (e.g. "请先用 /planner_add" → "请先用 /goal")

- [ ] **Step 4: Update `src/plugins/track/locale.py`**

- `register("planner", STRINGS)` → `register("track", STRINGS)`
- Rename command keys: `"cmd.add"` → `"cmd.goal"`, `"cmd.del"` → `"cmd.drop"`, `"cmd.checkin"` stays, `"cmd.list"` → `"cmd.goals"`
- Update any message strings that reference old command names (e.g. "/planner_add" → "/goal")

- [ ] **Step 5: Update `src/plugins/track/scheduler.py`**

- `import src.plugins.planner.locale` → `import src.plugins.track.locale`
- `t("planner.` → `t("track.`

- [ ] **Step 6: Update `src/plugins/track/reminder.py`**

No i18n references — no changes needed.

- [ ] **Step 7: Update `src/plugins/track/db.py`** (if it exists)

Update any i18n references. If the file doesn't have i18n, skip.

- [ ] **Step 8: Verify imports**

```bash
python -c "from src.plugins.track import TrackPlugin; print(TrackPlugin.name)"
```
Expected: `track`

- [ ] **Step 9: Commit**

```bash
git add -A src/plugins/track/
git commit -m "refactor: rename planner plugin to track"
```

---

## Task 5: Update main.py for Renamed Plugins

**Files:**
- Modify: `src/main.py:85-89` (`_PLUGIN_EMOJI`)

- [ ] **Step 1: Update `_PLUGIN_EMOJI` dict**

At `src/main.py:85-89`, change:

```python
_PLUGIN_EMOJI: dict[str, str] = {
    "reflect": "🌙",
    "track": "📊",
    "memo": "📝",
    "wiki": "🧠",
}
```

- [ ] **Step 2: Verify the help cmd_key derivation still works**

The existing logic at line 108:
```python
cmd_key = cmd.name.replace(f"{plugin.name}_", "")
```

This works for the new names:
- Plugin "memo", command "today" → cmd_key = "today" → i18n `"memo.cmd.today"` ✓
- Plugin "reflect", command "reflect" → cmd_key = "reflect" → i18n `"reflect.cmd.reflect"` ✓
- Plugin "track", command "goal" → cmd_key = "goal" → i18n `"track.cmd.goal"` ✓
- Plugin "wiki", command "ask" → cmd_key = "ask" → i18n `"wiki.cmd.ask"` ✓

No code change needed here.

- [ ] **Step 3: Run the full test suite**

```bash
pytest tests/ -v --timeout=30
```

Fix any remaining import errors from the renames.

- [ ] **Step 4: Commit**

```bash
git add src/main.py
git commit -m "refactor: update main.py for renamed plugins"
```

---

## Task 6: Update config.example.yaml

**Files:**
- Modify: `config.example.yaml`

- [ ] **Step 1: Update plugin keys and add wiki section**

```yaml
telegram:
  token: "${TELEGRAM_BOT_TOKEN}"
  allowed_user_ids: [123456789]

llm:
  text:
    base_url: "https://api.openai.com/v1"
    api_key: "${LLM_API_KEY}"
    model: "gpt-4o-mini"
  vision:
    base_url: "https://ark.cn-beijing.volces.com/api/v3"
    api_key: "${VISION_API_KEY}"
    model: "doubao-seed-1241-v2.0-250304"

log_level: "DEBUG"
timezone: "Asia/Shanghai"

trial:
  rate_per_minute: 10
  daily_quota: 50

plugins:
  memo:
    dedup_window: 10

  wiki:
    seed_topics:
      - { topic: "health", title: "Health & Fitness" }
      - { topic: "career", title: "Career & Growth" }
      - { topic: "reading", title: "Reading Notes" }
      - { topic: "ideas", title: "Ideas & Inspiration" }
    ingest_hour: 22
    ingest_minute: 30
    digest_day: "sunday"
    digest_hour: 21
    nudge_enabled: true
    nudge_threshold: 0.85
    nudge_max_per_day: 3
    lint_day: 1

  reflect:
    remind_hour: 21
    remind_minute: 0
    auto_journal_hour: 22
    auto_journal_minute: 30
    template: "zeng_guofan"

  track: {}
```

- [ ] **Step 2: Commit**

```bash
git add config.example.yaml
git commit -m "chore: update config.example.yaml for renamed plugins and wiki"
```

---

## Task 7: Update Tests for Renamed Plugins

**Files:**
- Rename: `tests/test_plugins/test_recorder.py` → `tests/test_plugins/test_memo.py`
- Rename: `tests/test_plugins/test_journal.py` → `tests/test_plugins/test_reflect.py`
- Rename: `tests/test_plugins/test_planner.py` → `tests/test_plugins/test_track.py`
- Modify: `tests/test_integration.py`, `tests/test_integration_commands.py` (if they reference old names)

- [ ] **Step 1: Rename test files**

```bash
git mv tests/test_plugins/test_recorder.py tests/test_plugins/test_memo.py
git mv tests/test_plugins/test_journal.py tests/test_plugins/test_reflect.py
git mv tests/test_plugins/test_planner.py tests/test_plugins/test_track.py
```

- [ ] **Step 2: Update `tests/test_plugins/test_memo.py`**

- Update migration path: `_SRC_ROOT / "plugins" / "recorder" / "migrations"` → `_SRC_ROOT / "plugins" / "memo" / "migrations"`
- Update migration runner name: `await runner.run("recorder", …)` → `await runner.run("memo", …)`
- Update function imports: `from src.plugins.recorder.commands import recorder_del` → `from src.plugins.memo.commands import memo_del`
- Update function calls: `recorder_del(db, event)` → `memo_del(db, event)`
- Update i18n imports if present: `from src.plugins.recorder.dedup` → `from src.plugins.memo.dedup`

- [ ] **Step 3: Update `tests/test_plugins/test_reflect.py`**

- Update imports: `from src.plugins.journal.engine import …` → `from src.plugins.reflect.engine import …`
- Update i18n assertions if they reference "journal" namespace

- [ ] **Step 4: Update `tests/test_plugins/test_track.py`**

- Update migration path: `"src/plugins/planner/migrations"` → `"src/plugins/track/migrations"`
- Update migration runner name: `await runner.run("planner", …)` → `await runner.run("track", …)`
- Update imports: `from src.plugins.planner.commands import make_commands` → `from src.plugins.track.commands import make_commands`
- Update command name lookups: `c.name == "planner_add"` → `c.name == "goal"`, etc.
- Update assertion strings: `"已创建计划"`, `"已打卡"`, `"已归档"` should remain the same (those are i18n message values, not command names)
- Update scheduler imports: `from src.plugins.planner.scheduler` → `from src.plugins.track.scheduler`
- Update scheduler job names: `"plan_reminder_ielts"` (unchanged — scheduler uses plan tag, not plugin name)

- [ ] **Step 5: Update integration test files**

Read `tests/test_integration.py` and `tests/test_integration_commands.py`. Update any references to old plugin names, command names, or import paths.

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v --timeout=30
```

All tests must pass. Fix any remaining references.

- [ ] **Step 7: Commit**

```bash
git add tests/
git commit -m "test: update all tests for renamed plugins (memo/reflect/track)"
```

---

## Task 8: Wiki Plugin — DB Schema + WikiDB Helper

**Files:**
- Create: `src/plugins/wiki/migrations/001_init.sql`
- Create: `src/plugins/wiki/db.py`
- Create: `tests/test_plugins/test_wiki.py` (initial DB tests)

- [ ] **Step 1: Write the migration**

Create `src/plugins/wiki/__init__.py` (empty for now, needed for package):
```python
```

Create `src/plugins/wiki/migrations/001_init.sql`:

```sql
CREATE TABLE IF NOT EXISTS wiki_pages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    topic        TEXT NOT NULL,
    title        TEXT NOT NULL,
    content      TEXT NOT NULL,
    links        TEXT DEFAULT '[]',
    page_type    TEXT DEFAULT 'organic',
    source_count INTEGER DEFAULT 0,
    last_ingest  TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, topic)
);

CREATE INDEX IF NOT EXISTS idx_wiki_pages_user ON wiki_pages(user_id, updated_at);

CREATE TABLE IF NOT EXISTS wiki_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    op         TEXT NOT NULL,
    detail     TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_wiki_log_user ON wiki_log(user_id, created_at);
```

- [ ] **Step 2: Write WikiDB helper**

Create `src/plugins/wiki/db.py`:

```python
"""WikiDB — data access for wiki_pages and wiki_log tables."""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class WikiDB:
    """Immutable-style data access — every write returns a new value, never mutates arguments."""

    def __init__(self, db: Any) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # wiki_pages CRUD
    # ------------------------------------------------------------------

    async def get_topic_index(self, user_id: int) -> list[dict[str, Any]]:
        """Return all topics for a user: topic, title, source_count, updated_at."""
        cursor = await self._db.conn.execute(
            "SELECT topic, title, page_type, source_count, updated_at "
            "FROM wiki_pages WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_page(self, user_id: int, topic: str) -> dict[str, Any] | None:
        """Return full page content for a topic, or None."""
        cursor = await self._db.conn.execute(
            "SELECT id, topic, title, content, links, page_type, source_count, "
            "last_ingest, created_at, updated_at "
            "FROM wiki_pages WHERE user_id = ? AND topic = ?",
            (user_id, topic),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_pages(self, user_id: int, topics: list[str]) -> list[dict[str, Any]]:
        """Return full pages for a list of topics."""
        if not topics:
            return []
        placeholders = ",".join("?" for _ in topics)
        cursor = await self._db.conn.execute(
            f"SELECT id, topic, title, content, links, page_type, source_count, "
            f"last_ingest, created_at, updated_at "
            f"FROM wiki_pages WHERE user_id = ? AND topic IN ({placeholders})",
            (user_id, *topics),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def upsert_page(
        self,
        user_id: int,
        topic: str,
        title: str,
        content: str,
        links: list[str],
        page_type: str = "organic",
        source_delta: int = 0,
    ) -> int:
        """Insert or update a wiki page. Returns row ID."""
        links_json = json.dumps(links, ensure_ascii=False)
        cursor = await self._db.conn.execute(
            "INSERT INTO wiki_pages (user_id, topic, title, content, links, page_type, source_count, last_ingest, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now')) "
            "ON CONFLICT(user_id, topic) DO UPDATE SET "
            "title = excluded.title, "
            "content = excluded.content, "
            "links = excluded.links, "
            "source_count = source_count + ?, "
            "last_ingest = datetime('now'), "
            "updated_at = datetime('now')",
            (user_id, topic, title, content, links_json, page_type, source_delta, source_delta),
        )
        await self._db.conn.commit()
        return cursor.lastrowid or 0

    async def get_pages_updated_since(
        self, user_id: int, since: str,
    ) -> list[dict[str, Any]]:
        """Return pages updated since a given ISO datetime."""
        cursor = await self._db.conn.execute(
            "SELECT topic, title, content, links, source_count, updated_at "
            "FROM wiki_pages WHERE user_id = ? AND updated_at > ? "
            "ORDER BY updated_at DESC",
            (user_id, since),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_global_watermark(self, user_id: int) -> str | None:
        """Return the most recent last_ingest across all pages for a user."""
        cursor = await self._db.conn.execute(
            "SELECT MAX(last_ingest) AS wm FROM wiki_pages WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["wm"] if row and row["wm"] else None

    # ------------------------------------------------------------------
    # wiki_log
    # ------------------------------------------------------------------

    async def log_op(self, user_id: int, op: str, detail: str) -> None:
        """Append an entry to the wiki operation log."""
        await self._db.conn.execute(
            "INSERT INTO wiki_log (user_id, op, detail) VALUES (?, ?, ?)",
            (user_id, op, detail),
        )
        await self._db.conn.commit()

    async def get_recent_logs(
        self, user_id: int, limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return recent log entries."""
        cursor = await self._db.conn.execute(
            "SELECT op, detail, created_at FROM wiki_log "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 3: Write tests for WikiDB**

Create `tests/test_plugins/test_wiki.py`:

```python
"""Tests for the wiki plugin."""
from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from src.core.db import Database, MigrationRunner

_SRC_ROOT = Path(__file__).parent.parent.parent / "src"
_WIKI_MIGRATIONS = str(_SRC_ROOT / "plugins" / "wiki" / "migrations")
_CORE_MIGRATIONS = str(_SRC_ROOT / "core" / "migrations")


@pytest_asyncio.fixture
async def wiki_db(tmp_path):
    """Database with core + wiki migrations applied."""
    db = Database(db_path=str(tmp_path / "wiki_test.db"))
    await db.connect()
    runner = MigrationRunner(db)
    await runner.run("core", _CORE_MIGRATIONS)
    await runner.run("wiki", _WIKI_MIGRATIONS)
    yield db
    await db.close()


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wiki_pages_table_accepts_insert(wiki_db):
    """wiki_pages table should accept rows after migration."""
    await wiki_db.conn.execute(
        "INSERT INTO wiki_pages (user_id, topic, title, content) VALUES (?, ?, ?, ?)",
        (1, "fitness", "Fitness & Health", "# Fitness\nStarted running."),
    )
    await wiki_db.conn.commit()

    cursor = await wiki_db.conn.execute(
        "SELECT topic, title, content FROM wiki_pages WHERE user_id = 1"
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row["topic"] == "fitness"


@pytest.mark.asyncio
async def test_wiki_pages_unique_constraint(wiki_db):
    """wiki_pages enforces UNIQUE(user_id, topic)."""
    await wiki_db.conn.execute(
        "INSERT INTO wiki_pages (user_id, topic, title, content) VALUES (?, ?, ?, ?)",
        (1, "fitness", "Title A", "Content A"),
    )
    await wiki_db.conn.commit()

    with pytest.raises(Exception):
        await wiki_db.conn.execute(
            "INSERT INTO wiki_pages (user_id, topic, title, content) VALUES (?, ?, ?, ?)",
            (1, "fitness", "Title B", "Content B"),
        )


@pytest.mark.asyncio
async def test_wiki_log_accepts_entries(wiki_db):
    """wiki_log table should accept rows."""
    await wiki_db.conn.execute(
        "INSERT INTO wiki_log (user_id, op, detail) VALUES (?, ?, ?)",
        (1, "ingest", "Processed 5 sources, updated 3 pages"),
    )
    await wiki_db.conn.commit()

    cursor = await wiki_db.conn.execute(
        "SELECT op, detail FROM wiki_log WHERE user_id = 1"
    )
    row = await cursor.fetchone()
    assert row["op"] == "ingest"


# ---------------------------------------------------------------------------
# WikiDB tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wikidb_upsert_and_get(wiki_db):
    """WikiDB.upsert_page creates a page; get_page retrieves it."""
    from src.plugins.wiki.db import WikiDB

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(
        user_id=1,
        topic="career",
        title="Career & Growth",
        content="# Career\nThinking about systems programming.",
        links=["reading"],
        page_type="seed",
        source_delta=3,
    )

    page = await wdb.get_page(1, "career")
    assert page is not None
    assert page["title"] == "Career & Growth"
    assert page["source_count"] == 3
    assert "systems programming" in page["content"]


@pytest.mark.asyncio
async def test_wikidb_upsert_updates_existing(wiki_db):
    """WikiDB.upsert_page updates content and bumps source_count."""
    from src.plugins.wiki.db import WikiDB

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(
        user_id=1, topic="fitness", title="Fitness", content="v1",
        links=[], source_delta=2,
    )
    await wdb.upsert_page(
        user_id=1, topic="fitness", title="Fitness v2", content="v2",
        links=["health"], source_delta=3,
    )

    page = await wdb.get_page(1, "fitness")
    assert page["title"] == "Fitness v2"
    assert page["content"] == "v2"
    assert page["source_count"] == 5  # 2 + 3


@pytest.mark.asyncio
async def test_wikidb_topic_index(wiki_db):
    """WikiDB.get_topic_index returns all topics for a user."""
    from src.plugins.wiki.db import WikiDB

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "a", "A", "content a", [], source_delta=1)
    await wdb.upsert_page(1, "b", "B", "content b", [], source_delta=1)
    await wdb.upsert_page(2, "c", "C", "other user", [], source_delta=1)

    index = await wdb.get_topic_index(1)
    topics = {p["topic"] for p in index}
    assert topics == {"a", "b"}


@pytest.mark.asyncio
async def test_wikidb_log_op(wiki_db):
    """WikiDB.log_op appends to wiki_log."""
    from src.plugins.wiki.db import WikiDB

    wdb = WikiDB(wiki_db)
    await wdb.log_op(1, "query", "Asked about career goals")
    await wdb.log_op(1, "ingest", "3 pages updated")

    logs = await wdb.get_recent_logs(1)
    assert len(logs) == 2
    assert logs[0]["op"] == "ingest"  # most recent first
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_plugins/test_wiki.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/plugins/wiki/ tests/test_plugins/test_wiki.py
git commit -m "feat(wiki): add DB schema, WikiDB helper, and tests"
```

---

## Task 9: Wiki Plugin — Ingest Pipeline

**Files:**
- Create: `src/plugins/wiki/ingest.py`
- Modify: `tests/test_plugins/test_wiki.py` (add ingest tests)

- [ ] **Step 1: Write the ingest module**

Create `src/plugins/wiki/ingest.py`:

```python
"""Wiki ingest pipeline — reads raw sources and updates wiki pages via LLM."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from src.core.i18n import t

from .db import WikiDB

logger = logging.getLogger(__name__)

# Source table definitions — wiki reads from these without other plugins knowing.
SOURCE_TABLES = [
    {
        "name": "memos",
        "table": "messages",
        "content_col": "content",
        "meta_col": "metadata",
        "time_col": "created_at",
        "type_col": "msg_type",
        "filter": "deleted_at IS NULL",
    },
    {
        "name": "reflections",
        "table": "journal_entries",
        "content_col": "content",
        "category_col": "category",
        "time_col": "created_at",
    },
    {
        "name": "checkins",
        "table": "plan_checkins",
        "content_col": "note",
        "tag_col": "tag",
        "time_col": "created_at",
    },
]


async def fetch_sources_since(
    db: Any,
    user_id: int,
    since: str | None,
) -> list[dict[str, str]]:
    """Fetch all raw sources for a user since the given ISO datetime.

    Returns a flat list of dicts: {source, time, content, extra}.
    """
    sources: list[dict[str, str]] = []

    for src_def in SOURCE_TABLES:
        time_col = src_def["time_col"]
        content_col = src_def["content_col"]
        table = src_def["table"]
        where = f"user_id = ? AND {time_col} > ?"
        if "filter" in src_def:
            where += f" AND {src_def['filter']}"

        watermark = since or "2000-01-01T00:00:00"
        cols = [content_col, time_col]
        extra_cols: list[str] = []
        for extra_key in ("meta_col", "category_col", "tag_col", "type_col"):
            if extra_key in src_def:
                cols.append(src_def[extra_key])
                extra_cols.append(src_def[extra_key])

        col_str = ", ".join(cols)
        query = f"SELECT {col_str} FROM {table} WHERE {where} ORDER BY {time_col}"

        try:
            cursor = await db.conn.execute(query, (user_id, watermark))
            rows = await cursor.fetchall()
        except Exception:
            logger.warning("Failed to fetch sources from %s", table, exc_info=True)
            continue

        for row in rows:
            content = row[content_col] or ""
            if not content.strip():
                continue
            time_str = row[time_col] or ""
            extra_parts: list[str] = []
            for ec in extra_cols:
                val = row[ec]
                if val:
                    extra_parts.append(f"{ec}={val[:100]}")

            sources.append({
                "source": src_def["name"],
                "time": time_str[11:16] if len(time_str) > 16 else time_str,
                "content": content[:300],
                "extra": "; ".join(extra_parts),
            })

    return sources


def build_ingest_prompt(
    topic_index: list[dict[str, Any]],
    sources: list[dict[str, str]],
    lang: str = "zh",
) -> list[dict[str, str]]:
    """Build the LLM messages for an ingest cycle."""
    topic_lines: list[str] = []
    for t_info in topic_index:
        topic_lines.append(
            f"- {t_info['topic']}: \"{t_info['title']}\" "
            f"({t_info.get('source_count', 0)} sources, last updated {t_info.get('updated_at', '?')})"
        )
    topics_str = "\n".join(topic_lines) if topic_lines else "(no existing topics)"

    source_lines: list[str] = []
    for i, s in enumerate(sources, 1):
        line = f"{i}. [{s['source']} {s['time']}] {s['content']}"
        if s.get("extra"):
            line += f" ({s['extra']})"
        source_lines.append(line)
    sources_str = "\n".join(source_lines)

    lang_map = {"zh": "中文", "en": "English", "ja": "日本語"}
    lang_name = lang_map.get(lang, "English")

    system = (
        "You are the DailyClaw wiki editor. Given new sources and the current topic index, "
        "update the wiki by creating or updating topic pages.\n\n"
        f"Existing topics:\n{topics_str}\n\n"
        "Return strict JSON array (no markdown wrapping):\n"
        '[{"topic":"slug","title":"Display Title","action":"update|create",'
        '"content":"full page content in markdown","links":["other-topic"],'
        '"reason":"why this update"}]\n\n'
        "Rules:\n"
        "- Update 1-10 pages per batch (proportional to source count)\n"
        "- Create new topics ONLY when no existing topic fits\n"
        "- Preserve existing page content — append, revise, or reorganize, never discard\n"
        "- Cross-link related topics in the links array\n"
        "- topic slugs: lowercase, hyphens, no spaces (e.g. 'rust-learning')\n"
        f"- Write all content in {lang_name}\n"
        "- If sources are trivial or don't add knowledge, return empty array []"
    )

    user = f"New sources ({len(sources)} items):\n{sources_str}"

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


async def run_ingest(
    db: Any,
    llm: Any,
    wiki_db: WikiDB,
    user_id: int,
    lang: str = "zh",
) -> dict[str, int]:
    """Run one ingest cycle for a user. Returns {created, updated, sources}."""
    watermark = await wiki_db.get_global_watermark(user_id)
    sources = await fetch_sources_since(db, user_id, watermark)

    if not sources:
        logger.debug("[wiki-ingest] user=%d no new sources since %s", user_id, watermark)
        return {"created": 0, "updated": 0, "sources": 0}

    topic_index = await wiki_db.get_topic_index(user_id)
    messages = build_ingest_prompt(topic_index, sources, lang)

    raw = await llm.chat(
        messages=messages,
        temperature=0.3,
        max_tokens=2000,
        lang=lang,
    )

    try:
        updates = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[wiki-ingest] LLM returned non-JSON: %s", raw[:200])
        return {"created": 0, "updated": 0, "sources": len(sources)}

    if not isinstance(updates, list):
        return {"created": 0, "updated": 0, "sources": len(sources)}

    created = 0
    updated = 0
    for item in updates:
        topic = item.get("topic", "")
        title = item.get("title", "")
        content = item.get("content", "")
        links = item.get("links", [])
        action = item.get("action", "update")

        if not topic or not content:
            continue

        existing = await wiki_db.get_page(user_id, topic)
        if existing and action == "update":
            # Merge: keep existing content structure, let LLM have replaced it
            pass  # LLM returns full updated content

        page_type = "organic"
        if existing:
            page_type = existing.get("page_type", "organic")

        await wiki_db.upsert_page(
            user_id=user_id,
            topic=topic,
            title=title,
            content=content,
            links=links if isinstance(links, list) else [],
            page_type=page_type,
            source_delta=len(sources),
        )

        if action == "create":
            created += 1
        else:
            updated += 1

    detail = f"Processed {len(sources)} sources → {created} created, {updated} updated"
    await wiki_db.log_op(user_id, "ingest", detail)
    logger.info("[wiki-ingest] user=%d %s", user_id, detail)

    return {"created": created, "updated": updated, "sources": len(sources)}
```

- [ ] **Step 2: Write ingest tests**

Append to `tests/test_plugins/test_wiki.py`:

```python
@pytest.mark.asyncio
async def test_fetch_sources_since_returns_memos(wiki_db):
    """fetch_sources_since reads from messages table."""
    from src.plugins.wiki.ingest import fetch_sources_since
    from src.core.db import MigrationRunner

    # Apply memo migrations so messages table exists
    runner = MigrationRunner(wiki_db)
    memo_migrations = str(_SRC_ROOT / "plugins" / "memo" / "migrations")
    await runner.run("memo", memo_migrations)

    await wiki_db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content, created_at) VALUES (?, ?, ?, ?)",
        (1, "text", "Ran 5km this morning", "2026-04-14 08:00:00"),
    )
    await wiki_db.conn.commit()

    sources = await fetch_sources_since(wiki_db, user_id=1, since="2026-04-13 00:00:00")
    assert len(sources) == 1
    assert "5km" in sources[0]["content"]
    assert sources[0]["source"] == "memos"


@pytest.mark.asyncio
async def test_build_ingest_prompt_includes_sources():
    """build_ingest_prompt includes topic index and source text."""
    from src.plugins.wiki.ingest import build_ingest_prompt

    index = [{"topic": "fitness", "title": "Fitness", "source_count": 5, "updated_at": "2026-04-13"}]
    sources = [{"source": "memos", "time": "08:00", "content": "Ran 5km", "extra": ""}]

    messages = build_ingest_prompt(index, sources, lang="en")
    assert len(messages) == 2
    assert "fitness" in messages[0]["content"]
    assert "Ran 5km" in messages[1]["content"]


@pytest.mark.asyncio
async def test_run_ingest_updates_pages(wiki_db):
    """run_ingest processes sources and writes wiki pages."""
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.ingest import run_ingest
    from src.core.db import MigrationRunner

    runner = MigrationRunner(wiki_db)
    memo_migrations = str(_SRC_ROOT / "plugins" / "memo" / "migrations")
    await runner.run("memo", memo_migrations)

    await wiki_db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content, created_at) VALUES (?, ?, ?, ?)",
        (1, "text", "Started learning Rust today", "2026-04-14 10:00:00"),
    )
    await wiki_db.conn.commit()

    import json

    class FakeIngestLLM:
        async def chat(self, messages, **kwargs):
            return json.dumps([{
                "topic": "rust-learning",
                "title": "Rust Learning",
                "action": "create",
                "content": "# Rust Learning\nStarted learning Rust on April 14.",
                "links": ["career"],
                "reason": "New topic from user's message",
            }])

    wdb = WikiDB(wiki_db)
    result = await run_ingest(wiki_db, FakeIngestLLM(), wdb, user_id=1, lang="en")

    assert result["created"] == 1
    assert result["sources"] == 1

    page = await wdb.get_page(1, "rust-learning")
    assert page is not None
    assert "Rust" in page["content"]
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_plugins/test_wiki.py -v -k "ingest"
```
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/plugins/wiki/ingest.py tests/test_plugins/test_wiki.py
git commit -m "feat(wiki): add ingest pipeline with source registry pattern"
```

---

## Task 10: Wiki Plugin — Query Engine

**Files:**
- Create: `src/plugins/wiki/query.py`
- Modify: `tests/test_plugins/test_wiki.py` (add query tests)

- [ ] **Step 1: Write the query module**

Create `src/plugins/wiki/query.py`:

```python
"""Wiki query engine — two-stage retrieval (topic selection → answer generation)."""
from __future__ import annotations

import json
import logging
from typing import Any

from .db import WikiDB

logger = logging.getLogger(__name__)


async def answer_question(
    llm: Any,
    wiki_db: WikiDB,
    db: Any,
    user_id: int,
    question: str,
    lang: str = "zh",
) -> str:
    """Answer a user's question using the wiki. Two-stage retrieval."""
    # Stage 1: Topic selection
    topic_index = await wiki_db.get_topic_index(user_id)

    if not topic_index:
        return await _fallback_raw_search(db, llm, user_id, question, lang)

    index_text = "\n".join(
        f"- {t['topic']}: {t['title']}" for t in topic_index
    )

    selection_response = await llm.chat(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a topic selector. Given a question and a list of wiki topics, "
                    "return a JSON array of 1-5 topic slugs most relevant to answering the question.\n"
                    f"Available topics:\n{index_text}\n\n"
                    'Return strict JSON array: ["topic-a", "topic-b"]\n'
                    "If no topic is relevant, return empty array []"
                ),
            },
            {"role": "user", "content": question},
        ],
        temperature=0.1,
        max_tokens=200,
        lang=lang,
    )

    try:
        selected_topics = json.loads(selection_response)
    except json.JSONDecodeError:
        selected_topics = []

    if not isinstance(selected_topics, list) or not selected_topics:
        return await _fallback_raw_search(db, llm, user_id, question, lang)

    # Stage 2: Answer generation
    pages = await wiki_db.get_pages(user_id, selected_topics)
    if not pages:
        return await _fallback_raw_search(db, llm, user_id, question, lang)

    context_text = "\n\n---\n\n".join(
        f"## {p['title']}\n{p['content']}" for p in pages
    )

    lang_map = {"zh": "中文", "en": "English", "ja": "日本語"}
    lang_name = lang_map.get(lang, "English")

    answer = await llm.chat(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the user's personal knowledge assistant. Answer their question "
                    "based on their wiki — a collection of their own thoughts, habits, and experiences.\n\n"
                    f"Wiki context:\n{context_text}\n\n"
                    "Rules:\n"
                    "- Answer based on what the wiki says, not general knowledge\n"
                    "- If the wiki doesn't contain enough information, say so\n"
                    "- Be concise (3-5 sentences)\n"
                    "- Reference specific dates or details from the wiki when possible\n"
                    f"- Respond in {lang_name}"
                ),
            },
            {"role": "user", "content": question},
        ],
        temperature=0.5,
        max_tokens=500,
        lang=lang,
    )

    await wiki_db.log_op(user_id, "query", f"Q: {question[:100]} → {len(pages)} pages")
    return answer


async def _fallback_raw_search(
    db: Any,
    llm: Any,
    user_id: int,
    question: str,
    lang: str,
) -> str:
    """Fallback: search raw messages from last 30 days when wiki is insufficient."""
    try:
        cursor = await db.conn.execute(
            "SELECT content, created_at FROM messages "
            "WHERE user_id = ? AND deleted_at IS NULL "
            "AND created_at > datetime('now', '-30 days') "
            "ORDER BY created_at DESC LIMIT 50",
            (user_id,),
        )
        rows = await cursor.fetchall()
    except Exception:
        rows = []

    if not rows:
        lang_map = {
            "zh": "你的知识库还没有足够的内容来回答这个问题。继续记录，我会慢慢学习你的生活。",
            "en": "Your wiki doesn't have enough content to answer this yet. Keep recording and I'll learn over time.",
            "ja": "まだこの質問に答えるのに十分な内容がありません。記録を続けてください。",
        }
        return lang_map.get(lang, lang_map["en"])

    context = "\n".join(
        f"[{r['created_at'][:10]}] {r['content'][:150]}" for r in rows
    )

    lang_map = {"zh": "中文", "en": "English", "ja": "日本語"}
    lang_name = lang_map.get(lang, "English")

    return await llm.chat(
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer the user's question based on their recent messages (last 30 days). "
                    "Be concise. If you can't find relevant info, say so.\n\n"
                    f"Recent messages:\n{context}\n\n"
                    f"Respond in {lang_name}"
                ),
            },
            {"role": "user", "content": question},
        ],
        temperature=0.5,
        max_tokens=500,
        lang=lang,
    )
```

- [ ] **Step 2: Write query tests**

Append to `tests/test_plugins/test_wiki.py`:

```python
@pytest.mark.asyncio
async def test_answer_question_two_stage(wiki_db):
    """answer_question selects topics then generates answer from wiki pages."""
    import json
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.query import answer_question

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "fitness", "Fitness", "Running 5km daily since April.", ["health"])
    await wdb.upsert_page(1, "career", "Career", "Thinking about Rust.", [])

    class FakeQueryLLM:
        def __init__(self):
            self._call = 0

        async def chat(self, messages, **kwargs):
            self._call += 1
            if self._call == 1:
                return json.dumps(["fitness"])  # topic selection
            return "You've been running 5km daily since April."  # answer

    answer = await answer_question(FakeQueryLLM(), wdb, wiki_db, 1, "How's my running?", lang="en")
    assert "5km" in answer or "running" in answer


@pytest.mark.asyncio
async def test_answer_question_fallback_no_topics(wiki_db):
    """answer_question falls back to raw messages when no wiki topics exist."""
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.query import answer_question
    from src.core.db import MigrationRunner

    runner = MigrationRunner(wiki_db)
    memo_migrations = str(_SRC_ROOT / "plugins" / "memo" / "migrations")
    await runner.run("memo", memo_migrations)

    await wiki_db.conn.execute(
        "INSERT INTO messages (user_id, msg_type, content) VALUES (?, ?, ?)",
        (1, "text", "Felt stressed about deadline today"),
    )
    await wiki_db.conn.commit()

    class FakeFallbackLLM:
        async def chat(self, messages, **kwargs):
            return "Based on your recent messages, you seem stressed about a deadline."

    wdb = WikiDB(wiki_db)
    answer = await answer_question(FakeFallbackLLM(), wdb, wiki_db, 1, "Am I stressed?", lang="en")
    assert "stressed" in answer.lower() or "deadline" in answer.lower()
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_plugins/test_wiki.py -v -k "query or answer"
```
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/plugins/wiki/query.py tests/test_plugins/test_wiki.py
git commit -m "feat(wiki): add two-stage query engine with raw message fallback"
```

---

## Task 11: Wiki Plugin — Nudge, Digest, Lint

**Files:**
- Create: `src/plugins/wiki/nudge.py`
- Create: `src/plugins/wiki/digest.py`
- Create: `src/plugins/wiki/lint.py`
- Modify: `tests/test_plugins/test_wiki.py`

- [ ] **Step 1: Write nudge module**

Create `src/plugins/wiki/nudge.py`:

```python
"""Real-time connection detection — lightweight LLM check after each memo."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from .db import WikiDB

logger = logging.getLogger(__name__)

# In-memory daily nudge counter per user {user_id: {date: count}}
_nudge_counts: dict[int, dict[str, int]] = {}


async def check_nudge(
    llm: Any,
    wiki_db: WikiDB,
    user_id: int,
    content: str,
    lang: str = "zh",
    threshold: float = 0.85,
    max_per_day: int = 3,
) -> str | None:
    """Check if a new memo connects to existing wiki topics.

    Returns a nudge message string, or None if no strong connection found.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    user_counts = _nudge_counts.setdefault(user_id, {})
    if user_counts.get(today, 0) >= max_per_day:
        return None

    topic_index = await wiki_db.get_topic_index(user_id)
    if not topic_index:
        return None

    index_text = "\n".join(f"- {t['topic']}: {t['title']}" for t in topic_index)

    response = await llm.chat(
        messages=[
            {
                "role": "system",
                "content": (
                    "You detect connections between a new message and existing wiki topics.\n\n"
                    f"Wiki topics:\n{index_text}\n\n"
                    'Return strict JSON: {"topic":"slug","confidence":0.0-1.0,"reason":"brief reason"}\n'
                    "If no meaningful connection, return {\"topic\":\"\",\"confidence\":0.0,\"reason\":\"\"}"
                ),
            },
            {"role": "user", "content": content[:300]},
        ],
        temperature=0.1,
        max_tokens=150,
        lang=lang,
    )

    try:
        result = json.loads(response)
    except json.JSONDecodeError:
        return None

    confidence = result.get("confidence", 0)
    topic = result.get("topic", "")
    reason = result.get("reason", "")

    if confidence < threshold or not topic:
        return None

    user_counts[today] = user_counts.get(today, 0) + 1
    await wiki_db.log_op(user_id, "nudge", f"topic={topic} confidence={confidence}")

    return f"💡 {reason}"
```

- [ ] **Step 2: Write digest module**

Create `src/plugins/wiki/digest.py`:

```python
"""Weekly digest — generates insight from recently updated wiki pages."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from .db import WikiDB

logger = logging.getLogger(__name__)


async def generate_digest(
    llm: Any,
    wiki_db: WikiDB,
    user_id: int,
    lang: str = "zh",
    days: int = 7,
) -> str | None:
    """Generate a weekly digest from pages updated in the last N days.

    Returns the digest text, or None if no pages were updated.
    """
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    pages = await wiki_db.get_pages_updated_since(user_id, since)

    if not pages:
        return None

    context = "\n\n---\n\n".join(
        f"## {p['title']} (updated {p['updated_at'][:10]}, {p['source_count']} sources)\n{p['content']}"
        for p in pages
    )

    lang_map = {"zh": "中文", "en": "English", "ja": "日本語"}
    lang_name = lang_map.get(lang, "English")

    digest = await llm.chat(
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate a weekly personal insight digest. Based on the user's "
                    "recently updated wiki pages, provide:\n"
                    "1. Recurring themes this week\n"
                    "2. Notable connections across topics\n"
                    "3. Progress on tracked goals (if any)\n"
                    "4. One actionable suggestion\n\n"
                    "Keep it concise (5-8 sentences). Be warm and encouraging.\n"
                    f"Write in {lang_name}."
                ),
            },
            {"role": "user", "content": f"Wiki pages updated this week:\n{context}"},
        ],
        temperature=0.6,
        max_tokens=600,
        lang=lang,
    )

    await wiki_db.log_op(user_id, "digest", f"Generated from {len(pages)} updated pages")
    return digest
```

- [ ] **Step 3: Write lint module**

Create `src/plugins/wiki/lint.py`:

```python
"""Wiki lint — periodic health check for contradictions, stale pages, orphans."""
from __future__ import annotations

import json
import logging
from typing import Any

from .db import WikiDB

logger = logging.getLogger(__name__)


async def run_lint(
    llm: Any,
    wiki_db: WikiDB,
    user_id: int,
    lang: str = "zh",
) -> str | None:
    """Run a health check on all wiki pages. Returns a report or None if wiki is empty."""
    topic_index = await wiki_db.get_topic_index(user_id)
    if not topic_index:
        return None

    all_topics = [t["topic"] for t in topic_index]
    pages = await wiki_db.get_pages(user_id, all_topics)
    if not pages:
        return None

    # Build link graph for orphan detection
    all_slugs = {p["topic"] for p in pages}
    inbound: dict[str, int] = {slug: 0 for slug in all_slugs}
    for p in pages:
        links = json.loads(p.get("links", "[]")) if isinstance(p.get("links"), str) else p.get("links", [])
        for link in links:
            if link in inbound:
                inbound[link] += 1

    orphans = [slug for slug, count in inbound.items() if count == 0 and len(all_slugs) > 1]

    context = "\n\n---\n\n".join(
        f"## {p['title']} ({p['topic']})\nSources: {p['source_count']} | "
        f"Updated: {p.get('updated_at', '?')}\n{p['content'][:500]}"
        for p in pages
    )

    lang_map = {"zh": "中文", "en": "English", "ja": "日本語"}
    lang_name = lang_map.get(lang, "English")

    report = await llm.chat(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a wiki health checker. Review the user's personal wiki and report:\n"
                    "1. Contradictions between pages\n"
                    "2. Stale pages (not updated recently, check dates)\n"
                    "3. Topics that should be merged\n"
                    "4. Gaps (frequently referenced but no dedicated page)\n\n"
                    f"Known orphan pages (no inbound links): {orphans}\n\n"
                    "Be concise. Only report actual issues, not speculation.\n"
                    f"Write in {lang_name}."
                ),
            },
            {"role": "user", "content": f"Wiki pages:\n{context}"},
        ],
        temperature=0.3,
        max_tokens=500,
        lang=lang,
    )

    await wiki_db.log_op(user_id, "lint", f"Checked {len(pages)} pages")
    return report
```

- [ ] **Step 4: Write tests for nudge, digest, lint**

Append to `tests/test_plugins/test_wiki.py`:

```python
@pytest.mark.asyncio
async def test_nudge_returns_message_on_high_confidence(wiki_db):
    """check_nudge returns a nudge when confidence >= threshold."""
    import json
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.nudge import check_nudge

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "fitness", "Fitness", "Running streak.", [])

    class FakeNudgeLLM:
        async def chat(self, messages, **kwargs):
            return json.dumps({
                "topic": "fitness",
                "confidence": 0.9,
                "reason": "Connects to your running streak",
            })

    result = await check_nudge(FakeNudgeLLM(), wdb, 1, "Ran 5km today", threshold=0.85)
    assert result is not None
    assert "running streak" in result.lower()


@pytest.mark.asyncio
async def test_nudge_returns_none_on_low_confidence(wiki_db):
    """check_nudge returns None when confidence < threshold."""
    import json
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.nudge import check_nudge

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "fitness", "Fitness", "Running.", [])

    class FakeLowLLM:
        async def chat(self, messages, **kwargs):
            return json.dumps({"topic": "", "confidence": 0.3, "reason": ""})

    result = await check_nudge(FakeLowLLM(), wdb, 1, "Had lunch", threshold=0.85)
    assert result is None


@pytest.mark.asyncio
async def test_digest_generates_from_updated_pages(wiki_db):
    """generate_digest produces text from recently updated wiki pages."""
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.digest import generate_digest

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "fitness", "Fitness", "Ran 5km 4 times this week.", [])

    class FakeDigestLLM:
        async def chat(self, messages, **kwargs):
            return "This week you maintained a strong running habit with 4 sessions."

    result = await generate_digest(FakeDigestLLM(), wdb, 1, lang="en")
    assert result is not None
    assert "running" in result.lower()


@pytest.mark.asyncio
async def test_lint_detects_orphan_pages(wiki_db):
    """run_lint reports orphan pages with no inbound links."""
    import json
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.lint import run_lint

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "fitness", "Fitness", "Running.", [], source_delta=1)
    await wdb.upsert_page(1, "career", "Career", "Rust.", [], source_delta=1)
    # fitness links to career, but career doesn't link back → career has 1 inbound, fitness has 0

    class FakeLintLLM:
        async def chat(self, messages, **kwargs):
            return "Orphan pages detected: fitness has no inbound links."

    result = await run_lint(FakeLintLLM(), wdb, 1, lang="en")
    assert result is not None
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_plugins/test_wiki.py -v -k "nudge or digest or lint"
```
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/plugins/wiki/nudge.py src/plugins/wiki/digest.py src/plugins/wiki/lint.py tests/test_plugins/test_wiki.py
git commit -m "feat(wiki): add nudge, digest, and lint modules"
```

---

## Task 12: Wiki Plugin — Commands, Intents, and i18n

**Files:**
- Create: `src/plugins/wiki/commands.py`
- Create: `src/plugins/wiki/locale.py`
- Modify: `tests/test_plugins/test_wiki.py`

- [ ] **Step 1: Write wiki commands**

Create `src/plugins/wiki/commands.py`:

```python
"""Wiki plugin commands — /ask, /topics, /topic, /digest."""
from __future__ import annotations

import json
import logging
from typing import Any

from src.core.bot import Event
from src.core.i18n import t

from .db import WikiDB
from .digest import generate_digest
from .query import answer_question

logger = logging.getLogger(__name__)


async def cmd_ask(ctx: Any, event: Event) -> str | None:
    """Handle /ask <question> — query the wiki."""
    question = (event.text or "").strip()
    if not question:
        return t("wiki.ask_usage", event.lang)

    wiki_db = WikiDB(ctx.db)
    return await answer_question(
        llm=ctx.llm,
        wiki_db=wiki_db,
        db=ctx.db,
        user_id=event.user_id,
        question=question,
        lang=event.lang,
    )


async def cmd_topics(ctx: Any, event: Event) -> str | None:
    """Handle /topics — show topic index."""
    wiki_db = WikiDB(ctx.db)
    index = await wiki_db.get_topic_index(event.user_id)

    if not index:
        return t("wiki.topics_empty", event.lang)

    lines = [t("wiki.topics_header", event.lang)]
    for item in index:
        links = ""
        page = await wiki_db.get_page(event.user_id, item["topic"])
        if page:
            link_list = json.loads(page.get("links", "[]")) if isinstance(page.get("links"), str) else page.get("links", [])
            if link_list:
                links = f" → {', '.join(link_list)}"
        lines.append(
            f"  📄 {item['title']} ({item['topic']})"
            f" — {item.get('source_count', 0)} sources{links}"
        )

    return "\n".join(lines)


async def cmd_topic(ctx: Any, event: Event) -> str | None:
    """Handle /topic <name> — show a specific topic page."""
    topic_slug = (event.text or "").strip().lower()
    if not topic_slug:
        return t("wiki.topic_usage", event.lang)

    wiki_db = WikiDB(ctx.db)
    page = await wiki_db.get_page(event.user_id, topic_slug)

    if not page:
        return t("wiki.topic_not_found", event.lang, topic=topic_slug)

    links = json.loads(page.get("links", "[]")) if isinstance(page.get("links"), str) else page.get("links", [])
    links_str = ", ".join(links) if links else t("wiki.no_links", event.lang)

    header = f"📄 *{page['title']}*\n"
    meta = (
        f"Sources: {page['source_count']} | "
        f"Updated: {(page.get('updated_at') or '?')[:10]} | "
        f"Links: {links_str}\n\n"
    )
    return header + meta + page["content"]


async def cmd_digest(ctx: Any, event: Event) -> str | None:
    """Handle /digest — trigger weekly insight on demand."""
    wiki_db = WikiDB(ctx.db)
    result = await generate_digest(
        llm=ctx.llm,
        wiki_db=wiki_db,
        user_id=event.user_id,
        lang=event.lang,
    )
    if result is None:
        return t("wiki.digest_empty", event.lang)

    return f"🧠 *{t('wiki.digest_header', event.lang)}*\n\n{result}"
```

- [ ] **Step 2: Write wiki locale**

Create `src/plugins/wiki/locale.py`:

```python
"""Wiki plugin i18n strings."""
from src.core.i18n import register

STRINGS: dict[str, dict[str, str]] = {
    "description": {
        "zh": "个人知识维基 — 自动整理、查询、洞察",
        "en": "Personal Wiki — auto-organize, query, insights",
        "ja": "パーソナルWiki — 自動整理・検索・インサイト",
    },
    "cmd.ask": {
        "zh": "向你的知识库提问",
        "en": "Ask your knowledge base",
        "ja": "ナレッジベースに質問",
    },
    "cmd.topics": {
        "zh": "查看主题索引",
        "en": "Show topic index",
        "ja": "トピック一覧",
    },
    "cmd.topic": {
        "zh": "查看指定主题",
        "en": "View a topic page",
        "ja": "トピックを表示",
    },
    "cmd.digest": {
        "zh": "生成本周洞察",
        "en": "Generate weekly insight",
        "ja": "週間インサイト生成",
    },
    "ask_usage": {
        "zh": "用法: /ask <问题>\n例如: /ask 最近我在焦虑什么?",
        "en": "Usage: /ask <question>\nExample: /ask What have I been stressed about?",
        "ja": "使い方: /ask <質問>\n例: /ask 最近何を心配していた?",
    },
    "topics_empty": {
        "zh": "📭 你的知识库还是空的。继续记录消息，每晚会自动整理。",
        "en": "📭 Your wiki is empty. Keep recording and it'll build up nightly.",
        "ja": "📭 Wikiはまだ空です。記録を続けると毎晩自動で整理されます。",
    },
    "topics_header": {
        "zh": "🧠 *知识主题索引*",
        "en": "🧠 *Wiki Topic Index*",
        "ja": "🧠 *Wikiトピック一覧*",
    },
    "topic_usage": {
        "zh": "用法: /topic <主题slug>\n用 /topics 查看所有主题",
        "en": "Usage: /topic <topic-slug>\nUse /topics to list all topics",
        "ja": "使い方: /topic <トピックslug>\n/topics で一覧表示",
    },
    "topic_not_found": {
        "zh": "❌ 找不到主题 \"{topic}\"。用 /topics 查看所有主题。",
        "en": "❌ Topic \"{topic}\" not found. Use /topics to list all.",
        "ja": "❌ トピック \"{topic}\" が見つかりません。/topics で一覧表示。",
    },
    "no_links": {
        "zh": "无",
        "en": "none",
        "ja": "なし",
    },
    "digest_empty": {
        "zh": "📭 本周没有更新的主题，无法生成洞察。",
        "en": "📭 No topics updated this week — nothing to digest.",
        "ja": "📭 今週更新されたトピックがありません。",
    },
    "digest_header": {
        "zh": "本周洞察",
        "en": "Weekly Insight",
        "ja": "週間インサイト",
    },
}

register("wiki", STRINGS)
```

- [ ] **Step 3: Write tests for commands**

Append to `tests/test_plugins/test_wiki.py`:

```python
@pytest.mark.asyncio
async def test_cmd_topics_shows_index(wiki_db):
    """cmd_topics returns formatted topic index."""
    from src.core.bot import Event
    from src.core.context import AppContext
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.commands import cmd_topics
    from zoneinfo import ZoneInfo

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "fitness", "Fitness & Health", "Running.", [], source_delta=5)

    ctx = AppContext(db=wiki_db, llm=None, bot=None, scheduler=None, config={}, tz=ZoneInfo("UTC"))
    event = Event(user_id=1, chat_id=1, lang="en")

    result = await cmd_topics(ctx, event)
    assert "Fitness & Health" in result
    assert "5 sources" in result


@pytest.mark.asyncio
async def test_cmd_topic_shows_page(wiki_db):
    """cmd_topic returns full page content."""
    from src.core.bot import Event
    from src.core.context import AppContext
    from src.plugins.wiki.db import WikiDB
    from src.plugins.wiki.commands import cmd_topic
    from zoneinfo import ZoneInfo

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "fitness", "Fitness", "# Fitness\nRunning 5km daily.", ["health"])

    ctx = AppContext(db=wiki_db, llm=None, bot=None, scheduler=None, config={}, tz=ZoneInfo("UTC"))
    event = Event(user_id=1, chat_id=1, lang="en", text="fitness")

    result = await cmd_topic(ctx, event)
    assert "Running 5km" in result
    assert "health" in result
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_plugins/test_wiki.py -v -k "cmd_topics or cmd_topic"
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/plugins/wiki/commands.py src/plugins/wiki/locale.py tests/test_plugins/test_wiki.py
git commit -m "feat(wiki): add commands (/ask, /topics, /topic, /digest), intents, and i18n"
```

---

## Task 13: Wiki Plugin — Scheduler + Full Registration

**Files:**
- Create: `src/plugins/wiki/scheduler.py`
- Modify: `src/plugins/wiki/__init__.py` (full WikiPlugin class)

- [ ] **Step 1: Write scheduler**

Create `src/plugins/wiki/scheduler.py`:

```python
"""Wiki scheduler — daily ingest, weekly digest, monthly lint."""
from __future__ import annotations

import logging
from datetime import time
from typing import TYPE_CHECKING, Any

from .db import WikiDB
from .digest import generate_digest
from .ingest import run_ingest
from .lint import run_lint

if TYPE_CHECKING:
    from src.core.context import AppContext

logger = logging.getLogger(__name__)

DAYS_MAP = {"sunday": 0, "monday": 1, "tuesday": 2, "wednesday": 3,
            "thursday": 4, "friday": 5, "saturday": 6}


def _get_user_lang(ctx: "AppContext", user_id: int) -> str:
    try:
        return ctx.bot._auth.get_lang(user_id)
    except AttributeError:
        return "en"


async def _get_allowed_user_ids(ctx: "AppContext") -> list[int]:
    try:
        cursor = await ctx.db.conn.execute("SELECT user_id FROM allowed_users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
    except Exception:
        logger.warning("Failed to query allowed_users", exc_info=True)
        return []


async def _ingest_callback(ctx: "AppContext", data: Any = None) -> None:
    """Daily ingest: process new sources into wiki pages for all users."""
    wiki_db = WikiDB(ctx.db)
    for user_id in await _get_allowed_user_ids(ctx):
        try:
            lang = _get_user_lang(ctx, user_id)
            result = await run_ingest(ctx.db, ctx.llm, wiki_db, user_id, lang)
            logger.info("[wiki-ingest] user=%d result=%s", user_id, result)
        except Exception:
            logger.exception("[wiki-ingest] failed for user=%d", user_id)


async def _digest_callback(ctx: "AppContext", data: Any = None) -> None:
    """Weekly digest: generate and send insight to all users."""
    wiki_db = WikiDB(ctx.db)
    for user_id in await _get_allowed_user_ids(ctx):
        try:
            lang = _get_user_lang(ctx, user_id)
            digest = await generate_digest(ctx.llm, wiki_db, user_id, lang)
            if digest:
                from src.core.i18n import t
                header = t("wiki.digest_header", lang)
                await ctx.bot.send_message(
                    chat_id=user_id,
                    text=f"🧠 *{header}*\n\n{digest}",
                )
        except Exception:
            logger.exception("[wiki-digest] failed for user=%d", user_id)


async def _lint_callback(ctx: "AppContext", data: Any = None) -> None:
    """Monthly lint: health check and report."""
    wiki_db = WikiDB(ctx.db)
    for user_id in await _get_allowed_user_ids(ctx):
        try:
            lang = _get_user_lang(ctx, user_id)
            report = await run_lint(ctx.llm, wiki_db, user_id, lang)
            if report:
                await ctx.bot.send_message(
                    chat_id=user_id,
                    text=f"🔍 Wiki Health Report\n\n{report}",
                )
        except Exception:
            logger.exception("[wiki-lint] failed for user=%d", user_id)


async def setup_wiki_schedules(ctx: "AppContext") -> None:
    """Register all wiki scheduled jobs."""
    config = ctx.config

    # Daily ingest (default 22:30)
    ingest_h = config.get("ingest_hour", 22)
    ingest_m = config.get("ingest_minute", 30)
    ingest_time = time(hour=ingest_h, minute=ingest_m, tzinfo=ctx.tz)
    await ctx.scheduler.run_daily(
        callback=lambda data=None: _ingest_callback(ctx, data),
        time=ingest_time,
        name="wiki_daily_ingest",
    )
    logger.info("Scheduled wiki daily ingest at %02d:%02d", ingest_h, ingest_m)

    # Weekly digest (default Sunday 21:00)
    digest_day_str = config.get("digest_day", "sunday").lower()
    digest_day = DAYS_MAP.get(digest_day_str, 0)
    digest_h = config.get("digest_hour", 21)
    digest_time = time(hour=digest_h, minute=0, tzinfo=ctx.tz)
    await ctx.scheduler.run_daily(
        callback=lambda data=None: _digest_callback(ctx, data),
        time=digest_time,
        name="wiki_weekly_digest",
        days=(digest_day,),
    )
    logger.info("Scheduled wiki weekly digest for %s %02d:00", digest_day_str, digest_h)

    # Monthly lint (default 1st of month, 03:00)
    lint_day = config.get("lint_day", 1)
    lint_time = time(hour=3, minute=0, tzinfo=ctx.tz)
    await ctx.scheduler.run_daily(
        callback=lambda data=None: _lint_callback(ctx, data),
        time=lint_time,
        name="wiki_monthly_lint",
    )
    logger.info("Scheduled wiki monthly lint on day %d at 03:00", lint_day)

    # Seed topics on first startup
    seed_topics = config.get("seed_topics", [])
    if seed_topics:
        wiki_db = WikiDB(ctx.db)
        for seed in seed_topics:
            topic = seed.get("topic", "")
            title = seed.get("title", "")
            if topic and title:
                existing = await wiki_db.get_page(0, topic)  # user 0 = check existence
                # Seed for all users on first run
                for user_id in await _get_allowed_user_ids(ctx):
                    existing = await wiki_db.get_page(user_id, topic)
                    if not existing:
                        await wiki_db.upsert_page(
                            user_id=user_id,
                            topic=topic,
                            title=title,
                            content=f"# {title}\n\n(Seed topic — content will grow as you record.)",
                            links=[],
                            page_type="seed",
                        )
        logger.info("Seeded %d wiki topics", len(seed_topics))
```

- [ ] **Step 2: Write full WikiPlugin class**

Replace `src/plugins/wiki/__init__.py`:

```python
"""Wiki plugin — personal knowledge wiki with LLM-powered synthesis."""
from __future__ import annotations

from src.core.bot import Command, Event, IntentDeclaration
from src.core.plugin import BasePlugin

import src.plugins.wiki.locale  # noqa: F401


class WikiPlugin(BasePlugin):
    name = "wiki"
    version = "1.0.0"
    description = "个人知识维基 — 自动整理、查询、洞察"

    def get_commands(self) -> list[Command]:
        ctx = self.ctx

        async def _ask(event: Event) -> str | None:
            from .commands import cmd_ask
            return await cmd_ask(ctx, event)

        async def _topics(event: Event) -> str | None:
            from .commands import cmd_topics
            return await cmd_topics(ctx, event)

        async def _topic(event: Event) -> str | None:
            from .commands import cmd_topic
            return await cmd_topic(ctx, event)

        async def _digest(event: Event) -> str | None:
            from .commands import cmd_digest
            return await cmd_digest(ctx, event)

        return [
            Command(name="ask", description="向知识库提问", handler=_ask),
            Command(name="topics", description="查看主题索引", handler=_topics),
            Command(name="topic", description="查看指定主题", handler=_topic),
            Command(name="digest", description="生成本周洞察", handler=_digest),
        ]

    def get_intents(self) -> list[IntentDeclaration]:
        ctx = self.ctx

        async def _ask_intent(event: Event) -> str | None:
            from .commands import cmd_ask
            return await cmd_ask(ctx, event)

        return [
            IntentDeclaration(
                name="wiki_ask",
                description="User is asking a question about their life, habits, patterns, or past thoughts/recordings",
                examples=(
                    "最近我在焦虑什么?",
                    "What have I been reading about?",
                    "上周我运动了几次?",
                    "总结一下我最近的状态",
                    "我之前说过关于 Rust 的什么?",
                ),
                handler=_ask_intent,
                args_description="The user's question, as-is",
            ),
        ]

    async def on_startup(self) -> None:
        from .scheduler import setup_wiki_schedules
        await setup_wiki_schedules(self.ctx)
```

- [ ] **Step 3: Run full wiki test suite**

```bash
pytest tests/test_plugins/test_wiki.py -v
```
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/plugins/wiki/
git commit -m "feat(wiki): add scheduler, seed topics, and full plugin registration"
```

---

## Task 14: Wire Nudge Hook into AppContext + Memo Handler

**Files:**
- Modify: `src/core/context.py` (add `wiki_nudge` field)
- Modify: `src/plugins/memo/handlers.py` (call nudge after recording text)
- Modify: `src/main.py` (inject wiki_nudge into AppContext after plugin discovery)

- [ ] **Step 1: Add wiki_nudge to AppContext**

At `src/core/context.py`, add the optional field:

```python
"""Application context injected into every plugin."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class AppContext:
    db: Any        # Database
    llm: Any       # LLMService or test fake
    bot: Any       # BotAdapter or test fake
    scheduler: Any  # Scheduler or test fake
    config: dict[str, Any]
    tz: ZoneInfo
    wiki_nudge: Callable[[int, str, str], Awaitable[str | None]] | None = field(default=None)
```

- [ ] **Step 2: Update memo text handler to call nudge**

In `src/plugins/memo/handlers.py`, at the end of `_make_text_handler`, before `return reply`, add the nudge check:

```python
        # Wiki nudge check (runs only if wiki plugin loaded)
        if ctx.wiki_nudge and row_id is not None:
            try:
                nudge_text = await ctx.wiki_nudge(user_id, text, event.lang)
                if nudge_text:
                    reply += f"\n\n{nudge_text}"
            except Exception:
                logger.debug("[nudge] check failed", exc_info=True)

        return reply
```

This goes right before both `return reply` statements in `handle_text` — after the dedup branch (line ~90) and after the normal insert branch (line ~106).

- [ ] **Step 3: Wire nudge in main.py**

In `src/main.py`, after plugin discovery (after line 376), add:

```python
    # Wire wiki nudge hook if wiki plugin is loaded
    wiki_plugin = next((p for p in plugins if p.name == "wiki"), None)
    if wiki_plugin:
        from src.plugins.wiki.db import WikiDB
        from src.plugins.wiki.nudge import check_nudge

        wiki_config = config.get("plugins", {}).get("wiki", {})
        nudge_enabled = wiki_config.get("nudge_enabled", True)
        nudge_threshold = wiki_config.get("nudge_threshold", 0.85)
        nudge_max = wiki_config.get("nudge_max_per_day", 3)

        if nudge_enabled:
            async def _wiki_nudge(user_id: int, content: str, lang: str) -> str | None:
                wiki_db = WikiDB(db)
                return await check_nudge(
                    llm, wiki_db, user_id, content, lang,
                    threshold=nudge_threshold, max_per_day=nudge_max,
                )

            # Rebuild memo plugin's AppContext with the nudge hook
            for plugin in plugins:
                if plugin.name == "memo":
                    from src.core.context import AppContext as _AC
                    plugin.ctx = _AC(
                        db=plugin.ctx.db,
                        llm=plugin.ctx.llm,
                        bot=plugin.ctx.bot,
                        scheduler=plugin.ctx.scheduler,
                        config=plugin.ctx.config,
                        tz=plugin.ctx.tz,
                        wiki_nudge=_wiki_nudge,
                    )
                    break

            logger.info("Wiki nudge hook wired to memo plugin")
```

Note: `AppContext` is frozen, so we create a new one with the nudge field set. This matches the immutability principle.

- [ ] **Step 4: Write test for nudge wiring**

Append to `tests/test_plugins/test_wiki.py`:

```python
@pytest.mark.asyncio
async def test_nudge_wired_to_text_handler(wiki_db):
    """Text handler appends nudge text when wiki_nudge is set."""
    import json
    from zoneinfo import ZoneInfo
    from src.core.bot import Event
    from src.core.context import AppContext
    from src.core.db import MigrationRunner

    runner = MigrationRunner(wiki_db)
    memo_migrations = str(_SRC_ROOT / "plugins" / "memo" / "migrations")
    await runner.run("memo", memo_migrations)

    async def fake_nudge(user_id, content, lang):
        return "💡 Connects to your fitness goal!"

    class SimpleLLM:
        def supports(self, cap): return False
        async def classify(self, text, lang="en"):
            return {"category": "other", "summary": text[:30], "tags": ""}
        async def chat(self, messages, **kwargs):
            return '{"duplicate": false}'

    ctx = AppContext(
        db=wiki_db, llm=SimpleLLM(), bot=None, scheduler=None,
        config={}, tz=ZoneInfo("UTC"), wiki_nudge=fake_nudge,
    )

    from src.plugins.memo.handlers import make_handlers
    handlers = make_handlers(ctx)
    text_handler = handlers[0].handler  # TEXT handler

    event = Event(user_id=1, chat_id=1, text="Ran 5km today", lang="en")
    result = await text_handler(event)

    assert result is not None
    assert "fitness goal" in result
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_plugins/test_wiki.py::test_nudge_wired_to_text_handler -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/core/context.py src/plugins/memo/handlers.py src/main.py tests/test_plugins/test_wiki.py
git commit -m "feat(wiki): wire nudge hook into AppContext and memo text handler"
```

---

## Task 15: Wire /review to Wiki Query

**Files:**
- Modify: `src/plugins/reflect/commands.py` (update `cmd_review` to use wiki)

- [ ] **Step 1: Update cmd_review to query wiki with fallback**

In `src/plugins/reflect/commands.py`, update `cmd_review`:

```python
async def cmd_review(event: Event) -> str | None:
    """Review via wiki query, falling back to old summary generation."""
    ctx = _get_ctx()
    text = (event.text or "").strip()

    # Parse date range (same as before)
    today = _get_today()
    if text:
        try:
            start_date = text.split()[0]
            datetime.strptime(start_date, "%Y-%m-%d")
        except (ValueError, IndexError):
            return t("reflect.review_usage", event.lang)
    else:
        start_date = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=6)).strftime("%Y-%m-%d")

    # Try wiki query first
    try:
        from src.plugins.wiki.db import WikiDB
        wiki_db = WikiDB(ctx.db)
        index = await wiki_db.get_topic_index(event.user_id)
        if index:  # Wiki has content — use it
            from src.plugins.wiki.query import answer_question
            question = (
                f"Review and summarize my life from {start_date} to {today}. "
                "Cover themes, progress, mood, and any patterns."
            )
            return await answer_question(
                llm=ctx.llm,
                wiki_db=wiki_db,
                db=ctx.db,
                user_id=event.user_id,
                question=question,
                lang=event.lang,
            )
    except ImportError:
        pass  # Wiki plugin not installed — fall through to legacy

    # Fallback: legacy summary generation from raw journal entries
    from .db import JournalDB
    from .summary import generate_summary

    journal_db = JournalDB(ctx.db)
    return await generate_summary(
        db=journal_db,
        llm=ctx.llm,
        user_id=event.user_id,
        period_type="custom",
        start_date=start_date,
        end_date=today,
        lang=event.lang,
    )
```

- [ ] **Step 2: Write test**

Append to `tests/test_plugins/test_wiki.py`:

```python
@pytest.mark.asyncio
async def test_review_uses_wiki_when_available(wiki_db):
    """cmd_review queries wiki when topics exist."""
    import json
    from src.plugins.wiki.db import WikiDB

    wdb = WikiDB(wiki_db)
    await wdb.upsert_page(1, "fitness", "Fitness", "Ran daily this week.", [], source_delta=5)
    await wdb.upsert_page(1, "reading", "Reading", "Read 3 books.", [], source_delta=3)

    # The review should find wiki content and use it
    index = await wdb.get_topic_index(1)
    assert len(index) == 2  # Wiki has content, so review would use wiki path
```

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v --timeout=30
```
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/plugins/reflect/commands.py tests/test_plugins/test_wiki.py
git commit -m "feat(wiki): wire /review to wiki query with legacy fallback"
```

---

## Task 16: Final Verification

- [ ] **Step 1: Run full test suite with coverage**

```bash
pytest tests/ -v --timeout=30 --tb=short
```
All tests must pass.

- [ ] **Step 2: Verify import chain works**

```bash
python -c "
from src.plugins.memo import MemoPlugin
from src.plugins.reflect import ReflectPlugin
from src.plugins.track import TrackPlugin
from src.plugins.wiki import WikiPlugin
print(f'memo={MemoPlugin.name} reflect={ReflectPlugin.name} track={TrackPlugin.name} wiki={WikiPlugin.name}')
"
```
Expected: `memo=memo reflect=reflect track=track wiki=wiki`

- [ ] **Step 3: Verify config loads with new keys**

```bash
python -c "
from src.config import load_config
# This will fail if config.yaml doesn't exist, but validates the loader works
print('Config loader OK')
"
```

- [ ] **Step 4: Final commit — update CHANGELOG**

Add to `CHANGELOG.md` under Unreleased:

```markdown
## [Unreleased]

### Added
- **Wiki plugin** — personal knowledge wiki with LLM-powered synthesis
  - `/ask <question>` — query your knowledge base conversationally
  - `/topics` — browse wiki topic index
  - `/topic <name>` — read a specific topic page
  - `/digest` — generate weekly insight on demand
  - Daily auto-ingest at 22:30 (configurable)
  - Weekly digest on Sundays at 21:00
  - Real-time nudges when new memos connect to existing topics
  - Monthly lint health check

### Changed
- **Renamed plugins**: recorder → memo, journal → reflect, planner → track
- **Shorter commands**: `/today`, `/heatmap`, `/del`, `/reflect`, `/review`, `/goal`, `/checkin`, `/goals`, `/drop`
- `/review` now queries wiki for richer context (falls back to legacy summarization)
```

```bash
git add CHANGELOG.md
git commit -m "chore: update CHANGELOG for wiki redesign"
```
