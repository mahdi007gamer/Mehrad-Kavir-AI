"""Governed operations API: document revisions, imports, analytics, CRM, updates."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import db, settings
from .security import role_required, user_for

router = APIRouter()
OWNER = role_required("owner")
EDITOR = role_required("owner","editor")

class DocumentRevision(BaseModel):
    base_version: int = Field(ge=1)
    title: str = Field(min_length=4,max_length=150)
    body: str = Field(min_length=20,max_length=10000)
    category: Literal["brand","engineering","sales","faq","policy","content","other"] = "other"

class ReviewAction(BaseModel):
    decision: Literal["approved","rejected"]

@router.get("/api/knowledge/{id}/history")
def knowledge_history(id:int,user=Depends(user_for)):
    with db.read() as con:
        doc=con.execute("SELECT id,title,body,category,status,version FROM knowledge WHERE id=?",(id,)).fetchone()
        if not doc:raise HTTPException(404,"Document not found")
        revisions=[dict(x) for x in con.execute(
            "SELECT id,base_version,title,body,category,status,created_at,reviewed_at FROM knowledge_revisions "
            "WHERE knowledge_id=? ORDER BY id DESC LIMIT 100",(id,)).fetchall()]
    return {"current":dict(doc),"revisions":revisions}

@router.post("/api/knowledge/{id}/revisions")
def propose_revision(id:int,data:DocumentRevision,user=Depends(EDITOR)):
    with db.tx() as con:
        doc=con.execute("SELECT version,status FROM knowledge WHERE id=?",(id,)).fetchone()
        if not doc:raise HTTPException(404,"Document not found")
        if doc["status"]!="approved":raise HTTPException(409,"Only approved documents can be revised")
        if doc["version"]!=data.base_version:raise HTTPException(409,"Stale version: reload document")
        cur=con.execute("INSERT INTO knowledge_revisions(knowledge_id,base_version,title,body,category,proposed_by,created_at) "
            "VALUES(?,?,?,?,?,?,?)",(id,data.base_version,data.title.strip(),data.body.strip(),data.category,user["id"],db.now()))
        db.audit(con,user["id"],"knowledge_revision_proposed","knowledge_revisions",cur.lastrowid,
                 {"document_id":id,"base_version":data.base_version})
        return {"revision_id":cur.lastrowid,"status":"pending"}

@router.post("/api/knowledge/revisions/{id}/review")
def review_revision(id:int,data:ReviewAction,user=Depends(OWNER)):
    with db.tx() as con:
        rev=con.execute("SELECT * FROM knowledge_revisions WHERE id=? AND status='pending'",(id,)).fetchone()
        if not rev:raise HTTPException(409,"Revision already reviewed or missing")
        doc=con.execute("SELECT version FROM knowledge WHERE id=?",(rev["knowledge_id"],)).fetchone()
        if not doc or doc["version"]!=rev["base_version"]:
            raise HTTPException(409,"Revision conflict; current knowledge has changed")
        con.execute("UPDATE knowledge_revisions SET status=?,reviewed_by=?,reviewed_at=? WHERE id=?",
                    (data.decision,user["id"],db.now(),id))
        if data.decision=="approved":
            con.execute("UPDATE knowledge SET title=?,body=?,category=?,version=version+1,source_type='manual',"
                        "reviewed_by=?,reviewed_at=? WHERE id=?",
                        (rev["title"],rev["body"],rev["category"],user["id"],db.now(),rev["knowledge_id"]))
        db.audit(con,user["id"],"revision_"+data.decision,"knowledge",rev["knowledge_id"],{"revision":id})
        return {"revision_id":id,"status":data.decision}

class ImportRequest(BaseModel):
    provider: Literal["website","instagram_media","instagram_insights"]

@router.post("/api/import/jobs")
def queue_import(data:ImportRequest,user=Depends(OWNER)):
    if data.provider.startswith("instagram") and not (settings.META_ACCESS_TOKEN and settings.META_IG_USER_ID):
        raise HTTPException(409,"Meta account and token not connected")
    with db.tx() as con:
        pending=con.execute("SELECT id FROM import_jobs WHERE provider=? AND state IN ('queued','processing')",
                            (data.provider,)).fetchone()
        if pending:raise HTTPException(409,"A job for this source is already running or queued")
        cur=con.execute("INSERT INTO import_jobs(provider,requested_by,created_at) VALUES(?,?,?)",
                        (data.provider,user["id"],db.now()))
        db.audit(con,user["id"],"import_queued","import_jobs",cur.lastrowid,{"source":data.provider})
    return {"id":cur.lastrowid,"state":"queued"}

@router.get("/api/import/jobs")
def import_jobs(user=Depends(EDITOR)):
    with db.read() as con:
        return [dict(x) for x in con.execute(
            "SELECT id,provider,state,processed,error,created_at,finished_at FROM import_jobs ORDER BY id DESC LIMIT 70")]

@router.get("/api/import/documents")
def staged_documents(user=Depends(EDITOR)):
    with db.read() as con:
        return [dict(x) for x in con.execute(
            "SELECT id,provider,source_url,title,body,status,created_at FROM import_documents ORDER BY id DESC LIMIT 150")]

@router.post("/api/import/documents/{id}/review")
def approve_staged(id:int,data:ReviewAction,user=Depends(OWNER)):
    with db.tx() as con:
        source=con.execute("SELECT * FROM import_documents WHERE id=? AND status='pending'",(id,)).fetchone()
        if not source:raise HTTPException(409,"Staged document missing or already reviewed")
        knowledge_id=None
        if data.decision=="approved":
            old=con.execute("SELECT knowledge_id FROM knowledge_sources WHERE source_url=?",
                            (source["source_url"],)).fetchone()
            if old:
                knowledge_id=old["knowledge_id"]
                current=con.execute("SELECT title,body,category,version,status FROM knowledge WHERE id=?",
                                    (knowledge_id,)).fetchone()
                if not current or current["status"]!="approved":
                    raise HTTPException(409,"Existing source needs manual review")
                con.execute(
                    "INSERT INTO knowledge_revisions(knowledge_id,base_version,title,body,category,status,reviewed_by,created_at,reviewed_at) "
                    "VALUES(?,?,?,?,?,'approved',?,?,?)",
                    (knowledge_id,current["version"],source["title"],source["body"],"content" if source["provider"]=="instagram" else "other",
                     user["id"],db.now(),db.now()))
                con.execute("UPDATE knowledge SET title=?,body=?,category=?,version=version+1,source_type=?,reviewed_by=?,reviewed_at=? WHERE id=?",
                            (source["title"],source["body"],"content" if source["provider"]=="instagram" else "other",
                             source["provider"],user["id"],db.now(),knowledge_id))
            else:
                cur=con.execute("INSERT INTO knowledge(title,body,category,status,version,source_type,created_by,reviewed_by,created_at,reviewed_at) "
                                "VALUES(?,?,?,'approved',1,?,?,?, ?,?)",
                                (source["title"],source["body"],"content" if source["provider"]=="instagram" else "other",
                                 source["provider"],user["id"],user["id"],db.now(),db.now()))
                knowledge_id=cur.lastrowid
            con.execute("INSERT INTO knowledge_sources(source_url,knowledge_id,reviewed_at) VALUES(?,?,?) "
                        "ON CONFLICT(source_url) DO UPDATE SET knowledge_id=excluded.knowledge_id,reviewed_at=excluded.reviewed_at",
                        (source["source_url"],knowledge_id,db.now()))
        con.execute("UPDATE import_documents SET status=?,reviewed_by=?,reviewed_at=? WHERE id=?",
                    (data.decision,user["id"],db.now(),id))
        db.audit(con,user["id"],"source_"+data.decision,"import_documents",id,
                 {"provider":source["provider"],"knowledge_id":knowledge_id})
    return {"id":id,"status":data.decision,"knowledge_id":knowledge_id}

@router.get("/api/analytics")
def analytics(user=Depends(EDITOR)):
    with db.read() as con:
        media=[dict(x) for x in con.execute(
            "SELECT media_id,permalink,caption,media_type,timestamp,last_synced_at "
            "FROM instagram_media ORDER BY timestamp DESC LIMIT 50")]
        latest=[dict(x) for x in con.execute(
            "SELECT m.entity_type,m.entity_id,m.name,m.period,m.value,m.state,m.source,m.observed_at "
            "FROM instagram_metrics m WHERE m.id IN "
            "(SELECT MAX(id) FROM instagram_metrics GROUP BY entity_type,entity_id,name,period) "
            "ORDER BY m.observed_at DESC LIMIT 200")]
        leads={r["stage"]:r["count"] for r in con.execute(
            "SELECT stage,COUNT(*) AS count FROM leads GROUP BY stage")}
        jobs=[dict(x) for x in con.execute("SELECT provider,state,finished_at FROM import_jobs ORDER BY id DESC LIMIT 6")]
    return {"media":media,"latest_metrics":latest,"leads_by_stage":leads,"recent_jobs":jobs,
            "disclaimer":"Only observed values from an authorized Meta API are returned; unavailable is not zero."}

STAGES={"new","qualifying","qualified","engineering","quotation","won","lost"}
class LeadIn(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    project_city:str|None=Field(default=None,max_length=120)
    capacity_mw:float|None=Field(default=None,ge=0,le=100000)
    phone:str|None=Field(default=None,max_length=60)
    foundation:str|None=Field(default=None,max_length=100)
    panel_layout:str|None=Field(default=None,max_length=150)
    details:str=Field(default="",max_length=2500)
    source_thread_id:int|None=None

@router.get("/api/leads")
def leads(user=Depends(EDITOR)):
    with db.read() as con:
        return [dict(x) for x in con.execute(
            "SELECT * FROM leads ORDER BY updated_at DESC LIMIT 200")]

@router.post("/api/leads")
def new_lead(data:LeadIn,user=Depends(EDITOR)):
    with db.tx() as con:
        if data.source_thread_id and not con.execute("SELECT 1 FROM threads WHERE id=?",(data.source_thread_id,)).fetchone():
            raise HTTPException(404,"Linked thread not found")
        cur=con.execute(
            "INSERT INTO leads(name,project_city,capacity_mw,phone,foundation,panel_layout,details,source_thread_id,created_by,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (data.name,data.project_city,data.capacity_mw,data.phone,data.foundation,data.panel_layout,
             data.details,data.source_thread_id,user["id"],db.now(),db.now()))
        con.execute("INSERT INTO lead_events(lead_id,new_stage,actor,created_at) VALUES(?,'new',?,?)",
                    (cur.lastrowid,user["id"],db.now()))
        db.audit(con,user["id"],"lead_created","leads",cur.lastrowid)
        return {"id":cur.lastrowid,"stage":"new"}

class LeadStageIn(BaseModel):
    stage:Literal["new","qualifying","qualified","engineering","quotation","won","lost"]

@router.post("/api/leads/{id}/stage")
def update_lead_stage(id:int,data:LeadStageIn,user=Depends(EDITOR)):
    with db.tx() as con:
        lead=con.execute("SELECT stage FROM leads WHERE id=?",(id,)).fetchone()
        if not lead:raise HTTPException(404,"Lead not found")
        if lead["stage"]==data.stage:return {"id":id,"stage":data.stage}
        con.execute("UPDATE leads SET stage=?,updated_at=? WHERE id=?",(data.stage,db.now(),id))
        con.execute("INSERT INTO lead_events(lead_id,old_stage,new_stage,actor,created_at) VALUES(?,?,?,?,?)",
                    (id,lead["stage"],data.stage,user["id"],db.now()))
        db.audit(con,user["id"],"lead_stage_changed","leads",id,{"from":lead["stage"],"to":data.stage})
    return {"id":id,"stage":data.stage}

class AutoPolicyIn(BaseModel):
    keyword: Literal["سلام","درود","وقت بخیر","صبح بخیر","شب بخیر"]
    template: str = Field(min_length=15,max_length=320)

@router.get("/api/automation/policies")
def get_auto_policies(user=Depends(EDITOR)):
    with db.read() as con:
        return [dict(x) for x in con.execute(
            "SELECT id,keyword,template,enabled,created_at FROM auto_policies ORDER BY id DESC LIMIT 80")]
@router.post("/api/automation/policies")
def create_auto_policy(data:AutoPolicyIn,user=Depends(OWNER)):
    # Greeting-only, no URLs or arbitrary generated instructions.
    if re.search(r"https?://|www\.|@\w+|[\{\}]",data.template,re.I):
        raise HTTPException(422,"Templates may not contain links, handles or variables")
    with db.tx() as con:
        cur=con.execute("INSERT INTO auto_policies(keyword,template,created_by,created_at) VALUES(?,?,?,?)",
                        (data.keyword,data.template,user["id"],db.now()))
        db.audit(con,user["id"],"autopolicy_created","auto_policies",cur.lastrowid)
        return {"id":cur.lastrowid,"enabled":False}

class ToggleIn(BaseModel):
    enabled:bool
@router.post("/api/automation/policies/{id}/toggle")
def toggle_auto_policy(id:int,data:ToggleIn,user=Depends(OWNER)):
    if data.enabled and not settings.AUTO_REPLY_ENABLED:
        raise HTTPException(409,"AUTO_REPLY_ENABLED must be explicitly enabled on server")
    with db.tx() as con:
        cur=con.execute("UPDATE auto_policies SET enabled=? WHERE id=?",(int(data.enabled),id))
        if not cur.rowcount:raise HTTPException(404,"Policy not found")
        db.audit(con,user["id"],"autopolicy_toggled","auto_policies",id,{"enabled":data.enabled})
    return {"id":id,"enabled":data.enabled}

@router.get("/api/automation/status")
def auto_status(user=Depends(EDITOR)):
    return {"server_enabled":settings.AUTO_REPLY_ENABLED,"meta_ready":settings.meta_ready(),
            "scope":"Exact greeting only. No free-form AI-generated outgoing messages."}
