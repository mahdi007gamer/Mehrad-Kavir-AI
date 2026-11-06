"""Private container CLI for allowlisted local host update runner.

Not an HTTP endpoint. Host PowerShell may invoke ONLY this exact module through
docker compose exec; web application has no Docker daemon or shell access.
"""
import json
import sys
from pathlib import Path
from . import db

def peek():
    with db.read() as con:
        row=con.execute(
            "SELECT id,target_sha FROM update_requests WHERE state='approved' ORDER BY id ASC LIMIT 1"
        ).fetchone()
    return dict(row) if row else {}

def claim(id,sha):
    with db.tx() as con:
        cur=con.execute(
            "UPDATE update_requests SET state='applying',updated_at=? "
            "WHERE id=? AND target_sha=? AND state='approved'",
            (db.now(),id,sha))
        if cur.rowcount==1:
            db.audit(con,"host-updater","update_claimed","update_requests",id,{"sha":sha})
        return cur.rowcount==1

def complete(id,sha,state,detail=""):
    if state not in ("completed","failed"):
        return False
    with db.tx() as con:
        cur=con.execute(
            "UPDATE update_requests SET state=?,detail=?,updated_at=? "
            "WHERE id=? AND target_sha=? AND state='applying'",
            (state,detail[:300],db.now(),id,sha))
        if cur.rowcount==1:db.audit(con,"host-updater","update_"+state,"update_requests",id,{"sha":sha})
        return cur.rowcount==1

def backup():
    folder=Path(db.settings.DB_PATH).parent/"backups"
    folder.mkdir(parents=True,exist_ok=True)
    output=folder/("before-update-"+db.now().replace(":","-").replace("+","_")+".sqlite3")
    with db.read() as source:
        import sqlite3
        target=sqlite3.connect(str(output))
        try:source.backup(target)
        finally:target.close()
    return str(output)

def main():
    args=sys.argv[1:]
    if args==["peek"]:
        print(json.dumps(peek()))
        return
    if args and args[0]=="claim" and len(args)==3 and args[1].isdigit():
        print(json.dumps({"ok":claim(int(args[1]),args[2])}))
        return
    if args and args[0]=="finish" and len(args)>=4 and args[1].isdigit():
        print(json.dumps({"ok":complete(int(args[1]),args[2],args[3]," ".join(args[4:]))}))
        return
    if args==["backup"]:
        print(json.dumps({"path":backup()}))
        return
    print(json.dumps({"error":"Unsupported command"}))
    sys.exit(2)

if __name__=="__main__":
    main()
