"""Encrypted integration credentials at rest; owner only.

A single 32-byte Fernet key is stored ONLY in the host's private .env.
Database backups alone cannot decrypt external API tokens.
"""
import os
from cryptography.fernet import Fernet, InvalidToken
from . import db

NAMES=frozenset({
    "OPENAI_API_KEY","OPENAI_MODEL",
    "META_ACCESS_TOKEN","META_APP_SECRET","META_VERIFY_TOKEN",
    "META_IG_USER_ID","META_GRAPH_VERSION"
})
SECRETS=frozenset({
    "OPENAI_API_KEY","META_ACCESS_TOKEN","META_APP_SECRET","META_VERIFY_TOKEN"
})

def cipher():
    value=os.getenv("VAULT_ENCRYPTION_KEY","")
    if not value:
        raise RuntimeError("VAULT_ENCRYPTION_KEY is missing. Run installer to initialize the vault.")
    try:
        return Fernet(value.encode("ascii"))
    except (ValueError, TypeError):
        raise RuntimeError("Invalid VAULT_ENCRYPTION_KEY. Do not overwrite an existing vault key.")

def read(name):
    if name not in NAMES:
        raise ValueError("Integration setting not allowlisted")
    with db.read() as con:
        try:
            row=con.execute("SELECT ciphertext FROM integration_secrets WHERE name=?",(name,)).fetchone()
        except Exception as error:
            if "no such table" in str(error):
                return None
            raise
    if not row:return None
    try:
        return cipher().decrypt(bytes(row["ciphertext"])).decode("utf8")
    except InvalidToken:
        # Vault corruption is a critical condition, never fallback to stale plaintext.
        raise RuntimeError("Vault decryption failed; restore original VAULT_ENCRYPTION_KEY")

def write_batch(values,actor):
    if not values or not set(values).issubset(NAMES):
        raise ValueError("Invalid integration settings")
    f=cipher()
    encrypted={name:f.encrypt(str(value).encode("utf8")) for name,value in values.items()}
    with db.tx() as con:
        for name,value in encrypted.items():
            con.execute(
                "INSERT INTO integration_secrets(name,ciphertext,updated_by,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET ciphertext=excluded.ciphertext,"
                "updated_by=excluded.updated_by,updated_at=excluded.updated_at",
                (name,value,actor,db.now()))
        db.audit(con,actor,"integration_settings_changed","integration_secrets",
                 ",".join(sorted(values)),{"fields":sorted(values)})
    return sorted(values)

def erase_provider(provider,actor):
    if provider=="openai":
        names=["OPENAI_API_KEY","OPENAI_MODEL"]
    elif provider=="meta":
        names=["META_ACCESS_TOKEN","META_APP_SECRET","META_VERIFY_TOKEN","META_IG_USER_ID","META_GRAPH_VERSION"]
    else:
        raise ValueError("Unknown provider")
    # Empty values explicitly mask any inherited legacy environment variables.
    return write_batch({name:"" for name in names},actor)
