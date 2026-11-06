"""Recoverable durable worker; handles crash recovery and retries.

No Meta auto-sending is performed by the AI worker. All sends pass through
an authenticated approval endpoint after permission and window checks.
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from . import db
from .brain import create_reply

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mkai-worker")

def run_once():
    cutoff=(datetime.now(timezone.utc)-timedelta(minutes=3)).isoformat(timespec="seconds")
    with db.tx() as con:
        con.execute("UPDATE messages SET status='new' WHERE status='processing' AND processed_at < ? AND attempts < 3",(cutoff,))
        row=con.execute(
            "SELECT id,body FROM messages WHERE direction='in' AND status='new' AND attempts < 3 ORDER BY id LIMIT 1"
        ).fetchone()
        if not row: return False
        message_id=int(row["id"])
        con.execute("UPDATE messages SET status='processing',processed_at=?,attempts=attempts+1 WHERE id=?",(db.now(),message_id))
    try:
        decision=create_reply(row["body"])
        with db.tx() as con:
            con.execute(
                "INSERT OR IGNORE INTO drafts(message_id,text,specialty,risk,citations,generated_by,created_at) VALUES(?,?,?,?,?,?,?)",
                (message_id,decision.text,decision.specialty,decision.risk,json.dumps(decision.citations),decision.generated_by,db.now()))
            con.execute("UPDATE messages SET status='processed',processed_at=? WHERE id=?",(db.now(),message_id))
            db.audit(con,"worker","draft_created","messages",message_id,{"role":decision.specialty,"risk":decision.risk})
    except Exception:
        log.exception("Draft processing failed for id=%s",message_id)
        with db.tx() as con:
            con.execute("UPDATE messages SET status=CASE WHEN attempts>=3 THEN 'failed' ELSE 'new' END WHERE id=?",(message_id,))
    return True

def main():
    db.init_db()
    log.info("Worker started")
    while True:
        try:
            if not run_once():
                time.sleep(2)
        except Exception:
            log.exception("Worker loop error")
            time.sleep(5)

if __name__=="__main__":
    main()
