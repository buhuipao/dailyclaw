# Creating a Plugin

DailyClaw uses a plugin system that auto-discovers plugins at startup. Each plugin is a self-contained Python package with its own commands, message handlers, database migrations, and translations.

## Plugin Structure

```
src/plugins/your_plugin/
  __init__.py          # Plugin class (required)
  commands.py          # Command handlers
  locale.py            # i18n translations (zh/en/ja)
  migrations/
    001_init.sql       # Database schema
```

## Step 1: Create the Plugin Class

Every plugin must subclass `BasePlugin` and implement `get_commands()`.

```python
# src/plugins/your_plugin/__init__.py
from src.core.bot import Command
from src.core.plugin import BasePlugin


class YourPlugin(BasePlugin):
    name = "your_plugin"
    version = "1.0.0"
    description = "Short description of your plugin"

    def get_commands(self) -> list[Command]:
        from .commands import make_commands
        return make_commands(self.ctx)
```

### Available Overrides

| Method | Purpose | Required |
|--------|---------|----------|
| `get_commands()` | Return bot commands (`/your_command`) | Yes |
| `get_handlers()` | Return message handlers (text, photo, voice, video) | No |
| `get_conversations()` | Return multi-turn conversation flows | No |
| `get_intents()` | Return natural language intents (LLM routing) | No |
| `get_intent_context(user_id)` | Return per-user context for intent routing | No |
| `on_startup()` | Called once after plugin loads (schedule jobs, etc.) | No |
| `on_shutdown()` | Called once before bot stops (cleanup) | No |

## Step 2: Write Command Handlers

Handlers receive an `Event` and return a string (or `None`).

```python
# src/plugins/your_plugin/commands.py
from __future__ import annotations

from src.core.bot import Command, Event
from src.core.i18n import t

import src.plugins.your_plugin.locale  # noqa: F401


def make_commands(ctx) -> list[Command]:
    return [
        Command(
            name="your_command",
            description="What it does",
            handler=_make_handler(ctx),
        ),
    ]


def _make_handler(ctx):
    async def handler(event: Event) -> str | None:
        # event.user_id  — Telegram user ID
        # event.chat_id  — Telegram chat ID
        # event.text     — command arguments (prefix stripped)
        # event.lang     — user's language ("en", "zh", "ja")
        # ctx.db         — Database (aiosqlite)
        # ctx.llm        — LLMService
        # ctx.bot        — BotAdapter (send_message, etc.)
        # ctx.scheduler  — Scheduler (run_daily, run_repeating)
        # ctx.config     — Plugin-specific config from config.yaml
        # ctx.tz         — Timezone (ZoneInfo)

        return t("your_plugin.hello", event.lang, name="world")

    return handler
```

### Return Types

| Return | Behavior |
|--------|----------|
| `str` | Bot edits the ACK message with this text |
| `None` | Bot deletes the ACK (handler managed its own reply) |
| `dict` with `"photo"` key | Bot sends photo: `{"photo": bytes, "caption": "..."}` |
| `tuple (str, True)` | Conversation flow: send text and end conversation |

## Step 3: Add Database Migrations

Place numbered SQL files in `migrations/`. They run automatically at startup.

```sql
-- src/plugins/your_plugin/migrations/001_init.sql
CREATE TABLE IF NOT EXISTS your_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_your_table_user
    ON your_table(user_id);
```

Migrations are tracked per-plugin. Add new files (`002_add_column.sql`, etc.) for schema changes.

## Step 4: Add Translations (i18n)

Create a `locale.py` that registers translations under your plugin's namespace.

```python
# src/plugins/your_plugin/locale.py
from src.core.i18n import register

STRINGS: dict[str, dict[str, str]] = {
    "hello": {
        "zh": "你好 {name}!",
        "en": "Hello {name}!",
        "ja": "こんにちは {name}!",
    },
    "description": {
        "zh": "你的插件描述",
        "en": "Your plugin description",
        "ja": "プラグインの説明",
    },
}

register("your_plugin", STRINGS)
```

Use translations in handlers:

```python
from src.core.i18n import t

t("your_plugin.hello", event.lang, name="world")
# → "Hello world!" (en) / "你好 world!" (zh) / "こんにちは world!" (ja)
```

Shared labels (categories, periods, day names) are available via:

```python
from src.core.i18n.shared import category_label, period_label

category_label("morning", "en")  # → "Morning"
period_label("week", "ja")       # → "今週"
```

## Step 5: Register in Config

Add your plugin to `config.yaml`:

```yaml
plugins:
  your_plugin:
    custom_option: "value"
```

Access config in handlers via `ctx.config`:

```python
value = ctx.config.get("custom_option", "default")
```

**That's it.** The plugin system auto-discovers your package at startup, runs migrations, and registers commands.

## Optional: Message Handlers

To handle raw messages (not commands), return `MessageHandler` objects:

```python
from src.core.bot import MessageHandler, MessageType

def get_handlers(self) -> list[MessageHandler]:
    return [
        MessageHandler(
            msg_type=MessageType.TEXT,
            handler=my_text_handler,
            priority=0,  # higher = runs first
        ),
    ]
```

## Optional: Conversation Flows

For multi-turn interactions (like the journal reflection):

```python
from src.core.bot import ConversationFlow

def get_conversations(self) -> list[ConversationFlow]:
    return [ConversationFlow(
        name="my_flow",
        entry_command="my_start",    # must match a Command name
        entry_handler=start_fn,
        states={0: answer_fn},       # state 0 handler
        cancel_command="my_cancel",
    )]
```

State handlers return:
- `str` — reply and stay in conversation
- `(str, True)` — reply and end conversation
- `None` — end conversation silently

## Optional: Scheduled Jobs

Register in `on_startup()`:

```python
from datetime import time

async def on_startup(self) -> None:
    await self.ctx.scheduler.run_daily(
        callback=my_callback,
        time=time(hour=21, minute=0, tzinfo=self.ctx.tz),
        name="my_daily_job",
    )
```

## Optional: External Call Retry

Use `@with_retry` for any external API calls:

```python
from src.core.retry import with_retry

@with_retry(max_retries=3, delay=1.0, strategy="jitter")
async def call_external_api(url: str) -> dict:
    ...
```

## Optional: Natural Language Intents (Intent Router)

Let users trigger your plugin's features without commands. The IntentRouter uses LLM function-call semantics to match natural language to your plugin and extract arguments.

```python
from src.core.bot import IntentDeclaration

def get_intents(self) -> list[IntentDeclaration]:
    return [
        IntentDeclaration(
            name="your_plugin_action",
            description="What this action does (for LLM to understand)",
            examples=("example message 1", "example message 2"),
            handler=my_handler,
            args_description="What the LLM should extract as args for the handler",
        ),
    ]
```

### How it works

1. User sends a plain text message (no `/command`)
2. IntentRouter sends all plugin intents + user context to LLM
3. LLM returns `{"action": "your_plugin_action", "confidence": 0.9, "args": "extracted text"}`
4. If confidence >= 0.7, your handler receives `event.text = "extracted text"`
5. The message is **always recorded** by the Recorder regardless of intent match

### `args_description` field

This tells the LLM what to extract from the user's message:

| `args_description` | LLM extracts | Handler receives |
|---------------------|--------------|-----------------|
| `"The plan TAG to delete"` | `"brush_teeth"` | `event.text = "brush_teeth"` |
| `"The check-in content"` | `"跑了5公里"` | `event.text = "跑了5公里"` |
| `None` (omitted) | nothing | `event.text = None` |

### User context

Override `get_intent_context()` to provide per-user context that helps the LLM make better routing decisions:

```python
async def get_intent_context(self, user_id: int) -> str:
    # Return user-specific state: active plans, session status, etc.
    return "Active items:\n  - item_1: description\n  - item_2: description"
```

## Checklist

- [ ] `__init__.py` with `BasePlugin` subclass
- [ ] `name` attribute set (used for config key and i18n namespace)
- [ ] `get_commands()` returns at least one `Command`
- [ ] `locale.py` with zh/en/ja translations
- [ ] `migrations/001_init.sql` if using database
- [ ] Plugin added to `config.yaml` under `plugins:`
- [ ] Tests in `tests/test_plugins/test_your_plugin.py`
- [ ] (Optional) `get_intents()` for natural language routing
