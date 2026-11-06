"""SQLite repository, migrations and immutable audit journal.

SQLite is suitable for the single-instance MVP. For horizontal scaling,
migrate to PostgreSQL and a dedicated durable queue.
"""
import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from . import settings

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def connect():
    Path(settings.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.DB_PATH, timeout=20, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=20000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

@contextmanager
def tx():
    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    finally:
        db.close()

@contextmanager
def read():
    db = connect()
    try:
        yield db
    finally:
        db.close()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('owner','editor','viewer')), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
 id_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 csrf TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
 category TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
 CHECK(status IN ('pending','approved','rejected')),
 created_by INTEGER REFERENCES users(id), reviewed_by INTEGER REFERENCES users(id),
 created_at TEXT NOT NULL, reviewed_at TEXT
);
CREATE TABLE IF NOT EXISTS rules (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, instruction TEXT NOT NULL,
 scope TEXT NOT NULL CHECK(scope IN ('global','sales','engineering','support','content')),
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
 version INTEGER NOT NULL DEFAULT 1, created_by INTEGER REFERENCES users(id),
 reviewed_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL, reviewed_at TEXT
);
CREATE TABLE IF NOT EXISTS threads (
 id INTEGER PRIMARY KEY, platform TEXT NOT NULL CHECK(platform IN ('demo','instagram')),
 kind TEXT NOT NULL CHECK(kind IN ('dm','comment')),
 remote_user_id TEXT NOT NULL, label TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
 last_received_at TEXT NOT NULL,
 UNIQUE(platform,kind,remote_user_id)
);
CREATE TABLE IF NOT EXISTS messages (
 id INTEGER PRIMARY KEY, thread_id INTEGER NOT NULL REFERENCES threads(id),
 external_id TEXT UNIQUE, direction TEXT NOT NULL CHECK(direction IN ('in','out')),
 body TEXT NOT NULL, remote_object_id TEXT, status TEXT NOT NULL DEFAULT 'new',
 received_at TEXT NOT NULL, processed_at TEXT, attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS drafts (
 id INTEGER PRIMARY KEY, message_id INTEGER UNIQUE NOT NULL REFERENCES messages(id),
 text TEXT NOT NULL, specialty TEXT NOT NULL, risk TEXT NOT NULL,
 citations TEXT NOT NULL DEFAULT '[]', state TEXT NOT NULL DEFAULT 'pending'
 CHECK(state IN ('pending','approved','rejected','sending','sent','failed')),
 generated_by TEXT NOT NULL, decided_by INTEGER REFERENCES users(id),
 decided_at TEXT, error TEXT, external_reply_id TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scenarios (
 id INTEGER PRIMARY KEY, topic TEXT NOT NULL, audience TEXT NOT NULL,
 style TEXT NOT NULL, body TEXT NOT NULL, generated_by TEXT NOT NULL,
 author_id INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
 event_key TEXT PRIMARY KEY, received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL,
 entity TEXT NOT NULL, entity_id TEXT NOT NULL, metadata TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_messages_queue ON messages(status, direction, attempts);
CREATE INDEX IF NOT EXISTS ix_threads_date ON threads(last_received_at);
CREATE INDEX IF NOT EXISTS ix_audit_date ON audit(created_at);
"""

def audit(db, actor, action, entity, entity_id, metadata=None):
    # Never write access tokens or entire private conversations to audit.
    db.execute(
        "INSERT INTO audit(actor,action,entity,entity_id,metadata,created_at) VALUES(?,?,?,?,?,?)",
        (str(actor), action, entity, str(entity_id), json.dumps(metadata or {}, ensure_ascii=False), now())
    )

def init_db():
    from .security import hash_password
    settings.check_startup()
    schema_db = connect()
    try:
        schema_db.executescript(SCHEMA)
        from .extensions import ensure_schema
        ensure_schema(schema_db)
    finally:
        schema_db.close()
    with tx() as db:
        count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if not count:
            db.execute("INSERT INTO users(email,password_hash,role,created_at) VALUES(?,?,?,?)",
                       (settings.BOOTSTRAP_ADMIN_EMAIL.lower(), hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD), "owner", now()))
            audit(db, "system", "bootstrap", "users", "1")
        seed = db.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
        if not seed:
            docs = [
                ("هویت عمومی مهراد کویر",
                 "نام برند: مهراد کویر. نام مجموعه: یکتا فولاد مهراد کویر. حوزه فعالیت: طراحی و تولید سازه‌های فولادی نیروگاه‌های خورشیدی. رنگ اصلی هویت بصری: #006FFE. وب‌سایت: mehradkavir.com. اطلاعات فنی، ظرفیت تولید، قیمت‌ها و سوابق پروژه فقط از مدارک تأییدشده بیان شوند.",
                 "brand"),
                ("خط‌مشی ارتباطات",
                 "لحن: رسمی، محترمانه، روان و حرفه‌ای. برای محاسبه سازه و اعلام قیمت، محل پروژه، مشخصات پنل، شرایط خاک، باد، نوع فونداسیون و اطلاعات طراحی لازم است. قیمت، ظرفیت، زمان تحویل، تأییدیه فنی یا ضمانت را بدون سند قطعی اعلام نکن.",
                 "policy")
            ]
            for title, body, category in docs:
                db.execute(
                    "INSERT INTO knowledge(title,body,category,status,created_at) VALUES(?,?,?,'approved',?)",
                    (title, body, category, now())
                )
        # Curated pack inserts only NEW documents; never touches owner edits.
        from .brand_knowledge import apply_pack
        apply_pack(db)
