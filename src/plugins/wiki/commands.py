"""Wiki plugin command handlers."""
from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from src.core.i18n import t

import src.plugins.wiki.locale  # noqa: F401

from .db import WikiDB
from .digest import generate_digest
from .query import answer_question

if TYPE_CHECKING:
    from src.core.bot import Event
    from src.core.context import AppContext

logger = logging.getLogger(__name__)


def cmd_ask(ctx: "AppContext") -> Callable[["Event"], Awaitable[str | None]]:
    """Return handler for /ask command."""
    async def handler(event: "Event") -> str | None:
        if not event.text:
            return t("wiki.ask_usage", event.lang)

        wiki_db = WikiDB(ctx.db)
        return await answer_question(
            llm=ctx.llm,
            wiki_db=wiki_db,
            db=ctx.db,
            user_id=event.user_id,
            question=event.text,
            lang=event.lang,
        )

    return handler


def cmd_topics(ctx: "AppContext") -> Callable[["Event"], Awaitable[str | None]]:
    """Return handler for /topics command."""
    async def handler(event: "Event") -> str | None:
        wiki_db = WikiDB(ctx.db)
        index = await wiki_db.get_topic_index(event.user_id)

        if not index:
            return t("wiki.topics_empty", event.lang)

        lines = [t("wiki.topics_header", event.lang, count=len(index))]

        for item in index:
            topic = item["topic"]
            title = item["title"]
            source_count = item["source_count"]
            lines.append(f"  [{topic}] {title} ({source_count} sources)")

        return "\n".join(lines)

    return handler


def cmd_topic(ctx: "AppContext") -> Callable[["Event"], Awaitable[str | None]]:
    """Return handler for /topic <slug> command."""
    async def handler(event: "Event") -> str | None:
        slug = (event.text or "").strip()
        if not slug:
            return t("wiki.topic_usage", event.lang)

        wiki_db = WikiDB(ctx.db)
        page = await wiki_db.get_page(event.user_id, slug)

        if not page:
            return t("wiki.topic_not_found", event.lang, topic=slug)

        try:
            links = json.loads(page.get("links", "[]"))
        except (json.JSONDecodeError, TypeError):
            links = []

        links_text = ", ".join(links) if links else t("wiki.no_links", event.lang)

        return (
            f"📖 {page['title']}\n"
            f"({page['topic']} | {page['source_count']} sources)\n\n"
            f"{page['content']}\n\n"
            f"🔗 {links_text}"
        )

    return handler


def cmd_digest(ctx: "AppContext") -> Callable[["Event"], Awaitable[str | None]]:
    """Return handler for /digest command."""
    async def handler(event: "Event") -> str | None:
        wiki_db = WikiDB(ctx.db)
        result = await generate_digest(
            llm=ctx.llm,
            wiki_db=wiki_db,
            user_id=event.user_id,
            lang=event.lang,
        )

        if not result:
            return t("wiki.digest_empty", event.lang)

        return t("wiki.digest_header", event.lang) + result

    return handler
