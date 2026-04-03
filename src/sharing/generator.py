"""Generate static HTML sharing pages from journal entries."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..storage.db import Database
from ..storage.models import CATEGORY_LABELS

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = str(Path(__file__).resolve().parent.parent.parent / "templates")


async def generate_share_page(
    db: Database,
    user_id: int,
    date: str,
    output_dir: str,
    site_title: str = "My Daily Claw",
) -> str:
    """Generate a static HTML page for one day's journal. Returns output file path."""
    entries_raw = await db.get_journal_entries(user_id, date)

    entries = [
        (CATEGORY_LABELS.get(e.category, e.category.value), e.content)
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
