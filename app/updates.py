"""Owner-approved updates: network checks in app, privileged execution ONLY on Windows host.

This module never executes shell commands or exposes Docker socket to the web app.
"""
import re
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import db, settings
from .security import role_required

router=APIRouter()
OWNER=role_required("owner")

_cache={"at":0.0,"payload":None}
SHA=re.compile(r"^[a-f0-9]{40}$")

def remote_head(force=False):
    if not force and _cache["payload"] and time.monotonic()-_cache["at"]<180:
        return _cache["payload"]
    try:
        with httpx.Client(timeout=12,trust_env=False,follow_redirects=False) as client:
            resp=client.get(settings.UPDATE_CHANNEL,headers={
                "Accept":"application/vnd.github+json",
                "User-Agent":"MehradKavirAI-UpdateChecker/0.2",
                "X-GitHub-Api-Version":"2022-11-28"})
        resp.raise_for_status()
        data=resp.json()
        sha=data.get("sha","")
        if not SHA.fullmatch(sha):raise ValueError("Invalid GitHub commit hash")
        payload={"sha":sha,"date":data.get("commit",{}).get("committer",{}).get("date"),
                 "message":str(data.get("commit",{}).get("message","")).split("\n")[0][:180],
                 "url":f"https://github.com/mahdi007gamer/Mehrad-Kavir-AI/commit/{sha}"}
        _cache.update({"at":time.monotonic(),"payload":payload})
        return payload
    except Exception:
        if _cache["payload"]:
            return dict(_cache["payload"],stale=True)
        raise HTTPException(503,"Could not check official GitHub update channel")

@router.get("/api/updates/status")
def status(user=Depends(OWNER)):
    head=remote_head()
    with db.read() as con:
        last=con.execute("SELECT id,target_sha,state,detail,created_at,updated_at FROM update_requests "
                         "ORDER BY id DESC LIMIT 1").fetchone()
    installed=settings.APP_REVISION.lower()
    return {"installed_sha":installed,"latest_sha":head["sha"],"available":bool(installed!="unknown" and head["sha"]!=installed),
            "installed_known":bool(installed!="unknown"),"head":head,
            "request":dict(last) if last else None,"safe_mode":True,
            "note":"Updates are executed on the local host by the separately running, allowlisted update agent."}

@router.post("/api/updates/check")
def check(user=Depends(OWNER)):
    remote_head(force=True)
    return status(user)

class UpdateApproval(BaseModel):
    sha:str=Field(min_length=40,max_length=40)

@router.post("/api/updates/approve")
def approve(data:UpdateApproval,user=Depends(OWNER)):
    if not SHA.fullmatch(data.sha):
        raise HTTPException(422,"Invalid commit hash")
    head=remote_head(force=True)
    if head.get("stale"):
        raise HTTPException(503,"Cannot approve updates using stale metadata")
    if data.sha!=head["sha"] or data.sha==settings.APP_REVISION:
        raise HTTPException(409,"Update is no longer current or is already installed")
    with db.tx() as con:
        other=con.execute("SELECT id FROM update_requests WHERE state IN ('approved','applying')").fetchone()
        if other:raise HTTPException(409,"Another approved update is pending")
        cur=con.execute("INSERT INTO update_requests(target_sha,state,approved_by,created_at,updated_at) "
                        "VALUES(?,'approved',?,?,?)",(data.sha,user["id"],db.now(),db.now()))
        db.audit(con,user["id"],"update_approved","update_requests",cur.lastrowid,
                 {"sha":data.sha})
        return {"request_id":cur.lastrowid,"state":"approved",
                "note":"The host update runner will verify SHA against the fixed official GitHub origin before deployment."}
