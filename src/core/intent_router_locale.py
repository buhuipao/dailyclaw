"""Intent router translations."""
from src.core.i18n import register

STRINGS: dict[str, dict[str, str]] = {
    "fallback_hint": {
        "zh": "💡 如果我没理解你的意图，请描述得更详细一点，或直接使用 /help 查看指令。",
        "en": "💡 If I didn't catch your intent, try being more specific or use /help to see commands.",
        "ja": "💡 意図が伝わらなかった場合は、もう少し詳しく説明するか、/help でコマンドを確認してください。",
    },
}

register("intent_router", STRINGS)
