-- Add soft-delete column to messages table.
-- Uses a conditional approach safe for both fresh and existing databases.
ALTER TABLE messages ADD COLUMN deleted_at TEXT;

CREATE INDEX IF NOT EXISTS idx_messages_not_deleted ON messages(user_id, deleted_at);
