"""Memo plugin translations."""
from src.core.i18n import register

STRINGS: dict[str, dict[str, str]] = {
    # commands.py
    "heatmap_title": {
        "zh": "📊 记录热力图",
        "en": "📊 Recording Heatmap",
        "ja": "📊 記録ヒートマップ",
    },
    "heatmap_caption": {
        "zh": "📊 记录热力图\n共 {total} 条记录，活跃 {days} 天",
        "en": "📊 Recording Heatmap\n{total} records, {days} active days",
        "ja": "📊 記録ヒートマップ\n{total} 件の記録、{days} 日間アクティブ",
    },
    "del_usage": {
        "zh": "❌ 请提供要删除的记录 ID，例如：/del 42",
        "en": "❌ Please provide a record ID, e.g.: /del 42",
        "ja": "❌ 記録IDを指定してください。例：/del 42",
    },
    "del_invalid_id": {
        "zh": "❌ 记录 ID 必须是正整数。",
        "en": "❌ Record ID must be a positive integer.",
        "ja": "❌ 記録IDは正の整数でなければなりません。",
    },
    "del_not_found": {
        "zh": "❌ 找不到记录 #{id}。",
        "en": "❌ Record #{id} not found.",
        "ja": "❌ 記録 #{id} が見つかりません。",
    },
    "del_no_permission": {
        "zh": "❌ 你无权删除此记录。",
        "en": "❌ You don't have permission to delete this record.",
        "ja": "❌ この記録を削除する権限がありません。",
    },
    "del_already_deleted": {
        "zh": "❌ 记录 #{id} 已经删除过了。",
        "en": "❌ Record #{id} has already been deleted.",
        "ja": "❌ 記録 #{id} は既に削除されています。",
    },
    "del_success": {
        "zh": "✅ 记录 #{id} 已删除。",
        "en": "✅ Record #{id} deleted.",
        "ja": "✅ 記録 #{id} を削除しました。",
    },
    "today_empty": {
        "zh": "📭 {date} 还没有记录。随时发消息给我吧！",
        "en": "📭 No records for {date}. Send me a message anytime!",
        "ja": "📭 {date} の記録はまだありません。いつでもメッセージを送ってください！",
    },
    "today_header": {
        "zh": "📅 {date} 今日记录 ({count} 条)\n",
        "en": "📅 {date} Today's records ({count} entries)\n",
        "ja": "📅 {date} 今日の記録 ({count} 件)\n",
    },
    "today_more": {
        "zh": "\n  ...还有 {count} 条更早的记录",
        "en": "\n  ...and {count} earlier records",
        "ja": "\n  ...他に {count} 件の記録",
    },
    # handlers.py
    "dedup_skip": {
        "zh": "这条消息刚刚已经记录过了，不会重复保存。",
        "en": "This message was just recorded, no duplicate saved.",
        "ja": "このメッセージは既に記録済みです。重複保存はしません。",
    },
    "text_updated": {
        "zh": "已更新今日「{cat}」(#{id})。",
        "en": "Updated today's \"{cat}\" (#{id}).",
        "ja": "本日の「{cat}」を更新しました (#{id})。",
    },
    "text_recorded": {
        "zh": "已记录到今日「{cat}」(#{id})。",
        "en": "Recorded to today's \"{cat}\" (#{id}).",
        "ja": "本日の「{cat}」に記録しました (#{id})。",
    },
    "url_summary_label": {
        "zh": "\n\n🔗 链接摘要：\n{summary}",
        "en": "\n\n🔗 Link summary:\n{summary}",
        "ja": "\n\n🔗 リンク要約：\n{summary}",
    },
    "text_more_prompt": {
        "zh": "\n\n有更多想补充的吗？",
        "en": "\n\nAnything else to add?",
        "ja": "\n\n他に補足はありますか？",
    },
    "delete_hint": {
        "zh": "\n\n有误？发送 /del {id}",
        "en": "\n\nWrong? Send /del {id}",
        "ja": "\n\n間違い？ /del {id} で削除",
    },
    "photo_recorded": {
        "zh": "📷 图片已记录 (#{id})。",
        "en": "📷 Photo recorded (#{id}).",
        "ja": "📷 画像を記録しました (#{id})。",
    },
    "photo_note": {
        "zh": "\n备注: {caption}",
        "en": "\nNote: {caption}",
        "ja": "\nメモ: {caption}",
    },
    "photo_analysis": {
        "zh": "\n\n🔍 图片理解：\n{analysis}",
        "en": "\n\n🔍 Image analysis:\n{analysis}",
        "ja": "\n\n🔍 画像分析：\n{analysis}",
    },
    "voice_recorded": {
        "zh": "🎤 语音已记录 (#{id})。",
        "en": "🎤 Voice recorded (#{id}).",
        "ja": "🎤 音声を記録しました (#{id})。",
    },
    "video_recorded": {
        "zh": "🎬 视频已记录 (#{id})。",
        "en": "🎬 Video recorded (#{id}).",
        "ja": "🎬 動画を記録しました (#{id})。",
    },
    "video_note": {
        "zh": "\n备注: {caption}",
        "en": "\nNote: {caption}",
        "ja": "\nメモ: {caption}",
    },
    "media_placeholder.photo": {
        "zh": "[图片]",
        "en": "[Photo]",
        "ja": "[画像]",
    },
    "media_placeholder.voice": {
        "zh": "[语音消息]",
        "en": "[Voice message]",
        "ja": "[音声メッセージ]",
    },
    "media_placeholder.video": {
        "zh": "[视频]",
        "en": "[Video]",
        "ja": "[動画]",
    },
    "retry_done": {
        "zh": "✅ 之前失败的消息已处理完成 (#{id})。",
        "en": "✅ Previously failed message processed (#{id}).",
        "ja": "✅ 以前失敗したメッセージを処理しました (#{id})。",
    },
    "retry_type.photo": {"zh": "图片", "en": "photo", "ja": "画像"},
    "retry_type.voice": {"zh": "语音", "en": "voice", "ja": "音声"},
    "retry_type.video": {"zh": "视频", "en": "video", "ja": "動画"},
    "retry_backfill": {
        "zh": "[{type}，补录]",
        "en": "[{type}, backfill]",
        "ja": "[{type}、再記録]",
    },
    "retry_media_done": {
        "zh": "✅ 之前失败的{type}已补录 (#{id})。",
        "en": "✅ Previously failed {type} backfilled (#{id}).",
        "ja": "✅ 以前失敗した{type}を再記録しました (#{id})。",
    },
    # Plugin description
    "description": {
        "zh": "消息记录 — 自动分类、去重、URL摘要",
        "en": "Message recorder — auto-classify, dedup, URL summary",
        "ja": "メッセージ記録 — 自動分類・重複排除・URL要約",
    },
    "cmd.today": {
        "zh": "查看今日记录",
        "en": "View today's records",
        "ja": "今日の記録を見る",
    },
    "cmd.del": {
        "zh": "删除一条记录",
        "en": "Delete a record",
        "ja": "記録を削除",
    },
    "cmd.heatmap": {
        "zh": "记录热力图",
        "en": "Recording heatmap",
        "ja": "記録ヒートマップ",
    },
}

register("memo", STRINGS)
