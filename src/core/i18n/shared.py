"""Shared i18n labels — categories, periods, days, months."""
from __future__ import annotations

from . import register

STRINGS: dict[str, dict[str, str]] = {
    # Journal/recorder categories
    "cat.morning":    {"zh": "晨起",     "en": "Morning",     "ja": "朝の振り返り"},
    "cat.reading":    {"zh": "所阅",     "en": "Reading",     "ja": "読書"},
    "cat.social":     {"zh": "待人接物", "en": "Social",      "ja": "対人関係"},
    "cat.reflection": {"zh": "反省",     "en": "Reflection",  "ja": "反省"},
    "cat.idea":       {"zh": "想法",     "en": "Idea",        "ja": "アイデア"},
    "cat.other":      {"zh": "记录",     "en": "Note",        "ja": "メモ"},
    # Periods
    "period.week":    {"zh": "本周",     "en": "This week",   "ja": "今週"},
    "period.month":   {"zh": "本月",     "en": "This month",  "ja": "今月"},
    "period.quarter": {"zh": "本季度",   "en": "This quarter", "ja": "今四半期"},
    "period.year":    {"zh": "本年",     "en": "This year",   "ja": "今年"},
    # Day-of-week labels (short, for heatmap)
    "dow.mon": {"zh": "一", "en": "M", "ja": "月"},
    "dow.tue": {"zh": "二", "en": "T", "ja": "火"},
    "dow.wed": {"zh": "三", "en": "W", "ja": "水"},
    "dow.thu": {"zh": "四", "en": "T", "ja": "木"},
    "dow.fri": {"zh": "五", "en": "F", "ja": "金"},
    "dow.sat": {"zh": "六", "en": "S", "ja": "土"},
    "dow.sun": {"zh": "日", "en": "S", "ja": "日"},
    # Per-month labels for heatmap
    "month.1":  {"zh": "1月",  "en": "Jan", "ja": "1月"},
    "month.2":  {"zh": "2月",  "en": "Feb", "ja": "2月"},
    "month.3":  {"zh": "3月",  "en": "Mar", "ja": "3月"},
    "month.4":  {"zh": "4月",  "en": "Apr", "ja": "4月"},
    "month.5":  {"zh": "5月",  "en": "May", "ja": "5月"},
    "month.6":  {"zh": "6月",  "en": "Jun", "ja": "6月"},
    "month.7":  {"zh": "7月",  "en": "Jul", "ja": "7月"},
    "month.8":  {"zh": "8月",  "en": "Aug", "ja": "8月"},
    "month.9":  {"zh": "9月",  "en": "Sep", "ja": "9月"},
    "month.10": {"zh": "10月", "en": "Oct", "ja": "10月"},
    "month.11": {"zh": "11月", "en": "Nov", "ja": "11月"},
    "month.12": {"zh": "12月", "en": "Dec", "ja": "12月"},
    # Day name mapping for schedule display
    "day.mon": {"zh": "一", "en": "Mon", "ja": "月"},
    "day.tue": {"zh": "二", "en": "Tue", "ja": "火"},
    "day.wed": {"zh": "三", "en": "Wed", "ja": "水"},
    "day.thu": {"zh": "四", "en": "Thu", "ja": "木"},
    "day.fri": {"zh": "五", "en": "Fri", "ja": "金"},
    "day.sat": {"zh": "六", "en": "Sat", "ja": "土"},
    "day.sun": {"zh": "日", "en": "Sun", "ja": "日"},
    # Common words
    "daily": {"zh": "每天", "en": "Daily", "ja": "毎日"},
    "weekly_prefix": {"zh": "每周", "en": "Weekly ", "ja": "毎週"},
    # Language names for LLM prompts
    "lang_name.zh": {"zh": "中文", "en": "中文", "ja": "中文"},
    "lang_name.en": {"zh": "English", "en": "English", "ja": "English"},
    "lang_name.ja": {"zh": "日本語", "en": "日本語", "ja": "日本語"},
}

register("shared", STRINGS)


def category_label(key: str, lang: str = "zh") -> str:
    """Convenience: category_label('morning', 'en') -> 'Morning'."""
    from . import t
    return t(f"shared.cat.{key}", lang)


def period_label(key: str, lang: str = "zh") -> str:
    """Convenience: period_label('week', 'en') -> 'This week'."""
    from . import t
    return t(f"shared.period.{key}", lang)
