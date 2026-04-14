"""Reflect plugin translations."""
from src.core.i18n import register

STRINGS: dict[str, dict[str, str]] = {
    "description": {
        "zh": "曾国藩式每日四省反思",
        "en": "Daily four-part reflection",
        "ja": "曾国藩式・毎日四省の振り返り",
    },
    "cmd.reflect": {
        "zh": "开始今日反思",
        "en": "Start today's reflection",
        "ja": "今日の振り返りを開始",
    },
    "cmd.cancel": {
        "zh": "取消进行中的反思",
        "en": "Cancel current reflection",
        "ja": "振り返りをキャンセル",
    },
    "cmd.review": {
        "zh": "回顾日记 (用法: /review [YYYY-MM-DD])",
        "en": "Review journal (usage: /review [YYYY-MM-DD])",
        "ja": "日記を振り返る (使い方: /review [YYYY-MM-DD])",
    },
    "review_usage": {
        "zh": "用法: /review [起始日期]\n例如: /review 2026-04-01\n默认回顾最近 7 天。",
        "en": "Usage: /review [start date]\nE.g.: /review 2026-04-01\nDefaults to last 7 days.",
        "ja": "使い方: /review [開始日]\n例: /review 2026-04-01\nデフォルトは過去7日間。",
    },
    "today_system_prompt": {
        "zh": (
            "你是 DailyClaw 的日记编辑。用户今天记录了一些反思条目（可能有重复）。\n"
            "请整理成一篇简洁可读的今日日记，要求：\n"
            "1. 去除重复内容，合并同类条目\n"
            "2. 按四省分类（晨起、所阅、待人接物、反省）组织，用 emoji 标记\n"
            "3. 适当修饰语言使其流畅，但保留原意，不要添油加醋\n"
            "4. 忠实记录，不要加感慨或无中生有的内容\n"
            "5. 用中文，300字以内\n"
            "不要输出标题。"
        ),
        "en": (
            "You are DailyClaw's diary editor. The user recorded reflection entries today (may have duplicates).\n"
            "Polish into a concise daily diary:\n"
            "1. Remove duplicates, merge similar entries\n"
            "2. Organize by four categories (Morning, Reading, Social, Reflection) with emoji markers\n"
            "3. Improve flow while preserving meaning — do not embellish\n"
            "4. Be faithful — do not add sentiments the user didn't express\n"
            "5. Under 200 words, in English\n"
            "Do not output a title."
        ),
        "ja": (
            "あなたはDailyClawの日記エディターです。ユーザーが今日記録した振り返り（重複あり）を整理してください。\n"
            "簡潔な日記にまとめてください：\n"
            "1. 重複を削除、類似項目を統合\n"
            "2. 四省分類（朝・読書・対人・反省）でemoji付きで整理\n"
            "3. 元の意味を保持し脚色しない\n"
            "4. 記録に忠実に\n"
            "5. 日本語で300字以内\n"
            "タイトルは出力しない。"
        ),
    },
    "already_in_session": {
        "zh": "你已经有一个正在进行的反思。请继续回答，或发送 /cancel 取消。",
        "en": "You already have a reflection in progress. Continue answering, or send /cancel to cancel.",
        "ja": "振り返りが進行中です。回答を続けるか、/cancel でキャンセルしてください。",
    },
    "today_empty": {
        "zh": "今天还没有反思记录。发送 /reflect 开始吧！",
        "en": "No reflection today. Send /reflect to begin!",
        "ja": "今日の振り返りはまだありません。/reflect で始めましょう！",
    },
    "today_header": {
        "zh": "📝 今日反思 ({date}):\n",
        "en": "📝 Today's reflection ({date}):\n",
        "ja": "📝 今日の振り返り ({date}):\n",
    },
    "cancelled": {
        "zh": "已取消当前反思。随时可以用 /reflect 重新开始。",
        "en": "Reflection cancelled. Use /reflect anytime to restart.",
        "ja": "振り返りをキャンセルしました。/reflect でいつでも再開できます。",
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
    "step_indicator": {
        "zh": "📝 第 {step}/{total} 部分：{label}\n\n",
        "en": "📝 Part {step}/{total}: {label}\n\n",
        "ja": "📝 パート {step}/{total}：{label}\n\n",
    },
    "closing_fallback": {
        "zh": "───── ✅ 今日反思完成 ─────\n\n今天的反思结束了。明天继续加油！",
        "en": "───── ✅ Reflection Complete ─────\n\nToday's reflection is done. Keep it up tomorrow!",
        "ja": "───── ✅ 振り返り完了 ─────\n\n今日の振り返りは終わりです。明日も頑張りましょう！",
    },
    "closing_header": {
        "zh": "───── ✅ 今日反思完成 ─────\n\n",
        "en": "───── ✅ Reflection Complete ─────\n\n",
        "ja": "───── ✅ 振り返り完了 ─────\n\n",
    },
    "closing_footer": {
        "zh": "\n\n📖 查看完整记录: /review",
        "en": "\n\n📖 View full record: /review",
        "ja": "\n\n📖 全記録を表示: /review",
    },
    "closing_system_prompt": {
        "zh": "你是 DailyClaw。用户刚完成今日四省反思。请用 2-3 句温暖的话总结今天，给出一句鼓励。用中文，简洁。不要输出标题或分隔线。",
        "en": "You are DailyClaw. The user just completed today's four-part reflection. Summarize in 2-3 warm sentences and encourage. Be concise, respond in English. Do not output headers or separators.",
        "ja": "あなたはDailyClawです。ユーザーが今日の四省の振り返りを完了しました。2-3文で温かくまとめ、励ましてください。日本語で簡潔に。タイトルや区切り線は出力しないでください。",
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
        "zh": "今天过得怎么样？用 /reflect 开始今日反思吧。",
        "en": "How was your day? Start today's reflection with /reflect.",
        "ja": "今日はどうでしたか？ /reflect で今日の振り返りを始めましょう。",
    },
    "weekly_summary_header": {
        "zh": "本周总结\n\n{content}",
        "en": "Weekly Summary\n\n{content}",
        "ja": "今週のまとめ\n\n{content}",
    },
    # summary.py
    "no_entries": {
        "zh": "{period}没有记录。开始用 /reflect 记录每天的反思吧！",
        "en": "No entries for {period}. Start recording daily reflections with /reflect!",
        "ja": "{period}の記録がありません。/reflect で毎日の振り返りを始めましょう！",
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
            "あなたはDailyClawの要約アシスタントです。ユーザーの{period}まとめを生成してください。\n"
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
    "summary_user_prompt": {
        "zh": "时间范围：{start} ~ {end}\n\n日记条目：\n{entries}",
        "en": "Date range: {start} ~ {end}\n\nJournal entries:\n{entries}",
        "ja": "期間：{start} ~ {end}\n\n日記エントリ：\n{entries}",
    },
    # auto-reflect (scheduler)
    "auto_journal_notify": {
        "zh": "🌙 今天还没有写反思日记，正在根据你今天的 {count} 条记录自动生成...",
        "en": "🌙 No reflection today — auto-generating journal from your {count} records...",
        "ja": "🌙 今日の振り返りがまだです。{count} 件の記録から自動生成しています...",
    },
    "auto_journal_done": {
        "zh": "📝 已自动生成今日日记：\n\n{content}",
        "en": "📝 Auto-generated today's journal:\n\n{content}",
        "ja": "📝 今日の日記を自動生成しました：\n\n{content}",
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

register("reflect", STRINGS)
