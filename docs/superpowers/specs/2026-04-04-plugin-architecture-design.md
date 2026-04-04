# DailyClaw 插件化架构设计

**日期:** 2026-04-04
**状态:** 已批准
**目标:** 将 DailyClaw 重构为插件化架构，为开源做准备

---

## 1. 设计决策总结

| 决策项 | 选择 |
|--------|------|
| 插件系统 | 轻量级，项目内 Python 包，强制继承 BasePlugin |
| Bot 抽象 | 以 Telegram 为蓝本的 BotAdapter，当前只实现 TelegramAdapter |
| LLM | 统一 LLMService，按 Capability 路由，底层全部走 OpenAI SDK |
| Migration | 纯 SQL 文件 + schema_versions 表追踪版本 |
| 插件上下文 | 完整注入 AppContext（db, llm, bot, scheduler, config, tz） |
| 命令命名 | `/{plugin}_{action}` 格式 |
| 错误处理 | 插件隔离，单个插件失败不影响整体运行 |

---

## 2. 项目目录结构

```
dailyclaw/
├── core/
│   ├── __init__.py
│   ├── plugin.py          # BasePlugin + PluginRegistry
│   ├── bot.py             # BotAdapter + Event/Command/ConversationFlow/MessageRef
│   ├── llm.py             # LLMService + Capability + LLMProvider
│   ├── db.py              # Database + MigrationRunner
│   └── context.py         # AppContext
├── adapters/
│   ├── __init__.py
│   └── telegram.py        # TelegramAdapter implements BotAdapter
├── plugins/
│   ├── recorder/
│   │   ├── __init__.py
│   │   ├── handlers.py
│   │   ├── commands.py
│   │   ├── url_fetcher.py
│   │   ├── dedup.py
│   │   └── migrations/001_init.sql
│   ├── journal/
│   │   ├── __init__.py
│   │   ├── commands.py
│   │   ├── engine.py
│   │   ├── scheduler.py
│   │   └── migrations/001_init.sql
│   ├── planner/
│   │   ├── __init__.py
│   │   ├── commands.py
│   │   ├── scheduler.py
│   │   └── migrations/001_init.sql
│   └── sharing/
│       ├── __init__.py
│       ├── commands.py
│       └── migrations/001_init.sql
├── main.py
├── config.example.yaml
├── requirements.txt
└── tests/
    ├── conftest.py
    ├── test_core/
    │   ├── test_plugin.py
    │   ├── test_llm.py
    │   └── test_db.py
    └── test_plugins/
        ├── test_recorder.py
        ├── test_journal.py
        ├── test_planner.py
        └── test_sharing.py
```

---

## 3. 核心框架（core/）

### 3.1 AppContext

```python
@dataclass(frozen=True)
class AppContext:
    db: Database
    llm: LLMService
    bot: BotAdapter
    scheduler: Scheduler
    config: dict[str, Any]   # 该插件自己的配置段，即 config["plugins"][plugin.name]
    tz: ZoneInfo
```

### Scheduler 抽象

```python
class Scheduler(ABC):
    """定时任务调度器 — 与 Bot 实现解耦。"""

    @abstractmethod
    async def run_daily(
        self, callback: Callable, time: time, name: str, data: Any = None,
    ) -> None:
        """每天固定时间执行。"""
        ...

    @abstractmethod
    async def run_repeating(
        self, callback: Callable, interval: float, name: str, first: float = 0,
    ) -> None:
        """按固定间隔重复执行。"""
        ...

    @abstractmethod
    async def cancel(self, name: str) -> None:
        """取消指定名称的任务。"""
        ...
```

TelegramAdapter 内部用 `python-telegram-bot` 的 `JobQueue` 实现此接口。其他适配器可用 APScheduler、asyncio 或其他调度库实现。

### 3.2 BasePlugin

```python
class BasePlugin(ABC):
    """所有插件必须继承此基类。"""
    name: str           # 唯一标识，如 "journal"
    version: str        # 语义版本，如 "1.0.0"
    description: str    # 一句话描述

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx

    @abstractmethod
    def get_commands(self) -> list[Command]:
        """返回此插件提供的斜杠命令。"""
        ...

    def get_handlers(self) -> list[MessageHandler]:
        """返回消息处理器（可选，默认空）。"""
        return []

    def get_conversations(self) -> list[ConversationFlow]:
        """返回多轮对话定义（可选，默认空）。"""
        return []

    async def on_startup(self) -> None:
        """插件启动后回调（注册定时任务等）。"""
        pass

    async def on_shutdown(self) -> None:
        """插件关闭时回调（清理资源）。"""
        pass
```

### 3.3 PluginRegistry

- 扫描 `plugins/` 下所有子目录
- 每个子目录的 `__init__.py` 必须导出一个 `BasePlugin` 子类
- 按目录名字母序加载，执行 migration，实例化插件，调用 `on_startup`
- 收集所有 commands、handlers、conversations 注册到 bot adapter

---

## 4. Bot 抽象层

以 Telegram 的能力模型为蓝本设计接口，其他 IM 平台通过适配器映射到这套接口。

### 4.1 事件与命令模型

```python
@dataclass(frozen=True)
class MessageRef:
    """发送后的消息引用，用于后续编辑。"""
    chat_id: int
    message_id: int

@dataclass(frozen=True)
class Event:
    """消息事件 — 字段命名沿用 Telegram 概念。"""
    user_id: int
    chat_id: int
    text: str | None = None
    photo_file_id: str | None = None
    voice_file_id: str | None = None
    video_file_id: str | None = None
    caption: str | None = None
    is_admin: bool = False
    raw: Any = None          # 原始平台对象

class MessageType(str, Enum):
    TEXT = "text"
    PHOTO = "photo"
    VOICE = "voice"
    VIDEO = "video"
    COMMAND = "command"

@dataclass(frozen=True)
class Command:
    name: str                    # "journal_start"
    description: str             # "开始今日反思"
    handler: Callable[[Event], Awaitable[str | None]]
    admin_only: bool = False

@dataclass(frozen=True)
class MessageHandler:
    msg_type: MessageType
    handler: Callable[[Event], Awaitable[str | None]]
    priority: int = 0            # 多个 handler 时按优先级排序

@dataclass(frozen=True)
class ConversationFlow:
    """多轮对话定义 — 对应 Telegram 的 ConversationHandler。"""
    name: str
    entry_command: str
    states: dict[int, Callable]
    cancel_command: str = "cancel"
```

### 4.2 BotAdapter 抽象

```python
class BotAdapter(ABC):
    """Bot 接口 — 以 Telegram 能力为蓝本。"""

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def send_message(self, chat_id: int, text: str) -> MessageRef: ...

    @abstractmethod
    async def edit_message(self, chat_id: int, message_id: int, text: str) -> None: ...

    @abstractmethod
    async def reply(self, event: Event, text: str) -> MessageRef: ...

    @abstractmethod
    async def download_file(self, file_id: str) -> bytes: ...

    @abstractmethod
    def register_command(self, cmd: Command) -> None: ...

    @abstractmethod
    def register_handler(self, handler: MessageHandler) -> None: ...

    @abstractmethod
    def register_conversation(self, conv: ConversationFlow) -> None: ...
```

### 4.3 TelegramAdapter

- 继承 `BotAdapter`，内部包装 `python-telegram-bot`
- 将 Telegram `Update` 转换为 `Event`
- 保留 `DynamicAuthFilter` 逻辑
- `event.raw` 存原始 `Update` 对象

### 4.4 Handler 返回值约定

- 返回 `str` → 框架自动调用 `bot.reply(event, text)` 回复
- 返回 `None` → 插件自行处理回复（如 ACK → 编辑消息场景）

---

## 5. LLM 统一服务

### 5.1 能力与 Provider

```python
class Capability(str, Enum):
    TEXT = "text"
    VISION = "vision"
    AUDIO = "audio"
    VIDEO = "video"

@dataclass(frozen=True)
class LLMProvider:
    capability: Capability
    base_url: str
    api_key: str
    model: str
    max_tokens: int = 2000
    temperature: float = 0.7
    timeout: float = 60.0
```

### 5.2 LLMService

```python
class LLMService:
    """统一多模态 LLM 服务。按能力路由到不同 provider。"""

    def __init__(self, providers: dict[Capability, LLMProvider]) -> None: ...

    def supports(self, capability: Capability) -> bool: ...

    # 基础能力
    async def chat(self, messages: list[dict], **kwargs) -> str: ...
    async def analyze_image(self, image_bytes: bytes, prompt: str = "") -> str: ...
    async def transcribe_audio(self, audio_bytes: bytes) -> str: ...
    async def analyze_video(self, video_bytes: bytes, prompt: str = "") -> str: ...

    # 业务便捷方法（核心框架公共能力）
    async def classify(self, text: str) -> dict[str, str]: ...
    async def summarize_text(self, text: str, url: str = "") -> str: ...
    async def parse_plan(self, text: str) -> dict[str, str]: ...
    async def match_checkin(self, text: str, plans: list) -> dict[str, str]: ...
```

所有 provider 底层走 `AsyncOpenAI`，只是 `base_url` 不同。未配置的能力调用时抛 `CapabilityNotConfigured`。

### 5.3 config.yaml LLM 段

```yaml
llm:
  text:
    base_url: "https://api.openai.com/v1"
    api_key: "${LLM_API_KEY}"
    model: "gpt-4o-mini"
  vision:
    base_url: "https://ark.cn-beijing.volces.com/api/v3"
    api_key: "${VISION_API_KEY}"
    model: "doubao-seed-1241-v2.0-250304"
  # audio: ...  可选
  # video: ...  可选
```

---

## 6. 数据库与 Migration

### 6.1 Migration 机制

每个插件目录下 `migrations/` 包含有序 SQL 文件：

```
plugins/journal/migrations/
├── 001_init.sql
└── 002_add_mood.sql
```

框架维护 `schema_versions` 表追踪每个插件的已执行版本：

```sql
CREATE TABLE IF NOT EXISTS schema_versions (
    plugin_name TEXT NOT NULL,
    version INTEGER NOT NULL,
    filename TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (plugin_name, version)
);
```

### 6.2 执行流程

1. 框架启动 → 创建 `schema_versions` 表
2. 扫描每个插件的 `migrations/` 目录
3. 查询该插件当前已执行的最大 version
4. 按版本号顺序执行未应用的 SQL 文件
5. 每个文件执行成功后写入 `schema_versions`
6. 某个文件失败 → 该插件不加载，其他插件正常运行，日志明确报错

---

## 7. 插件拆分

现有功能拆为 4 个内置插件：

| 插件 | 来源 | 命令 |
|------|------|------|
| `recorder` | `handlers.py` + `url_fetcher.py` | `/recorder_del <id>`（消息处理器 + LLM 语义去重） |
| `journal` | `journal/` + `commands.py` 部分 | `/journal_start`, `/journal_today`, `/journal_cancel` |
| `planner` | `planner/` + `commands.py` 部分 | `/planner_add`, `/planner_del`, `/planner_checkin`, `/planner_list` |
| `sharing` | `sharing/` + `commands.py` 部分 | `/sharing_summary`, `/sharing_export` |

框架级命令（不属于插件）：`/start`, `/help`, `/invite`, `/kick`

### 7.1 Recorder 特殊设计

- **ACK 消息带 ID：** 消息处理完成后，编辑 ACK 为结果文本 + 记录 ID + 删除命令提示
  ```
  已记录到今日「所阅」(#42)
  📝 读了一篇关于 Rust 内存安全的文章

  有误？发送 /recorder_del 42
  ```
- **LLM 语义去重（覆盖/合并策略）：** 新消息入库前取最近 N 条同用户消息，调用 LLM 判断语义是否重复。若重复：
  - LLM 返回 `{"duplicate_of": <old_id>, "action": "merge"|"replace", "merged_content": "..."}`
  - `replace`：用新内容覆盖旧记录，保留旧 ID
  - `merge`：LLM 将新旧内容合并为一条，更新旧记录
  - ACK 返回旧记录 ID：`已合并到 (#37)，内容已更新。有误？发送 /recorder_del 37`
- **软删除：** `/recorder_del <id>` 设置 `deleted_at` 字段，展示命令过滤已删除记录

### 7.2 /help 自动生成

框架遍历所有已加载插件的 `get_commands()`，按插件分组生成：

```
📖 使用指南

📝 recorder — 消息记录
  /recorder_del <id> → 删除一条记录

🌙 journal — 曾国藩式每日四省反思
  /journal_start → 开始今日反思
  /journal_today → 查看今日记录
  /journal_cancel → 取消进行中的反思

📊 planner — 计划与打卡
  /planner_add → 创建新计划
  /planner_del → 归档计划
  /planner_checkin → 智能打卡
  /planner_list → 查看计划进度

📄 sharing — 分享与总结
  /sharing_summary → 周/月总结
  /sharing_export → 分享内容

🔑 管理员
  /invite <user_id> → 邀请用户
  /kick <user_id> → 移除用户
```

---

## 8. 启动与关闭流程

### 8.1 启动

```
main.py
  1. load_config()
  2. Database.connect() + 创建 schema_versions 表
  3. LLMService(config["llm"])
  4. TelegramAdapter(config["telegram"])
  5. AppContext(db, llm, bot, scheduler, config, tz)
  6. PluginRegistry.discover("plugins/")
     ├── 扫描子目录，找到 BasePlugin 子类
     ├── 对每个插件：
     │   ├── 执行 migrations/
     │   ├── 实例化 Plugin(ctx)，ctx.config = config["plugins"][plugin.name]
     │   ├── 收集 commands + handlers + conversations
     │   └── 调用 plugin.on_startup()
     └── 注册所有 commands/handlers/conversations 到 bot adapter
  7. 自动生成 /help
  8. 注册框架级命令（/start, /help, /invite, /kick）
  9. bot.start()
```

### 8.2 关闭

```
bot.stop()
  → 逆序调用每个 plugin.on_shutdown()
  → db.close()
```

---

## 9. 错误处理

### 9.1 插件隔离

```python
async def _safe_dispatch(self, handler, event: Event) -> str | None:
    try:
        return await handler(event)
    except Exception as exc:
        logger.error("Plugin handler failed: %s", exc, exc_info=True)
        return "⚠️ 处理出错，请稍后重试。"
```

### 9.2 降级策略

- **Migration 失败：** 该插件不加载，其他插件正常，日志报错
- **LLM 能力缺失：** 抛 `CapabilityNotConfigured`，被 `_safe_dispatch` 捕获返回友好提示
- **LLM 不可用：** 启动但禁用 LLM 依赖功能，纯记录功能仍可用
- **插件 `on_startup` 失败：** 跳过该插件，其他正常

---

## 10. config.yaml 完整结构

```yaml
telegram:
  token: "${TELEGRAM_BOT_TOKEN}"
  allowed_user_ids:
    - 123456789

llm:
  text:
    base_url: "https://api.openai.com/v1"
    api_key: "${LLM_API_KEY}"
    model: "gpt-4o-mini"
  vision:
    base_url: "https://ark.cn-beijing.volces.com/api/v3"
    api_key: "${VISION_API_KEY}"
    model: "doubao-seed-1241-v2.0-250304"

timezone: "Asia/Shanghai"

plugins:
  recorder:
    dedup_window: 10
  journal:
    evening_prompt_time: "21:30"
    template: "zeng_guofan"
  planner:
    plans:
      - name: "雅思学习"
        tag: "ielts"
        schedule: "daily"
        remind_time: "20:00"
  sharing:
    output_dir: "./data/site"
    site_title: "My Daily Claw"
```
