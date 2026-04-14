# Changelog

All notable changes to DailyClaw are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- **Wiki plugin** -- personal knowledge wiki with LLM-powered synthesis
  - `/ask <question>` -- query your knowledge base conversationally
  - `/topics` -- browse wiki topic index
  - `/topic <name>` -- read a specific topic page
  - `/digest` -- generate weekly insight on demand
  - Daily auto-ingest at 22:30 (configurable) -- processes memos, reflections, and check-ins into wiki pages
  - Weekly digest on Sundays at 21:00 -- recurring themes, connections, progress, suggestions
  - Real-time nudges when new memos connect to existing topics (threshold 0.85, max 3/day)
  - Monthly lint health check -- detects contradictions, stale pages, orphans, merge candidates
  - Seed topics configurable in config.yaml
  - `wiki_ask` intent for natural language questions via intent router

### Changed
- **Renamed plugins**: recorder -> memo, journal -> reflect, planner -> track
- **Shorter commands**: `/today`, `/heatmap`, `/del`, `/reflect`, `/review`, `/goal`, `/checkin`, `/goals`, `/drop`
- `/review` now queries wiki for richer context (falls back to legacy summarization)
- `AppContext` gains optional `wiki_nudge` hook for cross-plugin nudge wiring
- Core migration 004 renames schema_versions entries for renamed plugins

### Previous: Intent Router

- **Intent Router** -- LLM-powered natural language routing to plugins, similar to function calling
  - Users can send plain messages instead of `/commands`; the LLM determines which plugin to invoke
  - Each plugin declares intents with `get_intents()` and per-user context with `get_intent_context()`
  - Router extracts arguments (like `brush_teeth` from "帮我删除刷牙计划") and passes clean input to handlers
  - Confidence threshold 0.7 for auto-dispatch; multi-dispatch supported for multi-intent messages
  - Fallback hint (zh/en/ja) when no intent matched, suggesting `/help` or more specific input
- **Always-record** -- every text message is recorded by the Recorder in parallel with intent routing
  - Messages are never lost: Recorder and IntentRouter run via `asyncio.gather`
  - If a plugin action matches, the user sees the plugin result; the recording happens silently
- **`IntentDeclaration`** dataclass in `core/bot.py` with `args_description` for LLM arg extraction
- **`route_intent()`** method on `LLMService` -- single LLM call that returns action + confidence + args
- **Planner intents**: `planner_checkin`, `planner_add`, `planner_list`, `planner_del`
- **Journal intents**: `journal_today`
- **Intent router locale** (`core/intent_router_locale.py`) with zh/en/ja fallback hint strings
- 21 new tests for IntentRouter (always-record, args extraction, multi-dispatch, fallback, error handling)

### Changed
- `BasePlugin` now has optional `get_intents()` and `get_intent_context()` methods
- Planner command handler factories renamed from `_cmd_planner_*` to `cmd_planner_*` (public API)
- `main.py` handler registration intercepts TEXT handlers and wraps them with IntentRouter
- Updated `README.md` with Intent Router section and architecture diagram
- Updated `docs/creating-plugins.md` with intent declaration guide

## [1.0.0] - 2026-04-08

### Added
- Plugin-based architecture with auto-discovery, per-plugin DB migrations, and i18n
- **Recorder plugin** -- auto-classify, semantic dedup, URL summary, vision analysis, media storage
- **Journal plugin** -- Zeng Guofan four-question reflection, auto-journal at 23:50, weekly/monthly summaries
- **Planner plugin** -- natural language plan creation, smart check-in matching, scheduled reminders
- Telegram adapter with ACK-first dispatch and message queue reliability
- Multi-modal LLM service (text + vision) with OpenAI-compatible API
- i18n support: English, Chinese, Japanese
- Heatmap generation for recording history
- `@with_retry` decorator with fixed/exponential/jitter backoff strategies
- Docker and Docker Compose deployment
