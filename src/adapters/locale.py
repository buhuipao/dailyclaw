"""Adapter-level translations."""
from src.core.i18n import register

STRINGS: dict[str, dict[str, str]] = {
    "ack_processing": {
        "zh": "⏳ 收到，正在处理...",
        "en": "⏳ Got it, processing...",
        "ja": "⏳ 受信しました、処理中...",
    },
    "retry_fail": {
        "zh": "⏳ 处理暂时失败，稍后会自动重试。",
        "en": "⏳ Processing failed, will retry automatically.",
        "ja": "⏳ 処理に失敗しました。自動的にリトライします。",
    },
    "unknown_command": {
        "zh": "❓ 命令 {cmd} 不存在\n\n发送 /help 查看所有可用命令",
        "en": "❓ Command {cmd} not found\n\nSend /help to see available commands",
        "ja": "❓ コマンド {cmd} は存在しません\n\n/help で利用可能なコマンドを確認",
    },
    "no_permission": {
        "zh": "⛔ 无权限",
        "en": "⛔ No permission",
        "ja": "⛔ 権限がありません",
    },
    "trial_rate_limit": {
        "zh": "⏸ 发送太快了，请稍等一分钟再试。\n（试用用户限制: {rate} 条/分钟）",
        "en": "⏸ Slow down! Please wait a minute before sending more.\n(Trial limit: {rate} msgs/min)",
        "ja": "⏸ 送信が速すぎます。1分後に再度お試しください。\n（トライアル制限: {rate} 件/分）",
    },
    "trial_daily_quota": {
        "zh": "📊 今日试用额度已用完（{quota} 条/天）。\n\n想要无限使用？请联系管理员获取邀请: tg://user?id={admin_id}",
        "en": "📊 Daily trial quota reached ({quota} msgs/day).\n\nWant unlimited access? Contact the admin: tg://user?id={admin_id}",
        "ja": "📊 本日のトライアル上限に達しました（{quota} 件/日）。\n\n無制限利用は管理者に連絡: tg://user?id={admin_id}",
    },
}

register("adapter", STRINGS)
