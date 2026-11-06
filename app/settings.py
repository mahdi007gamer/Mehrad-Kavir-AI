"""Configuration with fail-closed defaults; never commit .env."""
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DB_PATH", str(BASE / "data" / "mehrad.sqlite3"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-3.8-live")
GEMINI_TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
GEMINI_VOICE = os.getenv("GEMINI_VOICE", "Kore")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
PHONE_PUBLIC_BASE_URL = os.getenv("PHONE_PUBLIC_BASE_URL", "")
PHONE_RECEPTION_ENABLED = os.getenv("PHONE_RECEPTION_ENABLED", "false")
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
    return all(effective(n) for n in ('META_ACCESS_TOKEN','META_APP_SECRET','META_VERIFY_TOKEN','META_IG_USER_ID'))

def ai_ready():
    return bool(effective('GEMINI_API_KEY') if effective('AI_PROVIDER')=='gemini' else effective('OPENAI_API_KEY'))

def check_startup():
    if not BOOTSTRAP_ADMIN_PASSWORD or len(BOOTSTRAP_ADMIN_PASSWORD) < 16:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must be at least 16 characters")
    if APP_ENV == "production" and not COOKIE_SECURE:
        raise RuntimeError("COOKIE_SECURE=true required in production (HTTPS)")

# v0.2: only verified, explicitly enabled templates can trigger unattended sends.
AUTO_REPLY_ENABLED = os.getenv("AUTO_REPLY_ENABLED","false").lower()=="true"
APP_REVISION = os.getenv("APP_REVISION","unknown")
UPDATE_CHANNEL = "https://api.github.com/repos/mahdi007gamer/Mehrad-Kavir-AI/commits/main"


def effective(name):
    """Current credential or setting (encrypted vault overrides initial .env).

    Vault errors fail closed. Never expose returned values through HTTP.
    """
    from .vault import read
    saved=read(name)
    if saved is not None:
        return saved
    return getattr(__import__(__name__, fromlist=[name]),name)
