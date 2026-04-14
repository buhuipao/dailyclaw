CREATE TABLE IF NOT EXISTS wiki_pages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    topic        TEXT NOT NULL,
    title        TEXT NOT NULL,
    content      TEXT NOT NULL,
    links        TEXT DEFAULT '[]',
    page_type    TEXT DEFAULT 'organic',
    source_count INTEGER DEFAULT 0,
    last_ingest  TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, topic)
);

CREATE INDEX IF NOT EXISTS idx_wiki_pages_user ON wiki_pages(user_id, updated_at);

CREATE TABLE IF NOT EXISTS wiki_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    op         TEXT NOT NULL,
    detail     TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_wiki_log_user ON wiki_log(user_id, created_at);
