"""Wiki plugin translations."""
from src.core.i18n import register

STRINGS: dict[str, dict[str, str]] = {
    "description": {
        "zh": "个人知识维基 — 自动整理、查询、洞察",
        "en": "Personal knowledge wiki — auto-organize, query, insight",
        "ja": "個人知識Wiki — 自動整理・検索・洞察",
    },
    "cmd.ask": {
        "zh": "向知识库提问",
        "en": "Ask your knowledge wiki",
        "ja": "知識Wikiに質問する",
    },
    "cmd.topics": {
        "zh": "查看所有主题",
        "en": "View all topics",
        "ja": "全トピックを表示",
    },
    "cmd.topic": {
        "zh": "查看具体主题内容",
        "en": "View a specific topic",
        "ja": "特定のトピックを表示",
    },
    "cmd.digest": {
        "zh": "生成本周知识摘要",
        "en": "Generate weekly knowledge digest",
        "ja": "今週の知識ダイジェストを生成",
    },
    "ask_usage": {
        "zh": "用法: /ask <你的问题>\n例如: /ask 我最近在读什么书？",
        "en": "Usage: /ask <your question>\nE.g.: /ask What have I been reading recently?",
        "ja": "使い方: /ask <質問>\n例: /ask 最近何を読んでいましたか？",
    },
    "topics_empty": {
        "zh": "知识库还是空的。随着你每天记录，wiki 会自动整理你的知识。",
        "en": "Your wiki is still empty. As you record daily, the wiki will organize your knowledge.",
        "ja": "Wikiはまだ空です。毎日記録するにつれて、Wikiが自動的に知識を整理します。",
    },
    "topics_header": {
        "zh": "📚 你的知识主题 ({count} 个):\n",
        "en": "📚 Your wiki topics ({count}):\n",
        "ja": "📚 あなたのWikiトピック ({count} 件):\n",
    },
    "topic_usage": {
        "zh": "用法: /topic <主题slug>\n例如: /topic daily-routine",
        "en": "Usage: /topic <topic-slug>\nE.g.: /topic daily-routine",
        "ja": "使い方: /topic <トピックslug>\n例: /topic daily-routine",
    },
    "topic_not_found": {
        "zh": "找不到主题「{topic}」。用 /topics 查看所有主题。",
        "en": "Topic \"{topic}\" not found. Use /topics to see all topics.",
        "ja": "トピック「{topic}」が見つかりません。/topics で全トピックを確認してください。",
    },
    "no_links": {
        "zh": "无关联主题",
        "en": "No linked topics",
        "ja": "関連トピックなし",
    },
    "digest_empty": {
        "zh": "本周没有更新的知识页面。",
        "en": "No wiki pages were updated this week.",
        "ja": "今週更新されたWikiページはありません。",
    },
    "digest_header": {
        "zh": "📊 本周知识摘要\n\n",
        "en": "📊 Weekly Knowledge Digest\n\n",
        "ja": "📊 今週の知識ダイジェスト\n\n",
    },
}

register("wiki", STRINGS)
