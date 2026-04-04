"""Generate static HTML sharing pages from journal entries."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

CATEGORY_LABELS: dict[str, str] = {
    "morning": "晨起",
    "reading": "所阅",
    "social": "待人接物",
    "reflection": "反省",
}

# Templates live inside the src package so they're included in pip install
_TEMPLATES_DIR = str(Path(__file__).resolve().parent.parent.parent / "templates")


async def generate_share_page(
    db: object,
    user_id: int,
    date: str,
    output_dir: str,
    site_title: str = "My Daily Claw",
) -> str:
    """Generate a static HTML page for one day's journal.

    Returns the output file path.
    """
    entries_raw = await _get_journal_entries(db, user_id, date)

    entries = [
        (CATEGORY_LABELS.get(e["category"], e["category"]), e["content"])
        for e in entries_raw
    ]

    env = Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=True,
    )
    template = env.get_template("share.html")

    html = template.render(
        site_title=site_title,
        date=date,
        entries=entries,
        summary=None,
    )

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{date}.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Generated share page: %s", output_path)
    return output_path


async def _get_journal_entries(db: object, user_id: int, date: str) -> list[dict]:
    """Fetch journal entries for the given date."""
    try:
        cursor = await db.conn.execute(
            "SELECT category, content FROM journal_entries "
            "WHERE user_id = ? AND date = ? ORDER BY category",
            (user_id, date),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        logger.warning("journal_entries table unavailable", exc_info=True)
        return []
