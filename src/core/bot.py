from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class MessageRef:
    chat_id: int
    message_id: int


@dataclass(frozen=True)
class Event:
    user_id: int
    chat_id: int
    text: str | None = None
    photo_file_id: str | None = None
    voice_file_id: str | None = None
    video_file_id: str | None = None
    caption: str | None = None
    is_admin: bool = False
    lang: str = "en"
    raw: Any = None


class MessageType(str, Enum):
    TEXT = "text"
    PHOTO = "photo"
    VOICE = "voice"
    VIDEO = "video"
    COMMAND = "command"


@dataclass(frozen=True)
class Command:
    name: str
    description: str
    handler: Callable[[Event], Awaitable[str | None]]
    admin_only: bool = False


@dataclass(frozen=True)
class MessageHandler:
    msg_type: MessageType
    handler: Callable[[Event], Awaitable[str | None]]
    priority: int = 0


@dataclass(frozen=True)
class ConversationFlow:
    name: str
    entry_command: str
    entry_handler: Callable[[Event], Awaitable[str | None]]
    states: dict[int, Callable]
    cancel_command: str = "cancel"


@dataclass(frozen=True)
class IntentDeclaration:
    """A plugin-declared intent that can be triggered by natural language.

    *args_description* tells the LLM what to extract as the handler argument.
    When set, the router passes the extracted text as ``event.text`` so the
    handler receives clean, pre-parsed input — just like a ``/command <args>``.
    When ``None``, the handler receives ``text=None`` (no arguments needed).
    """

    name: str
    description: str  # For LLM to understand when this intent applies
    examples: tuple[str, ...]  # Example user messages
    handler: Callable[[Event], Awaitable[str | None]]
    args_description: str | None = None  # What the LLM should extract as args


class BotAdapter(ABC):
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
