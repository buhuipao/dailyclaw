"""Tests for static sharing page generator."""
from __future__ import annotations

import os

import pytest
import pytest_asyncio

from src.sharing.generator import generate_share_page
from src.storage.db import Database
from src.storage.models import JournalCategory


@pytest_asyncio.fixture
async def db(tmp_path):
    """Legacy db fixture using src.storage.db.Database for these tests."""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path=db_path)
    await database.connect()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_generate_share_page(db, tmp_path):
    await db.save_journal_entry(1, "2026-04-03", JournalCategory.MORNING, "7点起床")
    await db.save_journal_entry(1, "2026-04-03", JournalCategory.READING, "读了分布式系统文章")

    output_dir = str(tmp_path / "site")
    result = await generate_share_page(
        db=db, user_id=1, date="2026-04-03",
        output_dir=output_dir, site_title="Test Claw",
    )

    assert os.path.exists(result)
    with open(result) as f:
        html = f.read()
    assert "7点起床" in html
    assert "分布式系统" in html
    assert "Test Claw" in html


@pytest.mark.asyncio
async def test_generate_share_page_empty(db, tmp_path):
    output_dir = str(tmp_path / "site")
    result = await generate_share_page(
        db=db, user_id=1, date="2026-04-03",
        output_dir=output_dir, site_title="Test",
    )

    assert os.path.exists(result)
    with open(result) as f:
        html = f.read()
    assert "暂无记录" in html
