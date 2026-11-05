-- SQLite schema for the Garuda Purana Q&A app.
-- The database is a build artifact: scripts/ingest.py recreates the knowledge-base
-- tables from data/passages.json (the reviewed source of truth).

PRAGMA foreign_keys = ON;

-- Editions / translations. Each language layer of a passage points to one of these.
CREATE TABLE IF NOT EXISTS sources (
    id            TEXT PRIMARY KEY,          -- 'wood1911', 'gitapress1416'
    title         TEXT NOT NULL,
    translator    TEXT,
    publisher     TEXT,
    year          INTEGER,
    languages     TEXT NOT NULL,             -- 'en' | 'sa,hi'
    url           TEXT,
    license_note  TEXT
);

-- One row per knowledge-base passage. Text columns are stored verbatim from the sources
-- and are never written by the LLM.
CREATE TABLE IF NOT EXISTS passages (
    id                  TEXT PRIMARY KEY,    -- 'GPS-02-015' = Saroddhara ch.2 from v.15
    khanda              TEXT NOT NULL,
    chapter             INTEGER NOT NULL,
    chapter_title       TEXT NOT NULL,
    verse_ref_en        TEXT,                -- verse numbering of the English edition
    verse_ref_sa        TEXT,                -- verse numbering of the Sanskrit edition
    sanskrit            TEXT,                -- optional ("wherever available")
    hindi               TEXT NOT NULL,
    english             TEXT NOT NULL,
    sanskrit_source_id  TEXT REFERENCES sources(id),
    hindi_source_id     TEXT NOT NULL REFERENCES sources(id),
    english_source_id   TEXT NOT NULL REFERENCES sources(id),
    page_en             TEXT,
    page_sa             TEXT,
    keywords            TEXT NOT NULL,       -- JSON array
    topics              TEXT NOT NULL,       -- JSON array
    notes               TEXT,
    embedding           BLOB,                -- float32 vector, L2-normalised
    embedding_model     TEXT
);

CREATE INDEX IF NOT EXISTS idx_passages_chapter ON passages(chapter);

-- Chat history (written by POST /ask).
CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,            -- UUID from the client / server
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id  TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role             TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content          TEXT NOT NULL,
    language         TEXT,
    cited_ids        TEXT,                   -- JSON array of passage ids
    model_used       TEXT,
    answerable       INTEGER,
    latency_ms       INTEGER,
    created_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id);
