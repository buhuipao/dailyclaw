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

    def __init__(self, token: str, admin_ids: list[int], db: Any = None) -> None:
        self._token = token
        self._auth = DynamicAuthFilter(admin_ids)
        self._db = db  # Core Database for message queue
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

        # Catch-all for unknown commands — must be before general message handlers
        known = {cmd.name for cmd in self._commands}
        known.update(conv.entry_command for conv in self._conversations)
        known.update(conv.cancel_command for conv in self._conversations)

        async def _unknown_command(update: Update, context: Any) -> None:
            msg = update.effective_message
            if msg and msg.text:
                cmd_text = msg.text.split()[0]  # e.g. "/foo"
                hint = "  ".join(f"/{n}" for n in sorted(known))
                await msg.reply_text(f"未知命令 {cmd_text}\n\n可用命令：\n{hint}\n\n发送 /help 查看详细说明")

        app.add_handler(TgMessageHandler(filters.COMMAND, _unknown_command))

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
        db = self._db

        async def _handler(update: Update, context: Any) -> None:
            event = _build_event(update, auth)
            if event is None:
                return
            if cmd.admin_only and not event.is_admin:
                if update.effective_message:
                    await update.effective_message.reply_text("⛔ 无权限")
                return
            # Strip the /command prefix — event.text should only contain arguments.
            # e.g. "/planner_add 每天学雅思" → "每天学雅思", "/help" → None
            args_text = " ".join(context.args) if context.args else None
            event = Event(
                user_id=event.user_id,
                chat_id=event.chat_id,
                text=args_text,
                photo_file_id=event.photo_file_id,
                voice_file_id=event.voice_file_id,
                video_file_id=event.video_file_id,
                caption=event.caption,
                is_admin=event.is_admin,
                raw=event.raw,
            )
            await _ack_and_dispatch(cmd.handler, event, update, db, f"/{cmd.name}")

        return _handler

    def _make_msg_handler(self, mh: MessageHandler):
        auth = self._auth
        db = self._db

        async def _handler(update: Update, context: Any) -> None:
            event = _build_event(update, auth)
            if event is None:
                return
            await _ack_and_dispatch(mh.handler, event, update, db, mh.msg_type.value)

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
# ACK-first dispatch — enqueue, ACK, process async
# ---------------------------------------------------------------------------

_ACK_PROCESSING = "⏳ 收到，正在处理..."


async def _enqueue_to_db(db: Any, user_id: int, chat_id: int, msg_type: str, payload: str) -> int | None:
    """Save to message_queue for reliability. Returns queue ID or None if db unavailable."""
    if db is None:
        return None
    try:
        cursor = await db.conn.execute(
            "INSERT INTO message_queue (user_id, chat_id, msg_type, payload) VALUES (?, ?, ?, ?)",
            (user_id, chat_id, msg_type, payload),
        )
        await db.conn.commit()
        return cursor.lastrowid
    except Exception:
        logger.debug("Failed to enqueue message (table may not exist yet)", exc_info=True)
        return None


async def _mark_queue_done(db: Any, queue_id: int | None) -> None:
    if db is None or queue_id is None:
        return
    try:
        await db.conn.execute("UPDATE message_queue SET status = 'done' WHERE id = ?", (queue_id,))
        await db.conn.commit()
    except Exception:
        pass


async def _mark_queue_failed(db: Any, queue_id: int | None, error: str) -> None:
    if db is None or queue_id is None:
        return
    try:
        await db.conn.execute(
            "UPDATE message_queue SET status = 'failed', attempts = attempts + 1, last_error = ? WHERE id = ?",
            (error[:500], queue_id),
        )
        await db.conn.commit()
    except Exception:
        pass


async def _ack_and_dispatch(
    handler: Callable[[Event], Any],
    event: Event,
    update: Update,
    db: Any,
    label: str,
) -> None:
    """Enqueue → ACK → process in background → edit ACK with result.

    If the handler returns None, it manages its own reply (e.g. recorder's
    photo/voice handlers that do their own ACK + edit). If the handler
    returns a str, the framework edits the ACK with that string.
    """
    import asyncio
    import json

    msg = update.effective_message
    user_id = event.user_id
    chat_id = event.chat_id

    # 1. Enqueue for reliability
    payload = json.dumps({"label": label, "text": event.text or ""}, ensure_ascii=False)
    queue_id = await _enqueue_to_db(db, user_id, chat_id, label, payload)
    logger.info("[%s] user=%d queue_id=%s", label, user_id, queue_id)

    # 2. Send ACK (best effort)
    ack_msg_id: int | None = None
    if msg:
        try:
            ack = await msg.reply_text(_ACK_PROCESSING)
            ack_msg_id = ack.message_id
        except Exception:
            logger.debug("ACK send failed for user=%d", user_id)

    # 3. Process in background
    asyncio.create_task(
        _bg_process(handler, event, update, db, queue_id, chat_id, ack_msg_id)
    )


async def _bg_process(
    handler: Callable[[Event], Any],
    event: Event,
    update: Update,
    db: Any,
    queue_id: int | None,
    chat_id: int,
    ack_msg_id: int | None,
) -> None:
    """Background: run handler, edit ACK with result, mark queue done/failed."""
    bot = update.get_bot()
    try:
        result = await handler(event)
        await _mark_queue_done(db, queue_id)
        logger.info("[done] user=%d queue_id=%s", event.user_id, queue_id)
    except Exception as exc:
        await _mark_queue_failed(db, queue_id, str(exc))
        logger.warning("[fail] user=%d queue_id=%s: %s", event.user_id, queue_id, exc)
        # Edit ACK to show retry message
        if ack_msg_id:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id, message_id=ack_msg_id,
                    text="⏳ 处理暂时失败，稍后会自动重试。",
                )
            except Exception:
                pass
        return

    # Handler returned a string → edit ACK with the result
    if isinstance(result, str):
        if ack_msg_id:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id, message_id=ack_msg_id, text=result,
                )
                return
            except Exception:
                pass
        # Fallback: send new message
        try:
            await bot.send_message(chat_id=chat_id, text=result)
        except Exception:
            logger.warning("Failed to send reply to chat=%d", chat_id)
    elif ack_msg_id:
        # Handler returned None (managed its own reply) — delete the framework ACK
        try:
            await bot.delete_message(chat_id=chat_id, message_id=ack_msg_id)
        except Exception:
            pass
