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
        "zh": "AI 整理日记 (用法: /sharing_export [YYYY-MM-DD])",
        "en": "AI-polished diary (usage: /sharing_export [YYYY-MM-DD])",
        "ja": "AI整理日記 (使い方: /sharing_export [YYYY-MM-DD])",
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
    "export_system_prompt": {
        "zh": (
            "你是 DailyClaw 的日记编辑。用户今天记录了一些零散的消息和反思。\n"
            "请将这些内容整理成一篇简洁可读的日记，要求：\n"
            "1. 去除重复内容，合并相似条目\n"
            "2. 适当修饰语言，使其更流畅，但保留原意，不要添油加醋\n"
            "3. 按时间或主题组织，用清晰的段落结构\n"
            "4. 如果有反思/日记条目，作为重点突出\n"
            "5. 忠实记录，不要加感慨、鸡汤或无中生有的内容\n"
            "6. 用中文，300字以内，语气像写给自己看的日记\n"
            "不要输出标题，我会自己加。"
        ),
        "en": (
            "You are DailyClaw's diary editor. The user recorded scattered messages and reflections today.\n"
            "Polish them into a concise, readable diary entry:\n"
            "1. Remove duplicates, merge similar items\n"
            "2. Improve language flow while preserving original meaning — do not embellish\n"
            "3. Organize by time or theme with clear paragraphs\n"
            "4. Highlight reflection/journal entries as key moments\n"
            "5. Be faithful to the records — do not add sentiments or insights the user didn't express\n"
            "6. Respond in English, under 200 words, personal diary tone\n"
            "Do not output a title, I will add it."
        ),
        "ja": (
            "あなたはDailyClawの日記エディターです。ユーザーが今日記録した散発的なメッセージと振り返りを整理してください。\n"
            "簡潔で読みやすい日記にまとめてください：\n"
            "1. 重複を削除し、類似項目を統合\n"
            "2. 言葉遣いを改善し、元の意味を保持。脚色しない\n"
            "3. 時間やテーマごとに段落で整理\n"
            "4. 振り返りの内容を重点的に扱う\n"
            "5. 記録に忠実に。ユーザーが表現していない感想を加えない\n"
            "6. 日本語で、300字以内、自分の日記のような口調で\n"
            "タイトルは出力しないでください。"
        ),
    },
    "export_generating": {
        "zh": "✍️ 正在用 AI 整理 {date} 的 {count} 条记录...",
        "en": "✍️ AI is polishing {count} records from {date}...",
        "ja": "✍️ {date} の {count} 件の記録をAIで整理中...",
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
            "格式要求（严格遵守）：\n"
            "- 用 emoji 开头标记每个段落，不要用 markdown（不要用 ** 或 # 等符号）\n"
            "- 结构：\n"
            "  🔍 整体评价（1-2句）\n"
            "  ✅ 做得好的地方（列举要点）\n"
            "  💡 可以改进的地方（列举要点）\n"
            "  💪 一句鼓励\n"
            "简洁有力，用中文，300字以内。"
        ),
        "en": (
            "You are DailyClaw's summary assistant. Generate a {period} summary.\n"
            "Format rules (strictly follow):\n"
            "- Use emoji to mark each section, NO markdown (no ** or # symbols)\n"
            "- Structure:\n"
            "  🔍 Overall assessment (1-2 sentences)\n"
            "  ✅ What went well (bullet points)\n"
            "  💡 Areas for improvement (bullet points)\n"
            "  💪 One line of encouragement\n"
            "Concise, respond in English, under 200 words."
        ),
        "ja": (
            "あなたはDailyClawの要約アシスタントです。{period}まとめを生成してください。\n"
            "フォーマット（厳守）：\n"
            "- 各段落の先頭にemojiを付ける。markdownは使わない（** や # は禁止）\n"
            "- 構成：\n"
            "  🔍 全体評価（1-2文）\n"
            "  ✅ よかった点（箇条書き）\n"
            "  💡 改善点（箇条書き）\n"
            "  💪 励ましの一言\n"
            "簡潔に、日本語で、300字以内。"
        ),
    },
}

register("sharing", STRINGS)
