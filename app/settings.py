"""Configuration with fail-closed defaults; never commit .env."""
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DB_PATH", str(BASE / "data" / "mehrad.sqlite3"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_IG_USER_ID = os.getenv("META_IG_USER_ID", "")
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v25.0")
APP_ENV = os.getenv("APP_ENV", "development")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
BOOTSTRAP_ADMIN_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@localhost")
BOOTSTRAP_ADMIN_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
AI_INPUT_LIMIT = 2800
MAX_KNOWLEDGE_CHARS = 6500

def meta_ready():
    return bool(META_ACCESS_TOKEN and META_APP_SECRET and META_VERIFY_TOKEN and META_IG_USER_ID)

def ai_ready():
    return bool(OPENAI_API_KEY)

def check_startup():
    if not BOOTSTRAP_ADMIN_PASSWORD or len(BOOTSTRAP_ADMIN_PASSWORD) < 16:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must be at least 16 characters")
    if APP_ENV == "production" and not COOKIE_SECURE:
        raise RuntimeError("COOKIE_SECURE=true required in production (HTTPS)")

# v0.2: only verified, explicitly enabled templates can trigger unattended sends.
AUTO_REPLY_ENABLED = os.getenv("AUTO_REPLY_ENABLED","false").lower()=="true"
APP_REVISION = os.getenv("APP_REVISION","unknown")
UPDATE_CHANNEL = "https://api.github.com/repos/mahdi007gamer/Mehrad-Kavir-AI/commits/main"
