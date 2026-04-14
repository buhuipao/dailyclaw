# DailyClaw Wiki Redesign — Design Spec

**Date**: 2026-04-14
**Status**: Draft
**Inspired by**: [Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

---

## 1. Vision

Transform DailyClaw from isolated recording/journaling/planning silos into a
**personal LLM Wiki** — a three-layer system where raw sources are
incrementally compiled into structured, interlinked knowledge that the user
can query conversationally.

## 2. Three-Layer Architecture

```
┌─────────────────────────────────────────────────────┐
│  Layer 3: SCHEMA (config.yaml)                      │
│  Seed topics, schedules, thresholds, rules          │
├─────────────────────────────────────────────────────┤
│  Layer 2: THE WIKI (wiki_pages table)               │
│  LLM-maintained topic pages, cross-linked,          │
│  incrementally updated — the "compiled" knowledge   │
├─────────────────────────────────────────────────────┤
│  Layer 1: RAW SOURCES (messages, journal_entries,   │
│           plan_checkins tables)                      │
│  Immutable records: text, photos, links, voice,     │
│  reflections, check-ins                             │
└─────────────────────────────────────────────────────┘
```

## 3. Plugin Reorganization

### Before → After

| Before | After | Role |
|--------|-------|------|
| `recorder` | `memo` | Layer 1: Raw source capture |
| _(new)_ | `wiki` | Layer 2: Knowledge synthesis + query |
| `journal` | `reflect` | Ritual: Structured reflection → wiki source |
| `planner` | `track` | Ritual: Goal/habit tracking → wiki source |

### Directory Structure

```
src/plugins/
├── memo/                # Layer 1: Raw source capture
│   ├── __init__.py      # MemoPlugin(BasePlugin)
│   ├── commands.py      # /today, /heatmap, /del
│   ├── handlers.py      # TEXT, PHOTO, VOICE, VIDEO handlers
│   ├── dedup.py         # Content + image dedup
│   ├── url.py           # URL extraction + summarization
│   ├── locale.py        # i18n
│   ├── retry.py         # Message queue retry
│   ├── scheduler.py     # Retry scheduler
│   └── migrations/
│       ├── 001_init.sql
│       └── 002_add_deleted_at.sql
│
├── wiki/                # Layer 2: Knowledge synthesis
│   ├── __init__.py      # WikiPlugin(BasePlugin)
│   ├── commands.py      # /ask, /topics, /topic, /digest
│   ├── ingest.py        # Batch ingest: sources → wiki pages
│   ├── query.py         # Two-stage retrieval + LLM answer
│   ├── nudge.py         # Real-time connection detection
│   ├── digest.py        # Weekly insight generation
│   ├── lint.py          # Health check: contradictions, gaps
│   ├── db.py            # WikiDB helper
│   ├── locale.py        # i18n
│   ├── scheduler.py     # Ingest, digest, lint schedules
│   └── migrations/
│       └── 001_init.sql
│
├── reflect/             # Ritual: Structured reflection
│   ├── __init__.py      # ReflectPlugin(BasePlugin)
│   ├── commands.py      # /reflect, /review, /cancel
│   ├── db.py            # JournalDB (reused)
│   ├── locale.py        # i18n
│   ├── scheduler.py     # Reflection reminder
│   └── migrations/
│       └── 001_init.sql
│
└── track/               # Ritual: Goal/habit tracking
    ├── __init__.py      # TrackPlugin(BasePlugin)
    ├── commands.py      # /goal, /checkin, /goals, /drop
    ├── db.py            # PlannerDB (reused)
    ├── locale.py        # i18n
    ├── scheduler.py     # Check-in reminders
    └── migrations/
        └── 001_init.sql
```

## 4. Command Reference

### memo (was: recorder)

| Command | Description | Was |
|---------|-------------|-----|
| `/today` | View today's memos | `/recorder_today` |
| `/heatmap` | 90-day contribution heatmap | `/recorder_list` |
| `/del <id>` | Delete a memo | `/recorder_del` |

### wiki (new)

| Command | Description |
|---------|-------------|
| `/ask <question>` | Query wiki conversationally |
| `/topics` | Show topic index with summaries |
| `/topic <name>` | Read a specific topic page |
| `/digest` | Trigger weekly insight on demand |

### reflect (was: journal)

| Command | Description | Was |
|---------|-------------|-----|
| `/reflect` | Start Zeng Guofan 4-question reflection | `/journal_start` |
| `/review [period]` | Review via wiki query | `/journal_review` |
| `/cancel` | Cancel ongoing reflection | `/journal_cancel` |

Removed: `/journal_today` — replaced by `/today` (memo) + wiki daily page.

### track (was: planner)

| Command | Description | Was |
|---------|-------------|-----|
| `/goal <desc>` | Create a goal/habit | `/planner_add` |
| `/checkin <desc>` | Check in on a goal | `/planner_checkin` |
| `/goals` | List goals + wiki insights | `/planner_list` |
| `/drop <name>` | Archive a goal | `/planner_del` |

### Meta & Admin (unchanged)

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Command list (admin-aware) |
| `/lang <zh\|en\|ja>` | Switch language |
| `/invite <id>` | Admin: invite user |
| `/kick <id>` | Admin: remove user |
| `/stats` | Admin: user stats |

## 5. Database Schema

### Existing tables (unchanged)

- `messages` — raw memos (text, photo, voice, video, link)
- `journal_entries` — reflection answers
- `plan_checkins` — goal check-ins
- `plans` — goal definitions
- `allowed_users` — user access
- `message_queue` — async processing queue

### New tables

#### `wiki_pages`

```sql
CREATE TABLE wiki_pages (
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
CREATE INDEX idx_wiki_pages_user ON wiki_pages(user_id, updated_at);
```

- `topic`: URL-friendly slug, e.g. `"fitness"`, `"career"`, `"reading-notes"`
- `title`: Display name, e.g. `"Fitness & Health"`
- `content`: Markdown body, maintained by LLM
- `links`: JSON array of linked topic slugs, e.g. `["career", "reading"]`
- `page_type`: `"seed"` (from config), `"organic"` (LLM-created), `"plan"` (linked to a goal)
- `source_count`: How many raw sources have been ingested into this page
- `last_ingest`: Watermark — when this page was last updated by ingest

#### `wiki_log`

```sql
CREATE TABLE wiki_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    op         TEXT NOT NULL,
    detail     TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_wiki_log_user ON wiki_log(user_id, created_at);
```

- `op`: `"ingest"`, `"query"`, `"nudge"`, `"lint"`, `"digest"`
- `detail`: Free-form description of what happened

## 6. Wiki Operations

### 6.1 Ingest

**When**: Daily at configurable time (default 22:30). Replaces auto-journal.

**Input**: All unprocessed sources since the wiki's global `last_ingest` watermark,
pulled from `messages`, `journal_entries`, and `plan_checkins` tables.

**LLM prompt structure**:
```
System: You are the DailyClaw wiki editor. Given new sources and the
        current topic index, update the wiki.

Existing topics:
- fitness: "Fitness & Health" (last updated 2026-04-13, 12 sources)
- career: "Career & Growth" (last updated 2026-04-12, 8 sources)
- ...

New sources (7 items):
1. [memo 08:00] 早起跑了5公里，感觉不错
2. [memo 12:30] 读了一篇关于 Rust 异步的好文章 (summary: ...)
3. [checkin 08:00] fitness: 晨跑5km
4. [reflect 22:10] 今日读书: 读了 Rust 异步文章，对 Future trait 有了新理解
...

Return JSON array:
[
  {
    "topic": "fitness",
    "title": "Fitness & Health",
    "action": "update",
    "content": "full updated page content in markdown",
    "links": ["daily-routine"],
    "reason": "Added morning run entry, noted 3-day streak"
  },
  {
    "topic": "rust-learning",
    "title": "Rust Learning Notes",
    "action": "create",
    "content": "...",
    "links": ["career", "reading"],
    "reason": "New topic emerged from article + reflection"
  }
]

Rules:
- Update 3-10 pages per batch
- Create new topics ONLY when no existing topic fits
- Preserve existing content — append/revise, never discard
- Cross-link related topics
- Write in the user's language
```

**After ingest**: Update `wiki_pages`, bump `source_count`, set `last_ingest`,
write `wiki_log` entry.

### 6.2 Query (`/ask`)

**Two-stage retrieval**:

1. **Topic selection** (cheap): LLM reads question + topic index
   (topic slugs + titles + one-line summaries ≈ small payload).
   Returns 3-5 relevant topic slugs.

2. **Answer generation** (focused): Fetch full content of selected pages.
   LLM generates answer grounded in wiki content.

**Fallback**: If wiki pages are insufficient, fall back to searching raw
`messages` table for the last 30 days. This handles queries about things
not yet ingested.

**Logging**: Every query + answer is logged to `wiki_log` with `op="query"`.
Valuable answers can be filed back as new wiki content in the next ingest.

### 6.3 Nudge (real-time)

**When**: After each memo is recorded (runs in parallel with intent routing).

**How**: Lightweight LLM call — memo text + topic index only (no full pages).
LLM returns `{connected_topic, confidence, reason}`.

**Threshold**: Only nudge when confidence >= 0.85 (configurable).

**Output**: Inline message appended to recording confirmation:
```
✅ Recorded.
💡 This connects to your "career" topic — you had similar thoughts on April 3 about switching to systems programming.
```

**Rate limit**: Max 3 nudges per day per user to prevent fatigue.

### 6.4 Digest (weekly)

**When**: Weekly on configurable day (default Sunday 21:00).

**Input**: All wiki pages updated in the past 7 days.

**LLM prompt**: Generate a concise weekly insight covering:
- Recurring themes
- Notable connections across topics
- Progress on tracked goals
- Emerging patterns or shifts
- One actionable suggestion

**Output**: Sent as a Telegram message. Also saved as a `wiki_log` entry
with `op="digest"`.

### 6.5 Lint (monthly)

**When**: Monthly (1st of month) or on-demand.

**Checks**:
- Contradictions between pages
- Stale pages (no updates in 30+ days)
- Orphan pages (no inbound links)
- Topics that should be merged
- Gaps (frequently mentioned concepts with no dedicated page)

**Output**: Brief health report sent to user.

## 7. Plugin Interconnection

### Source Registry Pattern

The wiki plugin reads from all source tables without other plugins
knowing it exists. No coupling required.

```python
SOURCE_TABLES = [
    {
        "name": "memos",
        "table": "messages",
        "content_col": "content",
        "meta_col": "metadata",
        "time_col": "created_at",
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
        "time_col": "created_at",
    },
]
```

### Coupling Matrix

| Plugin | Knows about wiki? | Wiki reads from it? |
|--------|-------------------|---------------------|
| memo | Only nudge hook (via AppContext) | Yes — `messages` table |
| reflect | No | Yes — `journal_entries` table |
| track | No | Yes — `plan_checkins` table |
| wiki | Reads all source tables | Maintains `wiki_pages` |

### Nudge Hook

The only cross-plugin coupling. Injected via `AppContext.wiki_nudge`
(optional callable). If wiki plugin is not loaded, the hook is `None`
and memo skips it.

```python
# In memo handler, after recording:
if ctx.wiki_nudge:
    nudge_text = await ctx.wiki_nudge(user_id, content, lang)
    if nudge_text:
        result += f"\n\n{nudge_text}"
```

## 8. Intent Router Updates

### New intents (wiki plugin)

```python
IntentDeclaration(
    name="wiki_ask",
    description="User is asking a question about their life, habits, "
                "patterns, or past thoughts/recordings",
    examples=(
        "最近我在焦虑什么?",
        "What have I been reading about?",
        "上周我运动了几次?",
        "总结一下我最近的状态",
        "我之前说过关于 Rust 的什么?",
    ),
    handler=cmd_ask,
    args_description="The user's question, as-is",
)
```

### Updated intents (reflect + track)

Reflect and track intents stay the same, just with updated handler
references matching the renamed plugins.

### Routing priority

The intent router distinguishes:
- **Recording** ("跑了5公里") → memo + track checkin
- **Questioning** ("最近跑了几次?") → wiki ask
- **Commanding** ("/goals") → track

Questions are identified by: question marks, interrogative words
(什么/为什么/how/what/when), "总结"/"review"/"summarize" patterns.

## 9. Configuration (config.yaml)

```yaml
plugins:
  memo:
    dedup_window: 10              # seconds

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
    lint_day: 1                   # day of month

  reflect:
    remind_hour: 21
    remind_minute: 0
    template: "zeng_guofan"

  track: {}
```

## 10. Migration Strategy

This is a **rename + add** migration, not a destructive rewrite.

### Phase 1: Rename plugins
- `recorder/` → `memo/` (rename directory, update class name, register new command names)
- `journal/` → `reflect/` (rename directory, update class name, register new command names)
- `planner/` → `track/` (rename directory, update class name, register new command names)
- Database tables stay the same — no data migration needed
- Config keys update: `recorder` → `memo`, `journal` → `reflect`, `planner` → `track`

### Phase 2: Add wiki plugin
- Create `wiki/` plugin with migrations
- Seed topics created on first startup
- First ingest processes all historical sources (one-time bulk ingest)
- Bulk ingest is chunked: process 1 week at a time to stay within LLM context
  limits and avoid timeouts. For a user with 6 months of history, this runs
  ~26 sequential ingest cycles on first startup (background, non-blocking).

### Phase 3: Wire nudge hook
- Add optional `wiki_nudge` to `AppContext`
- Memo handler calls it after recording

### Phase 4: Wire `/review` to wiki
- `/review` in reflect plugin queries wiki instead of generating one-off summaries
- Falls back to old behavior if wiki has insufficient data

## 11. LLM Cost Considerations

| Operation | Frequency | Input tokens (est.) | Output tokens (est.) |
|-----------|-----------|---------------------|----------------------|
| Ingest | 1x/day | ~2000 (sources + index) | ~1500 (page updates) |
| Query | ~3x/day | ~1500 (question + pages) | ~500 (answer) |
| Nudge | per memo (~10/day) | ~500 (memo + index) | ~100 (yes/no + reason) |
| Digest | 1x/week | ~3000 (week's pages) | ~800 (insight) |
| Lint | 1x/month | ~5000 (all pages) | ~500 (report) |

**Daily estimate**: ~8,500 input + ~2,500 output tokens for wiki operations.
At GPT-4o-mini pricing (~$0.15/1M input, ~$0.60/1M output): **~$0.003/day**.
Negligible cost addition.

Nudge is the most frequent call but also the cheapest (topic index only,
no full page reads). If cost is a concern, nudge can be disabled first.
