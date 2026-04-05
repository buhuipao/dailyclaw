"""Sharing plugin translations."""
from src.core.i18n import register

STRINGS: dict[str, dict[str, str]] = {
    "description": {
        "zh": "分享与总结 — 周/月总结和内容导出",
        "en": "Sharing & summaries — weekly/monthly reports and export",
        "ja": "共有とまとめ — 週次/月次レポートとエクスポート",
    },
    "cmd.summary": {
        "zh": "生成周/月总结 (用法: /sharing_summary [week|month])",
        "en": "Generate weekly/monthly summary (usage: /sharing_summary [week|month])",
        "ja": "週次/月次まとめ生成 (使い方: /sharing_summary [week|month])",
    },
    "cmd.export": {
        "zh": "导出指定日期的内容 (用法: /sharing_export [YYYY-MM-DD])",
        "en": "Export content for a date (usage: /sharing_export [YYYY-MM-DD])",
        "ja": "指定日のコンテンツをエクスポート (使い方: /sharing_export [YYYY-MM-DD])",
    },
    "summary_usage": {
        "zh": "用法: /sharing_summary [week|month]",
        "en": "Usage: /sharing_summary [week|month]",
        "ja": "使い方: /sharing_summary [week|month]",
    },
    "export_empty": {
        "zh": "📭 {date} 没有记录。",
        "en": "📭 No records for {date}.",
        "ja": "📭 {date} の記録はありません。",
    },
    "export_header": {
        "zh": "📅 {date} 日记\n",
        "en": "📅 {date} Diary\n",
        "ja": "📅 {date} 日記\n",
    },
    "export_records_section": {
        "zh": "── 今日记录 ──",
        "en": "── Today's Records ──",
        "ja": "── 今日の記録 ──",
    },
    "export_journal_section": {
        "zh": "── 日记反思 ──",
        "en": "── Journal Reflection ──",
        "ja": "── 日記の振り返り ──",
    },
    "export_summary_label": {
        "zh": "   摘要: {text}",
        "en": "   Summary: {text}",
        "ja": "   要約: {text}",
    },
    "export_vision_label": {
        "zh": "   图片: {text}",
        "en": "   Image: {text}",
        "ja": "   画像: {text}",
    },
    # summary.py
    "no_entries": {
        "zh": "{period}没有记录。开始用 /journal_start 记录每天的反思吧！",
        "en": "No entries for {period}. Start recording daily reflections with /journal_start!",
        "ja": "{period}の記録がありません。/journal_start で毎日の振り返りを始めましょう！",
    },
    "summary_system_prompt": {
        "zh": (
            "你是 DailyClaw 的总结助手。请为用户生成{period}总结。\n"
            "包含：1) 整体评价 2) 做得好的地方 3) 需要改进的地方 4) 一句鼓励\n"
            "简洁有力，用中文，300字以内。"
        ),
        "en": (
            "You are DailyClaw's summary assistant. Generate a {period} summary.\n"
            "Include: 1) Overall assessment 2) Strengths 3) Areas for improvement 4) Encouragement\n"
            "Concise, respond in English, under 200 words."
        ),
        "ja": (
            "あなたはDailyClawの要約アシスタントです。{period}まとめを生成してください。\n"
            "含む：1) 全体評価 2) よかった点 3) 改善点 4) 励ましの言葉\n"
            "簡潔に、日本語で、300字以内。"
        ),
    },
}

register("sharing", STRINGS)
