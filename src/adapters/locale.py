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
}

register("adapter", STRINGS)
