"""Password security, session rotation, CSRF and API access control."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request
from . import db

COOKIE_NAME = "mkai_session"

def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + salt.hex() + "$" + digest.hex()

def verify_password(password, encoded):
    try:
        method, salt, digest = encoded.split("$")
        if method != "scrypt":
            return False
        check = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1)
        return hmac.compare_digest(check, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def create_session(user_id):
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    with db.tx() as con:
        con.execute("INSERT INTO sessions(id_hash,user_id,csrf,expires_at) VALUES(?,?,?,?)",
                    (token_hash(token), user_id, csrf, expires))
        con.execute("DELETE FROM sessions WHERE expires_at < ?", (db.now(),))
    return token, csrf

def user_for(request: Request):
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        raise HTTPException(401, "Authentication required")
    with db.read() as con:
        row = con.execute(
            "SELECT u.id,u.email,u.role,s.csrf,s.expires_at FROM sessions s "
            "JOIN users u ON u.id=s.user_id WHERE s.id_hash=?",
            (token_hash(raw),)
        ).fetchone()
    if not row or row["expires_at"] < db.now():
        raise HTTPException(401, "Session expired")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        candidate = request.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(candidate, row["csrf"]):
            raise HTTPException(403, "CSRF verification failed")
    return dict(row)

def role_required(*allowed):
    def dependency(user=Depends(user_for)):
        if user["role"] not in allowed:
            raise HTTPException(403, "Insufficient permissions")
        return user
    return dependency

def verify_webhook(body: bytes, header: str, app_secret: str):
    if not app_secret or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[7:], expected)
