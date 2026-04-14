"""WikiDB — data access layer for wiki_pages and wiki_log tables."""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class WikiDB:
    """Thin adapter that exposes wiki operations on top of core Database."""

    def __init__(self, db: Any) -> None:
        self._db = db

    async def get_topic_index(self, user_id: int) -> list[dict[str, Any]]:
        """Return list of {topic, title, page_type, source_count, updated_at} for a user."""
        cursor = await self._db.conn.execute(
            "SELECT topic, title, page_type, source_count, updated_at "
            "FROM wiki_pages WHERE user_id = ? "
            "ORDER BY updated_at DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_page(self, user_id: int, topic: str) -> dict[str, Any] | None:
        """Return full wiki page row or None."""
        cursor = await self._db.conn.execute(
            "SELECT id, user_id, topic, title, content, links, page_type, "
            "source_count, last_ingest, created_at, updated_at "
            "FROM wiki_pages WHERE user_id = ? AND topic = ?",
            (user_id, topic),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_pages(self, user_id: int, topics: list[str]) -> list[dict[str, Any]]:
        """Return full rows for a list of topics (parameterized IN clause)."""
        if not topics:
            return []
        placeholders = ",".join("?" for _ in topics)
        cursor = await self._db.conn.execute(
            "SELECT id, user_id, topic, title, content, links, page_type, "
            "source_count, last_ingest, created_at, updated_at "
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
        """Insert or update a wiki page. Returns the page id."""
        links_json = json.dumps(links, ensure_ascii=False)
        cursor = await self._db.conn.execute(
            "INSERT INTO wiki_pages (user_id, topic, title, content, links, page_type, source_count, last_ingest) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(user_id, topic) DO UPDATE SET "
            "title = excluded.title, "
            "content = excluded.content, "
            "links = excluded.links, "
            "page_type = COALESCE(excluded.page_type, page_type), "
            "source_count = source_count + ?, "
            "last_ingest = datetime('now'), "
            "updated_at = datetime('now')",
            (user_id, topic, title, content, links_json, page_type, source_delta, source_delta),
        )
        await self._db.conn.commit()
        return cursor.lastrowid or 0

    async def get_pages_updated_since(
        self, user_id: int, since: str
    ) -> list[dict[str, Any]]:
        """Return pages with updated_at > since."""
        cursor = await self._db.conn.execute(
            "SELECT id, user_id, topic, title, content, links, page_type, "
            "source_count, last_ingest, created_at, updated_at "
            "FROM wiki_pages WHERE user_id = ? AND updated_at > ? "
            "ORDER BY updated_at DESC",
            (user_id, since),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_global_watermark(self, user_id: int) -> str | None:
        """Return MAX(last_ingest) across all pages for a user."""
        cursor = await self._db.conn.execute(
            "SELECT MAX(last_ingest) AS wm FROM wiki_pages WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["wm"] if row and row["wm"] else None

    async def log_op(self, user_id: int, op: str, detail: str) -> None:
        """Insert an operation log entry."""
        await self._db.conn.execute(
            "INSERT INTO wiki_log (user_id, op, detail) VALUES (?, ?, ?)",
            (user_id, op, detail),
        )
        await self._db.conn.commit()

    async def get_recent_logs(
        self, user_id: int, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Return recent wiki_log entries."""
        cursor = await self._db.conn.execute(
            "SELECT id, user_id, op, detail, created_at "
            "FROM wiki_log WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
