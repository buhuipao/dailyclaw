"""Main module translations — /start, /help, /invite, /kick."""
from src.core.i18n import register

STRINGS: dict[str, dict[str, str]] = {
    "help_header": {
        "zh": "🦉 *DailyClaw 指令列表*\n",
        "en": "🦉 *DailyClaw Commands*\n",
        "ja": "🦉 *DailyClaw コマンド一覧*\n",
    },
    "help_admin_section": {
        "zh": "🔑 *管理员*",
        "en": "🔑 *Admin*",
        "ja": "🔑 *管理者*",
    },
    "help_invite": {
        "zh": "  /invite <user_id> — 邀请用户",
        "en": "  /invite <user_id> — Invite user",
        "ja": "  /invite <user_id> — ユーザーを招待",
    },
    "help_kick": {
        "zh": "  /kick <user_id> — 踢出用户",
        "en": "  /kick <user_id> — Remove user",
        "ja": "  /kick <user_id> — ユーザーを削除",
    },
    "help_lang": {
        "zh": "  /lang <zh|en|ja> — 切换语言",
        "en": "  /lang <zh|en|ja> — Switch language",
        "ja": "  /lang <zh|en|ja> — 言語切替",
    },
    "help_footer": {
        "zh": "💡 /start — 欢迎消息 | /help — 显示帮助",
        "en": "💡 /start — Welcome | /help — Show help",
        "ja": "💡 /start — ようこそ | /help — ヘルプ表示",
    },
    "admin_suffix": {
        "zh": " (管理员)",
        "en": " (admin)",
        "ja": " (管理者)",
    },
    "welcome": {
        "zh": "欢迎使用 DailyClaw！发送 /help 查看指令列表。",
        "en": "Welcome to DailyClaw! Send /help to see available commands.",
        "ja": "DailyClawへようこそ！/help でコマンド一覧を確認できます。",
    },
    "cmd.start": {
        "zh": "欢迎消息",
        "en": "Welcome",
        "ja": "ようこそ",
    },
    "cmd.help": {
        "zh": "显示帮助",
        "en": "Show help",
        "ja": "ヘルプ表示",
    },
    "cmd.invite": {
        "zh": "邀请用户",
        "en": "Invite user",
        "ja": "ユーザーを招待",
    },
    "cmd.kick": {
        "zh": "踢出用户",
        "en": "Remove user",
        "ja": "ユーザーを削除",
    },
    "invite_usage": {
        "zh": "用法: /invite <user_id>",
        "en": "Usage: /invite <user_id>",
        "ja": "使い方: /invite <user_id>",
    },
    "kick_usage": {
        "zh": "用法: /kick <user_id>",
        "en": "Usage: /kick <user_id>",
        "ja": "使い方: /kick <user_id>",
    },
    "invalid_user_id": {
        "zh": "无效的 user_id: {id}",
        "en": "Invalid user_id: {id}",
        "ja": "無効な user_id: {id}",
    },
    "invite_success": {
        "zh": "已邀请用户 {id}",
        "en": "User {id} invited",
        "ja": "ユーザー {id} を招待しました",
    },
    "kick_success": {
        "zh": "已踢出用户 {id}",
        "en": "User {id} removed",
        "ja": "ユーザー {id} を削除しました",
    },
    "lang_usage": {
        "zh": "🌐 切换语言 / Switch language\n\n当前: {current}\n\n可选语言:\n  /lang zh — 中文\n  /lang en — English\n  /lang ja — 日本語",
        "en": "🌐 Switch language\n\nCurrent: {current}\n\nAvailable:\n  /lang zh — 中文\n  /lang en — English\n  /lang ja — 日本語",
        "ja": "🌐 言語切替\n\n現在: {current}\n\n利用可能:\n  /lang zh — 中文\n  /lang en — English\n  /lang ja — 日本語",
    },
    "lang_invalid": {
        "zh": "❌ 不支持的语言: {lang}\n\n可选语言:\n  zh — 中文\n  en — English\n  ja — 日本語",
        "en": "❌ Unsupported language: {lang}\n\nAvailable:\n  zh — 中文\n  en — English\n  ja — 日本語",
        "ja": "❌ サポートされていない言語: {lang}\n\n利用可能:\n  zh — 中文\n  en — English\n  ja — 日本語",
    },
    "lang_success": {
        "zh": "语言已切换为: {lang_name}",
        "en": "Language changed to: {lang_name}",
        "ja": "言語を変更しました: {lang_name}",
    },
}

register("main", STRINGS)
