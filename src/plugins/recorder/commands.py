"""Recorder plugin commands."""
from __future__ import annotations

import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from src.core.bot import Event
from src.core.i18n import t

import src.plugins.recorder.locale  # noqa: F401

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Heatmap image generation
# ---------------------------------------------------------------------------

# Green shades: empty → light → dark (GitHub-style)
_COLOR_BG = (255, 255, 255)
_COLOR_EMPTY = (235, 237, 240)
_COLOR_L1 = (198, 228, 139)
_COLOR_L2 = (123, 201, 111)
_COLOR_L3 = (35, 154, 59)
_COLOR_L4 = (25, 104, 41)
_COLOR_TEXT = (120, 120, 120)
_COLOR_TEXT_DARK = (80, 80, 80)
_CELL = 18
_GAP = 4
_RADIUS = 4


def _pick_color(count: int, thresholds: list[int]) -> tuple[int, int, int]:
    if count == 0:
        return _COLOR_EMPTY
    if count <= thresholds[0]:
        return _COLOR_L1
    if count <= thresholds[1]:
        return _COLOR_L2
    if count <= thresholds[2]:
        return _COLOR_L3
    return _COLOR_L4


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in (
        # macOS — CJK fonts that actually exist on modern macOS
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        # Debian/Ubuntu: fonts-noto-cjk package (Docker)
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        # Alpine
        "/usr/share/fonts/noto/NotoSansCJK-Regular.ttc",
        # Fallback non-CJK
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def render_heatmap(
    counts: dict[str, int],
    start_date: datetime,
    end_date: datetime,
    lang: str = "zh",
) -> bytes:
    """Render a GitHub-style green heatmap PNG.

    Standard GitHub layout:
      - 7 rows  = Mon .. Sun  (top → bottom)
      - N cols  = weeks       (left → right, oldest → newest)
      - Month labels along the top
      - Day-of-week labels on the left
    ~13 columns for 90 days, compact for mobile.
    """
    # Intensity thresholds from data quartiles
    nonzero = sorted(v for v in counts.values() if v > 0)
    if not nonzero:
        thresholds = [1, 2, 3, 4]
    else:
        q1 = nonzero[len(nonzero) // 4] if len(nonzero) > 3 else nonzero[0]
        q2 = nonzero[len(nonzero) // 2] if len(nonzero) > 1 else q1
        q3 = nonzero[len(nonzero) * 3 // 4] if len(nonzero) > 3 else q2
        thresholds = [
            max(1, q1),
            max(q1 + 1, q2),
            max(q2 + 1, q3),
            max(q3 + 1, q3 + 1),
        ]

    # Align start to the Monday of that week
    start_monday = start_date - timedelta(days=start_date.weekday())

    # Build columns (each column = one week, 7 cells top-to-bottom Mon→Sun)
    columns: list[list[tuple[str, int]]] = []
    current = start_monday
    while current <= end_date:
        week: list[tuple[str, int]] = []
        for dow in range(7):
            day = current + timedelta(days=dow)
            day_str = day.strftime("%Y-%m-%d")
            in_range = start_date <= day <= end_date
            week.append((day_str, counts.get(day_str, 0) if in_range else -1))
        columns.append(week)
        current += timedelta(days=7)

    num_cols = len(columns)

    # Month labels: detect which column starts a new month
    month_labels: dict[int, str] = {}
    prev_month = ""
    for col_idx, week in enumerate(columns):
        # Use the Monday of each week to decide the month
        day_str = week[0][0]
        m = day_str[5:7]
        if m != prev_month:
            month_labels[col_idx] = t(f"shared.month.{int(m)}", lang)
            prev_month = m

    # Fonts
    font = _load_font(13)
    font_small = _load_font(11)

    step = _CELL + _GAP
    left_margin = 28           # day-of-week labels
    top_margin = 24            # month labels
    right_margin = 14
    bottom_margin = 14

    img_w = left_margin + num_cols * step - _GAP + right_margin
    img_h = top_margin + 7 * step - _GAP + bottom_margin

    img = Image.new("RGB", (img_w, img_h), _COLOR_BG)
    draw = ImageDraw.Draw(img)

    # Month labels along the top
    for col_idx, label in month_labels.items():
        x = left_margin + col_idx * step
        draw.text((x, top_margin - 6), label, fill=_COLOR_TEXT_DARK, font=font_small, anchor="lb")

    # Day-of-week labels on the left (show Mon / Wed / Fri)
    day_labels = {0: t("shared.dow.mon", lang), 2: t("shared.dow.wed", lang), 4: t("shared.dow.fri", lang)}
    for row, label in day_labels.items():
        y = top_margin + row * step + _CELL // 2
        draw.text((left_margin - 6, y), label, fill=_COLOR_TEXT, font=font_small, anchor="rm")

    # Draw cells: col = week, row = day-of-week
    for col_idx, week in enumerate(columns):
        for row_idx, (day_str, cnt) in enumerate(week):
            if cnt == -1:
                continue
            x = left_margin + col_idx * step
            y = top_margin + row_idx * step
            color = _pick_color(cnt, thresholds)
            draw.rounded_rectangle(
                (x, y, x + _CELL, y + _CELL), radius=_RADIUS, fill=color,
            )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def recorder_list(db: object, tz: object, event: Event) -> dict[str, Any] | str:
    """Handle /recorder_list — show heatmap of recording frequency (last 3 months)."""
    now = datetime.now(tz)
    end_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=90)

    cursor = await db.conn.execute(
        "SELECT date(created_at) AS day, COUNT(*) AS cnt "
        "FROM messages "
        "WHERE user_id = ? AND created_at >= ? AND deleted_at IS NULL "
        "GROUP BY day",
        (event.user_id, start_date.strftime("%Y-%m-%d")),
    )
    rows = await cursor.fetchall()

    counts: dict[str, int] = {row["day"]: row["cnt"] for row in rows}
    total = sum(counts.values())
    active_days = len(counts)

    photo_bytes = render_heatmap(counts, start_date, end_date, lang=event.lang)
    caption = t("recorder.heatmap_caption", event.lang, total=total, days=active_days)

    return {"photo": photo_bytes, "caption": caption}


async def recorder_del(db: object, event: Event) -> str | None:
    """Handle /recorder_del <id> — soft delete a recorded message.

    Validates that the ID is a valid integer, the message exists,
    and the requesting user owns that message before soft-deleting.

    Returns a user-facing confirmation or error string.
    """
    text = (event.text or "").strip()
    if not text or not text.lstrip("-").isdigit():
        return t("recorder.del_usage", event.lang)

    record_id = int(text)
    if record_id <= 0:
        return t("recorder.del_invalid_id", event.lang)

    row = await _fetch_message(db, record_id)
    if row is None:
        return t("recorder.del_not_found", event.lang, id=record_id)

    if row["user_id"] != event.user_id:
        return t("recorder.del_no_permission", event.lang)

    if row["deleted_at"] is not None:
        return t("recorder.del_already_deleted", event.lang, id=record_id)

    deleted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    await db.conn.execute(
        "UPDATE messages SET deleted_at = ? WHERE id = ?",
        (deleted_at, record_id),
    )
    await db.conn.commit()

    logger.info("[recorder_del] soft-deleted id=%d user=%d", record_id, event.user_id)
    return t("recorder.del_success", event.lang, id=record_id)


async def recorder_today(db: object, tz: object, event: Event) -> str | None:
    """Handle /recorder_today — show today's recorded messages."""
    today = datetime.now(tz).strftime("%Y-%m-%d")
    cursor = await db.conn.execute(
        "SELECT id, msg_type, content, category, created_at FROM messages "
        "WHERE user_id = ? AND date(created_at) = ? AND deleted_at IS NULL "
        "ORDER BY created_at",
        (event.user_id, today),
    )
    rows = await cursor.fetchall()

    if not rows:
        return t("recorder.today_empty", event.lang, date=today)

    lines = [t("recorder.today_header", event.lang, date=today, count=len(rows))]
    for row in rows[-15:]:  # show last 15
        prefix = {"link": "🔗", "photo": "📷", "voice": "🎤", "video": "🎬"}.get(
            row["msg_type"], "💬"
        )
        content = row["content"][:60]
        if len(row["content"]) > 60:
            content += "..."
        lines.append(f"  {prefix} #{row['id']} {content}")

    if len(rows) > 15:
        lines.append(t("recorder.today_more", event.lang, count=len(rows) - 15))

    return "\n".join(lines)


async def _fetch_message(db: object, record_id: int) -> object | None:
    """Fetch a single message row by ID."""
    cursor = await db.conn.execute(
        "SELECT id, user_id, deleted_at FROM messages WHERE id = ?",
        (record_id,),
    )
    return await cursor.fetchone()
