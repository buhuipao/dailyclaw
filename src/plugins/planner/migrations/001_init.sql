CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    name TEXT NOT NULL,
    schedule TEXT NOT NULL DEFAULT 'daily',
    remind_time TEXT NOT NULL DEFAULT '20:00',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS plan_checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    date TEXT NOT NULL,
    note TEXT DEFAULT '',
    duration_minutes INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_plans_user_active ON plans(user_id, active);
CREATE INDEX IF NOT EXISTS idx_checkins_user_tag_date ON plan_checkins(user_id, tag, date);
