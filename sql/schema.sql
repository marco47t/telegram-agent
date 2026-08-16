-- Run once against a fresh database:
--   psql "$DATABASE_URL" -f sql/schema.sql

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    telegram_id     BIGINT UNIQUE NOT NULL,
    name            TEXT,
    timezone        TEXT DEFAULT 'UTC',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversations (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id                 BIGSERIAL PRIMARY KEY,
    conversation_id    INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role               TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content            TEXT NOT NULL,
    route              TEXT,               -- 'trivial' | 'simple' | 'complex'
    distilled          BOOLEAN NOT NULL DEFAULT FALSE,  -- has this been run through memory distillation yet?
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_undistilled ON messages(user_id, distilled) WHERE distilled = FALSE;

-- One row per distilled fact. vector_id links to the matching ChromaDB entry
-- so this table stays the source of truth if the vector index ever needs rebuilding.
CREATE TABLE IF NOT EXISTS memory_entries (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content         TEXT NOT NULL,
    category        TEXT NOT NULL,   -- 'preference' | 'fact' | 'event' | 'project_context'
    vector_id       TEXT UNIQUE NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reminders (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text            TEXT NOT NULL,
    due_at          TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'sent' | 'cancelled'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(due_at) WHERE status = 'pending';
