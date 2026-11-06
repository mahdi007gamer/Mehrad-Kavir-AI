"""Idempotent additive migrations; keeps existing v0.1 customer data intact."""
import sqlite3
from . import db

SQL = """
CREATE TABLE IF NOT EXISTS knowledge_revisions (
 id INTEGER PRIMARY KEY, knowledge_id INTEGER NOT NULL REFERENCES knowledge(id),
 base_version INTEGER NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
 category TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
 CHECK(status IN ('pending','approved','rejected')),
 proposed_by INTEGER REFERENCES users(id), reviewed_by INTEGER REFERENCES users(id),
 created_at TEXT NOT NULL, reviewed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_knowledge_revision_doc ON knowledge_revisions(knowledge_id,id);
CREATE TABLE IF NOT EXISTS import_jobs (
 id INTEGER PRIMARY KEY, provider TEXT NOT NULL CHECK(provider IN ('website','instagram_media','instagram_insights')),
 state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','processing','completed','failed')),
 requested_by INTEGER REFERENCES users(id), processed INTEGER NOT NULL DEFAULT 0,
 error TEXT, started_at TEXT, finished_at TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_import_jobs ON import_jobs(state,id);
CREATE TABLE IF NOT EXISTS import_documents (
 id INTEGER PRIMARY KEY, job_id INTEGER REFERENCES import_jobs(id),
 provider TEXT NOT NULL, source_url TEXT NOT NULL, title TEXT NOT NULL,
 body TEXT NOT NULL, fingerprint TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
 reviewed_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL, reviewed_at TEXT,
 UNIQUE(source_url,fingerprint)
);
CREATE TABLE IF NOT EXISTS knowledge_sources (
 source_url TEXT PRIMARY KEY, knowledge_id INTEGER NOT NULL REFERENCES knowledge(id),
 reviewed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS instagram_media (
 media_id TEXT PRIMARY KEY, permalink TEXT, caption TEXT,
 media_type TEXT, timestamp TEXT, last_synced_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS instagram_metrics (
 id INTEGER PRIMARY KEY, entity_type TEXT NOT NULL CHECK(entity_type IN ('account','media')),
 entity_id TEXT NOT NULL, name TEXT NOT NULL, period TEXT NOT NULL,
 value REAL, state TEXT NOT NULL CHECK(state IN ('available','unavailable')),
 source TEXT NOT NULL, observed_at TEXT NOT NULL,
 UNIQUE(entity_type,entity_id,name,period,observed_at)
);
CREATE INDEX IF NOT EXISTS idx_insights_entity ON instagram_metrics(entity_type,entity_id,observed_at);
CREATE TABLE IF NOT EXISTS leads (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, project_city TEXT,
 capacity_mw REAL, phone TEXT, foundation TEXT, panel_layout TEXT,
 details TEXT NOT NULL DEFAULT '', stage TEXT NOT NULL DEFAULT 'new'
 CHECK(stage IN ('new','qualifying','qualified','engineering','quotation','won','lost')),
 source_thread_id INTEGER REFERENCES threads(id), created_by INTEGER REFERENCES users(id),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(stage,updated_at);
CREATE TABLE IF NOT EXISTS lead_events (
 id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id),
 old_stage TEXT, new_stage TEXT NOT NULL, actor INTEGER REFERENCES users(id),
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS phone_calls (
 id INTEGER PRIMARY KEY,
 provider TEXT NOT NULL CHECK(provider IN ('twilio')),
 call_sid TEXT NOT NULL UNIQUE,
 stream_token_hash TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','active','ended','failed','human_requested')),
 caller_ciphertext BLOB,
 transcript_ciphertext BLOB,
 consent_to_contact INTEGER NOT NULL DEFAULT 0,
 duration_seconds INTEGER,
 failure_code TEXT,
 started_at TEXT NOT NULL,
 finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_phone_calls_started ON phone_calls(started_at);
CREATE TABLE IF NOT EXISTS phone_lead_proposals (
 id INTEGER PRIMARY KEY,
 call_id INTEGER NOT NULL UNIQUE REFERENCES phone_calls(id),
 details_ciphertext BLOB NOT NULL,
 state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','approved','rejected')),
 approved_by INTEGER REFERENCES users(id),
 lead_id INTEGER REFERENCES leads(id),
 created_at TEXT NOT NULL,
 reviewed_at TEXT
);
CREATE TABLE IF NOT EXISTS integration_secrets (
 name TEXT PRIMARY KEY, ciphertext BLOB NOT NULL,
 updated_by INTEGER REFERENCES users(id), updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS integration_checks (
 provider TEXT PRIMARY KEY CHECK(provider IN ('openai','meta')),
 status TEXT NOT NULL CHECK(status IN ('ok','failed','never')),
 account_label TEXT, checked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS update_requests (
 id INTEGER PRIMARY KEY, target_sha TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('approved','applying','completed','failed')),
 detail TEXT, approved_by INTEGER REFERENCES users(id),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_updates_state ON update_requests(state,id);
CREATE TABLE IF NOT EXISTS auto_policies (
 id INTEGER PRIMARY KEY, keyword TEXT NOT NULL, template TEXT NOT NULL,
 enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
 created_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auto_attempts (
 message_id INTEGER PRIMARY KEY REFERENCES messages(id),
 policy_id INTEGER NOT NULL REFERENCES auto_policies(id),
 state TEXT NOT NULL CHECK(state IN ('reserved','sent','uncertain')),
 reply_id TEXT, attempted_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_auto_attempts ON auto_attempts(state,updated_at);
CREATE TABLE IF NOT EXISTS auto_sent (
 id INTEGER PRIMARY KEY, message_id INTEGER UNIQUE NOT NULL REFERENCES messages(id),
 policy_id INTEGER NOT NULL REFERENCES auto_policies(id),
 external_id TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_auto_sent_date ON auto_sent(created_at);
"""

def ensure_schema(connection:sqlite3.Connection):
    connection.executescript(SQL)
    columns={r[1] for r in connection.execute("PRAGMA table_info(knowledge)").fetchall()}
    if "version" not in columns:
        connection.execute("ALTER TABLE knowledge ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
    if "source_type" not in columns:
        connection.execute("ALTER TABLE knowledge ADD COLUMN source_type TEXT NOT NULL DEFAULT 'manual'")
