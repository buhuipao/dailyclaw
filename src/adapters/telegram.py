"""Telegram adapter — bridges python-telegram-bot to BotAdapter/Scheduler ABCs."""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import time
from typing import Any

from telegram import Bot, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler as TgMessageHandler,
    filters,
)

from src.core.bot import (
    BotAdapter,
    Command,
    ConversationFlow,
    Event,
    MessageHandler,
    MessageRef,
    MessageType,
)
from src.core.scheduler import Scheduler

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DynamicAuthFilter — no Telegram dependency; pure Python
# ---------------------------------------------------------------------------


class DynamicAuthFilter:
    """Thread-safe-ish auth check; admin IDs are fixed, DB users are cached."""

    def __init__(self, admin_ids: list[int]) -> None:
        self._admin_ids: set[int] = set(admin_ids)
        self._db_users: set[int] = set()

    @property
    def admin_ids(self) -> set[int]:
        return set(self._admin_ids)

    def update_cache(self, user_ids: set[int]) -> None:
        self._db_users = set(user_ids)

    def is_authorized(self, user_id: int) -> bool:
        return user_id in self._admin_ids or user_id in self._db_users


# ---------------------------------------------------------------------------
# TelegramScheduler
# ---------------------------------------------------------------------------


class TelegramScheduler(Scheduler):
    """Wraps python-telegram-bot JobQueue."""

    def __init__(self, job_queue: Any) -> None:
        self._jq = job_queue

    async def run_daily(
        self,
        callback: Callable,
        time: time,
        name: str,
        *,
        days: tuple[int, ...] | None = None,
        data: Any = None,
    ) -> None:
        kwargs: dict[str, Any] = {"name": name, "data": data}
        if days is not None:
            kwargs["days"] = days
        self._jq.run_daily(callback, time=time, **kwargs)
        logger.debug("Scheduled daily job %r at %s", name, time)

    async def run_repeating(
        self,
        callback: Callable,
        interval: float,
        name: str,
        *,
        first: float = 0,
    ) -> None:
        self._jq.run_repeating(callback, interval=interval, first=first, name=name)
        logger.debug("Scheduled repeating job %r every %ss", name, interval)

    async def cancel(self, name: str) -> None:
        jobs = self._jq.get_jobs_by_name(name)
        for job in jobs:
            job.schedule_removal()
        logger.debug("Cancelled %d job(s) named %r", len(jobs), name)


# ---------------------------------------------------------------------------
# Event builder
# ---------------------------------------------------------------------------

_TYPE_MAP: dict[MessageType, str] = {
    MessageType.TEXT: "text",
    MessageType.PHOTO: "photo",
    MessageType.VOICE: "voice",
    MessageType.VIDEO: "video",
}


def _build_event(update: Update, auth: DynamicAuthFilter) -> Event | None:
    """Convert a Telegram Update into our platform-agnostic Event.

    Returns None if the update doesn't carry a usable message.
    """
    user = update.effective_user
    chat = update.effective_chat
    msg = update.effective_message

    if user is None or chat is None or msg is None:
        return None

    user_id = user.id
    chat_id = chat.id
    is_admin = user_id in auth.admin_ids

    return Event(
        user_id=user_id,
        chat_id=chat_id,
        text=msg.text or msg.caption,
        photo_file_id=msg.photo[-1].file_id if msg.photo else None,
        voice_file_id=msg.voice.file_id if msg.voice else None,
        video_file_id=msg.video.file_id if msg.video else None,
        caption=msg.caption,
        is_admin=is_admin,
        raw=update,
    )


# ---------------------------------------------------------------------------
# TelegramAdapter
# ---------------------------------------------------------------------------

# Sentinel returned by ConversationHandler when the conversation ends
_END = ConversationHandler.END


class TelegramAdapter(BotAdapter):
    """Full Telegram adapter.

    Usage::

        adapter = TelegramAdapter(token="...", admin_ids=[123])
        adapter.register_command(cmd)
        adapter.register_handler(handler)
        app = adapter.build()
        await adapter.start()
    """

    def __init__(self, token: str, admin_ids: list[int]) -> None:
        self._token = token
        self._auth = DynamicAuthFilter(admin_ids)
        self._commands: list[Command] = []
        self._handlers: list[MessageHandler] = []
        self._conversations: list[ConversationFlow] = []
        self._app: Application | None = None

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_command(self, cmd: Command) -> None:
        self._commands = [*self._commands, cmd]

    def register_handler(self, handler: MessageHandler) -> None:
        self._handlers = [*self._handlers, handler]

    def register_conversation(self, conv: ConversationFlow) -> None:
        self._conversations = [*self._conversations, conv]

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> Application:
        """Construct and return the Telegram Application with all handlers."""
        app = Application.builder().token(self._token).build()

        for conv in self._conversations:
            tg_conv = self._build_conversation_handler(conv)
            app.add_handler(tg_conv)

        for cmd in self._commands:
            tg_handler = CommandHandler(
                cmd.name,
                self._make_command_handler(cmd),
            )
            app.add_handler(tg_handler)

        for mh in sorted(self._handlers, key=lambda h: -h.priority):
            tg_filter = self._msg_type_to_filter(mh.msg_type)
            if tg_filter is not None:
                app.add_handler(TgMessageHandler(tg_filter, self._make_msg_handler(mh)))

        self._app = app
        return app

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._app is None:
            self.build()
        assert self._app is not None
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()
        logger.info("TelegramAdapter polling started")

    async def stop(self) -> None:
        if self._app is None:
            return
        try:
            if self._app.updater and self._app.updater.running:
                await self._app.updater.stop()
            if self._app.running:
                await self._app.stop()
            await self._app.shutdown()
            logger.info("TelegramAdapter stopped")
        except Exception:
            logger.debug("TelegramAdapter stop error (ignored)", exc_info=True)

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    async def send_message(self, chat_id: int, text: str) -> MessageRef:
        bot = self._get_bot()
        msg = await bot.send_message(chat_id=chat_id, text=text)
        return MessageRef(chat_id=chat_id, message_id=msg.message_id)

    async def edit_message(self, chat_id: int, message_id: int, text: str) -> None:
        bot = self._get_bot()
        await bot.edit_message_text(
            chat_id=chat_id, message_id=message_id, text=text
        )

    async def reply(self, event: Event, text: str) -> MessageRef:
        bot = self._get_bot()
        msg = await bot.send_message(chat_id=event.chat_id, text=text)
        return MessageRef(chat_id=event.chat_id, message_id=msg.message_id)

    async def download_file(self, file_id: str) -> bytes:
        bot = self._get_bot()
        tg_file = await bot.get_file(file_id)
        return await tg_file.download_as_bytearray()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_bot(self) -> Bot:
        if self._app is None:
            raise RuntimeError("TelegramAdapter.build() must be called before use")
        return self._app.bot

    def _make_command_handler(self, cmd: Command):
        auth = self._auth

        async def _handler(update: Update, context: Any) -> None:
            event = _build_event(update, auth)
            if event is None:
                return
            if cmd.admin_only and not event.is_admin:
                if update.effective_message:
                    await update.effective_message.reply_text("⛔ 无权限")
                return
            await _safe_dispatch(cmd.handler, event, update)

        return _handler

    def _make_msg_handler(self, mh: MessageHandler):
        auth = self._auth

        async def _handler(update: Update, context: Any) -> None:
            event = _build_event(update, auth)
            if event is None:
                return
            await _safe_dispatch(mh.handler, event, update)

        return _handler

    def _build_conversation_handler(self, conv: ConversationFlow) -> ConversationHandler:
        auth = self._auth

        def _wrap_state(fn: Callable):
            async def _inner(update: Update, context: Any) -> int | None:
                event = _build_event(update, auth)
                if event is None:
                    return None
                result = await fn(event)
                return result

            return _inner

        entry = CommandHandler(conv.entry_command, _wrap_state(list(conv.states.values())[0]))
        states = {
            state_key: [TgMessageHandler(filters.TEXT & ~filters.COMMAND, _wrap_state(fn))]
            for state_key, fn in conv.states.items()
        }
        cancel = CommandHandler(conv.cancel_command, lambda u, c: _END)

        return ConversationHandler(
            entry_points=[entry],
            states=states,
            fallbacks=[cancel],
            name=conv.name,
        )

    @staticmethod
    def _msg_type_to_filter(msg_type: MessageType):
        mapping = {
            MessageType.TEXT: filters.TEXT & ~filters.COMMAND,
            MessageType.PHOTO: filters.PHOTO,
            MessageType.VOICE: filters.VOICE,
            MessageType.VIDEO: filters.VIDEO,
        }
        return mapping.get(msg_type)


# ---------------------------------------------------------------------------
# _safe_dispatch
# ---------------------------------------------------------------------------


async def _safe_dispatch(
    handler: Callable[[Event], Any],
    event: Event,
    update: Update,
) -> None:
    """Call handler; if it returns a str, auto-reply. Catch all exceptions."""
    try:
        result = await handler(event)
        if isinstance(result, str) and update.effective_message:
            await update.effective_message.reply_text(result)
    except Exception:
        logger.exception("Handler raised an exception for event user_id=%d", event.user_id)
        if update.effective_message:
            try:
                await update.effective_message.reply_text("⚠️ 处理失败，请稍后再试。")
            except Exception:
                pass
