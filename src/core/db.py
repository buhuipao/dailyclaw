"""Database connection and plugin migration runner."""
from __future__ import annotations

import logging
import re
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

_SCHEMA_VERSIONS_TABLE = """\
CREATE TABLE IF NOT EXISTS schema_versions (
    plugin_name TEXT NOT NULL,
    version INTEGER NOT NULL,
    filename TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (plugin_name, version)
);
"""


class Database:
    def __init__(self, db_path: str = "data/dailyclaw.db") -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Database.connect() has not been awaited")
        return self._db

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA_VERSIONS_TABLE)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None


class MigrationRunner:
    _VERSION_RE = re.compile(r"^(\d+)_.+\.sql$")

    def __init__(self, db: Database) -> None:
        self._db = db

    async def run(self, plugin_name: str, migrations_dir: str) -> None:
        mig_path = Path(migrations_dir)
        if not mig_path.is_dir():
            return

        files = sorted(mig_path.glob("*.sql"))
        if not files:
            return

        cursor = await self._db.conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS max_ver FROM schema_versions WHERE plugin_name = ?",
            (plugin_name,),
        )
        row = await cursor.fetchone()
        current_version = row["max_ver"]

        for sql_file in files:
            match = self._VERSION_RE.match(sql_file.name)
            if not match:
                continue
            version = int(match.group(1))
            if version <= current_version:
                continue

            sql = sql_file.read_text(encoding="utf-8")
            logger.info("Applying migration %s/%s (v%d)", plugin_name, sql_file.name, version)

            try:
                await self._db.conn.executescript(sql)
                await self._db.conn.execute(
                    "INSERT INTO schema_versions (plugin_name, version, filename) VALUES (?, ?, ?)",
                    (plugin_name, version, sql_file.name),
                )
                await self._db.conn.commit()
            except Exception:
                logger.error("Migration failed: %s/%s", plugin_name, sql_file.name, exc_info=True)
                raise
