"""Exact-greeting-only outbound automation with hard opt-in and safe failure.

No model-generated answer can ever reach this sender. Unknown provider outcomes
are never retried automatically.
"""
from datetime import datetime, timezone, timedelta
from . import db, settings
from .meta import send_reply

GREETINGS={"سلام","درود","وقت بخیر","صبح بخیر","شب بخیر"}
MAX_PER_DAY=20

def _eligible(message_id):
    if not settings.AUTO_REPLY_ENABLED or not settings.meta_ready():
        return None
    with db.read() as con:
        verified=con.execute(
            "SELECT 1 FROM integration_checks WHERE provider='meta' AND status='ok'"
        ).fetchone()
        if not verified:
            return None
        msg=con.execute(
            "SELECT m.id,m.body,m.received_at,m.status,m.thread_id,t.kind,t.platform,t.remote_user_id "
            "FROM messages m JOIN threads t ON t.id=m.thread_id WHERE m.id=?",(message_id,)
        ).fetchone()
        if not msg or msg["platform"]!="instagram" or msg["kind"]!="dm":
            return None
        cleaned=" ".join(msg["body"].strip().split())
        if cleaned not in GREETINGS:
            return None
        try:
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(msg["received_at"]).astimezone(timezone.utc)).total_seconds()
            if age<0 or age>23*3600:return None
        except (TypeError,ValueError):
            return None
        policy=con.execute(
            "SELECT id,template FROM auto_policies WHERE keyword=? AND enabled=1 ORDER BY id DESC LIMIT 1",
            (cleaned,)
        ).fetchone()
        if not policy:return None
        return dict(msg),dict(policy)

def try_greeting(message_id):
    eligible=_eligible(message_id)
    if not eligible:return "not_applicable"
    msg,policy=eligible
    cutoff=(datetime.now(timezone.utc)-timedelta(days=30)).isoformat(timespec="seconds")
    daily=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat(timespec="seconds")
    with db.tx() as con:
        if con.execute("SELECT 1 FROM auto_attempts WHERE message_id=?",(message_id,)).fetchone():
            return "already_attempted"
        total=con.execute("SELECT COUNT(*) FROM auto_attempts WHERE attempted_at>=?",(daily,)).fetchone()[0]
        if total>=MAX_PER_DAY:
            return "not_applicable"
        repeated=con.execute(
            "SELECT 1 FROM auto_attempts a JOIN messages m ON m.id=a.message_id "
            "JOIN threads t ON t.id=m.thread_id WHERE t.platform='instagram' AND t.remote_user_id=? "
            "AND a.attempted_at>=? LIMIT 1",
            (msg["remote_user_id"],cutoff)).fetchone()
        if repeated:return "not_applicable"
        con.execute(
            "INSERT INTO auto_attempts(message_id,policy_id,state,attempted_at,updated_at)"
            " VALUES(?,?,'reserved',?,?)",
            (message_id,policy["id"],db.now(),db.now()))
        db.audit(con,"worker","auto_reply_reserved","messages",message_id,{"policy":policy["id"]})
    try:
        result=send_reply(kind="dm",recipient=msg["remote_user_id"],body=policy["template"],reply_to=None)
        with db.tx() as con:
            con.execute("UPDATE auto_attempts SET state='sent',reply_id=?,updated_at=? WHERE message_id=?",
                        (result,db.now(),message_id))
            con.execute(
                "INSERT OR IGNORE INTO messages(thread_id,external_id,direction,body,remote_object_id,status,received_at) "
                "VALUES(?,?,'out',?,?,'sent',?)",
                (msg["thread_id"],"auto:"+result,policy["template"],result,db.now()))
            con.execute("UPDATE messages SET status='processed',processed_at=? WHERE id=?",(db.now(),message_id))
            db.audit(con,"worker","auto_reply_sent","messages",message_id,{"policy":policy["id"]})
        return "sent"
    except Exception:
        # Network error might mean Meta accepted the message. Never retry automatically.
        with db.tx() as con:
            con.execute("UPDATE auto_attempts SET state='uncertain',updated_at=? WHERE message_id=?",
                        (db.now(),message_id))
            con.execute("UPDATE messages SET status='failed',processed_at=? WHERE id=?",(db.now(),message_id))
            db.audit(con,"worker","auto_reply_uncertain","messages",message_id,{"policy":policy["id"]})
        return "uncertain"
