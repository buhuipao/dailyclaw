"""Tests for src/core/db.py — Database and MigrationRunner."""
from __future__ import annotations

import pytest
import pytest_asyncio

from src.core.db import Database, MigrationRunner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db(tmp_path):
    """In-memory-style Database using a temp file, connected and ready."""
    db_path = str(tmp_path / "test_core.db")
    database = Database(db_path=db_path)
    await database.connect()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def runner(db):
    """MigrationRunner wired to the test database."""
    return MigrationRunner(db)


# ---------------------------------------------------------------------------
# Database tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_creates_schema_versions_table(db):
    """connect() must create the schema_versions table."""
    cursor = await db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_versions'"
    )
    row = await cursor.fetchone()
    assert row is not None, "schema_versions table should exist after connect()"


@pytest.mark.asyncio
async def test_close_and_reconnect(tmp_path):
    """close() and a subsequent connect() should work without errors."""
    db_path = str(tmp_path / "reconnect.db")
    database = Database(db_path=db_path)
    await database.connect()
    await database.close()

    # Second connect on the same path
    await database.connect()
    cursor = await database.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_versions'"
    )
    row = await cursor.fetchone()
    assert row is not None
    await database.close()


@pytest.mark.asyncio
async def test_conn_raises_before_connect(tmp_path):
    """Accessing .conn before connect() must raise RuntimeError."""
    database = Database(db_path=str(tmp_path / "unused.db"))
    with pytest.raises(RuntimeError, match="connect\\(\\)"):
        _ = database.conn


# ---------------------------------------------------------------------------
# MigrationRunner tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_runner_applies_sql_and_tracks_version(tmp_path, runner, db):
    """A valid migration file is executed and recorded in schema_versions."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_create_items.sql").write_text(
        "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL);",
        encoding="utf-8",
    )

    await runner.run("test_plugin", str(mig_dir))

    # Table should exist
    cursor = await db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='items'"
    )
    assert await cursor.fetchone() is not None

    # Version recorded
    cursor = await db.conn.execute(
        "SELECT version, filename FROM schema_versions WHERE plugin_name = ?",
        ("test_plugin",),
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row["version"] == 1
    assert row["filename"] == "001_create_items.sql"


@pytest.mark.asyncio
async def test_migration_runner_skips_already_applied(tmp_path, runner, db):
    """A migration whose version is already recorded must not be re-applied."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_create_items.sql").write_text(
        "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL);",
        encoding="utf-8",
    )

    # Apply once
    await runner.run("test_plugin", str(mig_dir))

    # Apply again — should be a no-op (no duplicate-table error)
    await runner.run("test_plugin", str(mig_dir))

    cursor = await db.conn.execute(
        "SELECT COUNT(*) AS cnt FROM schema_versions WHERE plugin_name = ?",
        ("test_plugin",),
    )
    row = await cursor.fetchone()
    assert row["cnt"] == 1, "Version should be recorded exactly once"


@pytest.mark.asyncio
async def test_migration_runner_applies_in_version_order(tmp_path, runner, db):
    """Migrations are applied in ascending version order (001 then 002)."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()

    # Write 002 before 001 to verify sorting
    (mig_dir / "002_add_col.sql").write_text(
        "ALTER TABLE items ADD COLUMN description TEXT;",
        encoding="utf-8",
    )
    (mig_dir / "001_create_items.sql").write_text(
        "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL);",
        encoding="utf-8",
    )

    await runner.run("order_plugin", str(mig_dir))

    cursor = await db.conn.execute(
        "SELECT version FROM schema_versions WHERE plugin_name = ? ORDER BY version",
        ("order_plugin",),
    )
    rows = await cursor.fetchall()
    assert [r["version"] for r in rows] == [1, 2]

    # description column must exist
    cursor = await db.conn.execute("PRAGMA table_info(items)")
    cols = {r["name"] for r in await cursor.fetchall()}
    assert "description" in cols


@pytest.mark.asyncio
async def test_migration_runner_incremental_only_runs_new(tmp_path, db):
    """Adding a new migration file only applies that file, not the old one."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_create_items.sql").write_text(
        "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL);",
        encoding="utf-8",
    )

    runner = MigrationRunner(db)
    await runner.run("inc_plugin", str(mig_dir))

    # Add second migration
    (mig_dir / "002_add_col.sql").write_text(
        "ALTER TABLE items ADD COLUMN description TEXT;",
        encoding="utf-8",
    )
    await runner.run("inc_plugin", str(mig_dir))

    cursor = await db.conn.execute(
        "SELECT COUNT(*) AS cnt FROM schema_versions WHERE plugin_name = ?",
        ("inc_plugin",),
    )
    row = await cursor.fetchone()
    assert row["cnt"] == 2, "Both migrations should be recorded"

    cursor = await db.conn.execute("PRAGMA table_info(items)")
    cols = {r["name"] for r in await cursor.fetchall()}
    assert "description" in cols


@pytest.mark.asyncio
async def test_migration_runner_failure_does_not_track_version(tmp_path, runner, db):
    """When a migration SQL fails the version must NOT be recorded."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_bad.sql").write_text(
        "THIS IS NOT VALID SQL !!!;",
        encoding="utf-8",
    )

    with pytest.raises(Exception):
        await runner.run("fail_plugin", str(mig_dir))

    cursor = await db.conn.execute(
        "SELECT COUNT(*) AS cnt FROM schema_versions WHERE plugin_name = ?",
        ("fail_plugin",),
    )
    row = await cursor.fetchone()
    assert row["cnt"] == 0, "Failed migration must not be tracked"


@pytest.mark.asyncio
async def test_migration_runner_empty_dir_is_noop(tmp_path, runner, db):
    """An empty migrations directory produces no rows in schema_versions."""
    mig_dir = tmp_path / "empty_migrations"
    mig_dir.mkdir()

    await runner.run("empty_plugin", str(mig_dir))

    cursor = await db.conn.execute(
        "SELECT COUNT(*) AS cnt FROM schema_versions WHERE plugin_name = ?",
        ("empty_plugin",),
    )
    row = await cursor.fetchone()
    assert row["cnt"] == 0


@pytest.mark.asyncio
async def test_migration_runner_nonexistent_dir_is_noop(tmp_path, runner, db):
    """A non-existent migrations directory is silently ignored."""
    nonexistent = str(tmp_path / "does_not_exist")

    await runner.run("ghost_plugin", nonexistent)  # must not raise

    cursor = await db.conn.execute(
        "SELECT COUNT(*) AS cnt FROM schema_versions WHERE plugin_name = ?",
        ("ghost_plugin",),
    )
    row = await cursor.fetchone()
    assert row["cnt"] == 0


# ---------------------------------------------------------------------------
# Core migration 004 — rename plugin entries
# ---------------------------------------------------------------------------

from pathlib import Path

_SRC_ROOT = Path(__file__).parent.parent.parent / "src"
_CORE_MIGRATIONS = str(_SRC_ROOT / "core" / "migrations")


@pytest.mark.asyncio
async def test_004_rename_plugins_migration(tmp_path):
    """Migration 004 renames recorder→memo, journal→reflect, planner→track."""
    db_path = str(tmp_path / "rename_test.db")
    database = Database(db_path=db_path)
    await database.connect()

    try:
        # Seed old plugin names into schema_versions as if they were applied
        # before the rename (version 1 each so they look like real prior state).
        old_names = ("recorder", "journal", "planner")
        for name in old_names:
            await database.conn.execute(
                "INSERT INTO schema_versions (plugin_name, version, filename) VALUES (?, ?, ?)",
                (name, 1, f"001_initial.sql"),
            )
        await database.conn.commit()

        # Run core migrations — migration 004 should rename the seeded entries.
        runner = MigrationRunner(database)
        await runner.run("core", _CORE_MIGRATIONS)

        # Assert new names exist.
        cursor = await database.conn.execute(
            "SELECT plugin_name FROM schema_versions WHERE plugin_name IN ('memo', 'reflect', 'track')"
        )
        new_rows = await cursor.fetchall()
        new_names = {row["plugin_name"] for row in new_rows}
        assert new_names == {"memo", "reflect", "track"}, (
            f"Expected renamed entries to exist, got: {new_names}"
        )

        # Assert old names are gone.
        cursor = await database.conn.execute(
            "SELECT plugin_name FROM schema_versions WHERE plugin_name IN ('recorder', 'journal', 'planner')"
        )
        old_rows = await cursor.fetchall()
        assert len(old_rows) == 0, (
            f"Old plugin names should be gone, but found: {[r['plugin_name'] for r in old_rows]}"
        )
    finally:
        await database.close()
