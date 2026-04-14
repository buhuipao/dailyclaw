"""Track plugin translations."""
from src.core.i18n import register

STRINGS: dict[str, dict[str, str]] = {
    "description": {
        "zh": "计划与打卡 — 目标跟踪和智能匹配",
        "en": "Plans & check-ins — goal tracking with smart matching",
        "ja": "計画とチェックイン — 目標追跡とスマートマッチング",
    },
    "cmd.goal": {"zh": "创建新计划", "en": "Create a new plan", "ja": "新しい計画を作成"},
    "cmd.drop": {"zh": "归档计划", "en": "Archive a plan", "ja": "計画をアーカイブ"},
    "cmd.checkin": {"zh": "智能打卡", "en": "Smart check-in", "ja": "スマートチェックイン"},
    "cmd.goals": {"zh": "查看计划进度", "en": "View plan progress", "ja": "計画の進捗を見る"},
    # goal (add)
    "add_usage": {
        "zh": "用法: /goal <描述>\n例如: /goal 每天学雅思，晚上8点提醒\n例如: /goal 每周一三五锻炼，7点提醒",
        "en": "Usage: /goal <description>\nE.g.: /goal Study IELTS daily, remind at 8pm\nE.g.: /goal Exercise Mon/Wed/Fri, remind at 7am",
        "ja": "使い方: /goal <説明>\n例: /goal 毎日IELTS勉強、夜8時リマインド\n例: /goal 月水金運動、朝7時リマインド",
    },
    "add_parse_fail": {
        "zh": "没有理解你的计划，请再描述一下？",
        "en": "I didn't understand your plan. Could you describe it again?",
        "ja": "計画を理解できませんでした。もう一度説明してください。",
    },
    "add_duplicate": {
        "zh": "已存在同名计划 [{tag}]，请换个描述或先 /drop 旧的。",
        "en": "Plan [{tag}] already exists. Use a different name or /drop the old one first.",
        "ja": "計画 [{tag}] は既に存在します。別の名前にするか、先に /drop で削除してください。",
    },
    "add_success": {
        "zh": "已创建计划「{name}」\n标签: {tag}\n频率: {schedule}\n提醒: {remind}\n\n用自然语言打卡: /checkin 今天练了30分钟听力",
        "en": "Plan \"{name}\" created\nTag: {tag}\nFrequency: {schedule}\nReminder: {remind}\n\nCheck in with: /checkin practiced listening for 30 min",
        "ja": "計画「{name}」を作成しました\nタグ: {tag}\n頻度: {schedule}\nリマインド: {remind}\n\n自然言語でチェックイン: /checkin リスニング30分練習した",
    },
    # drop (del)
    "del_usage": {
        "zh": "用法: /drop <计划名称或标签>",
        "en": "Usage: /drop <plan name or tag>",
        "ja": "使い方: /drop <計画名またはタグ>",
    },
    "del_no_plans": {
        "zh": "你还没有任何计划。",
        "en": "You don't have any plans yet.",
        "ja": "まだ計画がありません。",
    },
    "del_no_match": {
        "zh": "没有匹配到计划。你的计划：\n{list}",
        "en": "No matching plan found. Your plans:\n{list}",
        "ja": "一致する計画が見つかりません。あなたの計画：\n{list}",
    },
    "del_success": {
        "zh": "已归档计划「{name}」[{tag}]",
        "en": "Archived plan \"{name}\" [{tag}]",
        "ja": "計画「{name}」[{tag}] をアーカイブしました",
    },
    "del_not_found": {
        "zh": "未找到活跃的计划 [{tag}]",
        "en": "No active plan found [{tag}]",
        "ja": "アクティブな計画 [{tag}] が見つかりません",
    },
    # checkin
    "checkin_usage": {
        "zh": "用法: /checkin <描述>\n例如: /checkin 今天练了半小时雅思听力\n例如: /checkin 跑了5公里",
        "en": "Usage: /checkin <description>\nE.g.: /checkin Practiced IELTS listening for 30 min\nE.g.: /checkin Ran 5km",
        "ja": "使い方: /checkin <説明>\n例: /checkin IELTSリスニング30分練習した\n例: /checkin 5km走った",
    },
    "checkin_no_plans": {
        "zh": "你还没有计划。用 /goal 创建一个吧！",
        "en": "You don't have any plans yet. Create one with /goal!",
        "ja": "まだ計画がありません。/goal で作成しましょう！",
    },
    "checkin_no_match": {
        "zh": "没有匹配到计划。你的计划有：{names}\n请再描述一下？",
        "en": "No matching plan found. Your plans: {names}\nCould you describe again?",
        "ja": "一致する計画がありません。計画一覧：{names}\nもう一度説明してください。",
    },
    "checkin_success": {
        "zh": "已打卡：{name}",
        "en": "Checked in: {name}",
        "ja": "チェックイン：{name}",
    },
    "checkin_week_count": {
        "zh": "\n本周已打卡 {count} 天",
        "en": "\n{count} days checked in this week",
        "ja": "\n今週 {count} 日チェックイン済み",
    },
    # goals (list)
    "list_empty": {
        "zh": "还没有计划。用 /goal 创建一个吧！",
        "en": "No plans yet. Create one with /goal!",
        "ja": "まだ計画がありません。/goal で作成しましょう！",
    },
    "list_header": {
        "zh": "📋 计划进度\n",
        "en": "📋 Plan Progress\n",
        "ja": "📋 計画の進捗\n",
    },
    "list_no_checkins": {
        "zh": "   暂无打卡记录",
        "en": "   No check-ins yet",
        "ja": "   チェックイン記録なし",
    },
    "list_recent_header": {
        "zh": "   最近打卡:",
        "en": "   Recent check-ins:",
        "ja": "   最近のチェックイン:",
    },
    "list_frequency": {
        "zh": "   频率: {schedule} | 提醒: {remind}",
        "en": "   Frequency: {schedule} | Reminder: {remind}",
        "ja": "   頻度: {schedule} | リマインド: {remind}",
    },
    "list_week_bar": {
        "zh": "   本周: {bar} {done}/{expected}",
        "en": "   This week: {bar} {done}/{expected}",
        "ja": "   今週: {bar} {done}/{expected}",
    },
    # scheduler.py reminder
    "reminder": {
        "zh": "今天的「{name}」还没打卡哦，还在计划中吗？\n用 /checkin {tag} <备注> 来打卡",
        "en": "Haven't checked in for \"{name}\" today. Still on track?\nUse /checkin {tag} <note> to check in",
        "ja": "今日の「{name}」はまだチェックインしていません。\n/checkin {tag} <メモ> でチェックイン",
    },
    "minutes": {
        "zh": "{n}分钟",
        "en": "{n} min",
        "ja": "{n}分",
    },
}

register("track", STRINGS)
