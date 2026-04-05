"""Journal plugin translations."""
from src.core.i18n import register

STRINGS: dict[str, dict[str, str]] = {
    "description": {
        "zh": "曾国藩式每日四省反思",
        "en": "Daily four-part reflection",
        "ja": "曾国藩式・毎日四省の振り返り",
    },
    "cmd.start": {
        "zh": "开始今日反思",
        "en": "Start today's reflection",
        "ja": "今日の振り返りを開始",
    },
    "cmd.today": {
        "zh": "查看今日记录",
        "en": "View today's entries",
        "ja": "今日の記録を見る",
    },
    "cmd.cancel": {
        "zh": "取消进行中的反思",
        "en": "Cancel current reflection",
        "ja": "振り返りをキャンセル",
    },
    "already_in_session": {
        "zh": "你已经有一个正在进行的反思。请继续回答，或发送 /journal_cancel 取消。",
        "en": "You already have a reflection in progress. Continue answering, or send /journal_cancel to cancel.",
        "ja": "振り返りが進行中です。回答を続けるか、/journal_cancel でキャンセルしてください。",
    },
    "today_empty": {
        "zh": "今天还没有反思记录。发送 /journal_start 开始吧！",
        "en": "No reflection today. Send /journal_start to begin!",
        "ja": "今日の振り返りはまだありません。/journal_start で始めましょう！",
    },
    "today_header": {
        "zh": "📝 今日反思 ({date}):\n",
        "en": "📝 Today's reflection ({date}):\n",
        "ja": "📝 今日の振り返り ({date}):\n",
    },
    "cancelled": {
        "zh": "已取消当前反思。随时可以用 /journal_start 重新开始。",
        "en": "Reflection cancelled. Use /journal_start anytime to restart.",
        "ja": "振り返りをキャンセルしました。/journal_start でいつでも再開できます。",
    },
    "no_session": {
        "zh": "没有进行中的反思。",
        "en": "No reflection in progress.",
        "ja": "進行中の振り返りはありません。",
    },
    # engine.py
    "flow_complete": {
        "zh": "今日反思已完成。",
        "en": "Today's reflection is complete.",
        "ja": "今日の振り返りが完了しました。",
    },
    "start_section": {
        "zh": "请开始「{label}」部分的引导。",
        "en": "Please guide the \"{label}\" section.",
        "ja": "「{label}」セクションのガイドを始めてください。",
    },
    "continue_section": {
        "zh": "继续，请引导「{label}」部分。",
        "en": "Continue, please guide the \"{label}\" section.",
        "ja": "続けて、「{label}」セクションをガイドしてください。",
    },
    "closing_fallback": {
        "zh": "今天的反思结束了。明天继续加油！",
        "en": "Today's reflection is done. Keep it up tomorrow!",
        "ja": "今日の振り返りは終わりです。明日も頑張りましょう！",
    },
    "closing_system_prompt": {
        "zh": "你是 DailyClaw。用户刚完成今日四省反思。请用 2-3 句温暖的话总结今天，给出一句鼓励。用中文，简洁。",
        "en": "You are DailyClaw. The user just completed today's four-part reflection. Summarize in 2-3 warm sentences and encourage. Be concise, respond in English.",
        "ja": "あなたはDailyClawです。ユーザーが今日の四省の振り返りを完了しました。2-3文で温かくまとめ、励ましてください。日本語で簡潔に。",
    },
    "system_prompt": {
        "zh": (
            "你是 DailyClaw，用户的每日反思助手。\n"
            "你正在引导用户完成曾国藩式每日四省。\n"
            "每次只引导一个部分，用 1-2 个简短问题，语气温暖但不啰嗦。\n"
            "用中文回复。"
        ),
        "en": (
            "You are DailyClaw, the user's daily reflection assistant.\n"
            "You are guiding the user through a four-part daily reflection.\n"
            "Guide one section at a time with 1-2 short questions, warm but concise.\n"
            "Respond in English."
        ),
        "ja": (
            "あなたはDailyClaw、ユーザーの毎日の振り返りアシスタントです。\n"
            "曾国藩式の毎日四省を通じてユーザーをガイドしています。\n"
            "一度に一つのセクションをガイドし、1-2の短い質問で、温かく簡潔に。\n"
            "日本語で回答してください。"
        ),
    },
    "context_prefix": {
        "zh": "\n用户今天发过的消息（供参考）：\n",
        "en": "\nUser's messages today (for reference):\n",
        "ja": "\nユーザーの今日のメッセージ（参考）：\n",
    },
    # scheduler.py
    "evening_reminder": {
        "zh": "今天过得怎么样？用 /journal_start 开始今日反思吧。",
        "en": "How was your day? Start today's reflection with /journal_start.",
        "ja": "今日はどうでしたか？ /journal_start で今日の振り返りを始めましょう。",
    },
    "weekly_summary_header": {
        "zh": "本周总结\n\n{content}",
        "en": "Weekly Summary\n\n{content}",
        "ja": "今週のまとめ\n\n{content}",
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
            "You are DailyClaw's summary assistant. Generate a {period} summary for the user.\n"
            "Include: 1) Overall assessment 2) Things done well 3) Areas for improvement 4) A word of encouragement\n"
            "Concise, respond in English, under 200 words."
        ),
        "ja": (
            "あなたはDailyClawの要約アシスタントです。ユーザーの{period}まとめを生成してください。\n"
            "含む：1) 全体評価 2) よかった点 3) 改善点 4) 励ましの言葉\n"
            "簡潔に、日本語で、300字以内。"
        ),
    },
    "summary_user_prompt": {
        "zh": "时间范围：{start} ~ {end}\n\n日记条目：\n{entries}",
        "en": "Date range: {start} ~ {end}\n\nJournal entries:\n{entries}",
        "ja": "期間：{start} ~ {end}\n\n日記エントリ：\n{entries}",
    },
    # auto-journal (scheduler)
    "auto_journal_notify": {
        "zh": "🌙 今天还没有写反思日记，正在根据你今天的 {count} 条记录自动生成...",
        "en": "🌙 No reflection today — auto-generating journal from your {count} records...",
        "ja": "🌙 今日の振り返りがまだです。{count} 件の記録から自動生成しています...",
    },
    "auto_journal_done": {
        "zh": "📝 已自动生成今日日记：\n\n{content}\n\n查看: /journal_today",
        "en": "📝 Auto-generated today's journal:\n\n{content}\n\nView: /journal_today",
        "ja": "📝 今日の日記を自動生成しました：\n\n{content}\n\n表示: /journal_today",
    },
    "auto_journal_system_prompt": {
        "zh": (
            "你是 DailyClaw，用户的每日反思助手。\n"
            "用户今天没有手动写日记，但发了一些消息。请根据这些消息，按曾国藩四省格式生成简短日记。\n"
            "四省分类：晨起(morning)、所阅(reading)、待人接物(social)、反省(reflection)。\n"
            "如果某个分类没有相关内容，跳过。每个分类 1-2 句话，语气温暖简洁。\n"
        ),
        "en": (
            "You are DailyClaw, the user's daily reflection assistant.\n"
            "The user didn't write a journal today but sent messages. Generate a brief journal.\n"
            "Categories: Morning(morning), Reading(reading), Social(social), Reflection(reflection).\n"
            "Skip categories with no relevant content. 1-2 sentences per category, warm and concise.\n"
        ),
        "ja": (
            "あなたはDailyClaw、ユーザーの毎日の振り返りアシスタントです。\n"
            "ユーザーは今日日記を書きませんでしたが、メッセージを送りました。簡潔な日記を生成してください。\n"
            "分類：朝の振り返り(morning)、読書(reading)、対人関係(social)、反省(reflection)。\n"
            "関連する内容がないカテゴリはスキップ。各カテゴリ1-2文、温かく簡潔に。\n"
        ),
    },
    "auto_journal_format": {
        "zh": "返回严格 JSON（不要 markdown）：\n[{\"category\":\"morning\",\"content\":\"...\"}]",
        "en": "Return strict JSON (no markdown):\n[{\"category\":\"morning\",\"content\":\"...\"}]",
        "ja": "厳密なJSONで返してください（markdownなし）：\n[{\"category\":\"morning\",\"content\":\"...\"}]",
    },
}

register("journal", STRINGS)
