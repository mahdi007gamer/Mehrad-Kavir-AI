"""Mehrad Kavir AI: authenticated admin API and verified Instagram webhook."""
import hmac
import json
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import db, settings
from .security import COOKIE_NAME, create_session, token_hash, user_for, role_required, verify_password, verify_webhook, hash_password
from .brain import create_scenario, create_reply
from .meta import send_reply

log = logging.getLogger("mkai")
STATIC = Path(__file__).parent / "static"
@asynccontextmanager
async def lifespan(_app):
    db.init_db()
    yield

app = FastAPI(title="Mehrad Kavir AI", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
EDITOR = role_required("owner","editor")
OWNER = role_required("owner")

@app.middleware("http")
async def security_headers(request: Request, call_next):
    if request.url.path.startswith("/api/") and int(request.headers.get("content-length","0") or "0") > 80_000:
        return Response("Request too large",status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    if settings.COOKIE_SECURE:
        response.headers["Strict-Transport-Security"]="max-age=31536000; includeSubDomains"
    response.headers["Cache-Control"]="no-store" if request.url.path.startswith("/api/") else "private, max-age=0"
    return response

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")

@app.get("/health")
def health():
    return {"status":"ok","service":"Mehrad Kavir AI"}

class Login(BaseModel):
    email: str = Field(min_length=3,max_length=150)
    password: str = Field(min_length=1,max_length=200)

@app.post("/api/auth/login")
def login(form:Login, request:Request, response:Response):
    ip = (request.client.host if request.client else "unknown")[:100]
    cutoff = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp()-900,timezone.utc).isoformat(timespec="seconds")
    with db.read() as con:
        fails = con.execute("SELECT COUNT(*) FROM audit WHERE actor=? AND action='login_failed' AND created_at>=?",
            ("login:"+ip,cutoff)).fetchone()[0]
    if fails >= 8:
        raise HTTPException(429,"Too many attempts; retry later")
    with db.read() as con:
        row=con.execute("SELECT id,email,password_hash,role FROM users WHERE email=?",(form.email.strip().lower(),)).fetchone()
    valid = bool(row and verify_password(form.password,row["password_hash"]))
    if not valid:
        with db.tx() as con:
            db.audit(con,"login:"+ip,"login_failed","auth","unknown")
        raise HTTPException(401,"Invalid credentials")
    token, csrf=create_session(row["id"])
    response.set_cookie(COOKIE_NAME,token,httponly=True,secure=settings.COOKIE_SECURE,
        samesite="strict",path="/",max_age=432000)
    with db.tx() as con:
        db.audit(con,row["id"],"login","users",row["id"])
    return {"user":{"id":row["id"],"email":row["email"],"role":row["role"]},"csrf":csrf}

@app.get("/api/me")
def me(user=Depends(user_for)):
    return {"user":{"id":user["id"],"email":user["email"],"role":user["role"]},"csrf":user["csrf"]}

@app.post("/api/auth/logout")
def logout(request:Request,response:Response,user=Depends(user_for)):
    with db.tx() as con:
        con.execute("DELETE FROM sessions WHERE id_hash=?",(token_hash(request.cookies.get(COOKIE_NAME,"")),))
        db.audit(con,user["id"],"logout","users",user["id"])
    response.delete_cookie(COOKIE_NAME,path="/")
    return {"ok":True}

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1,max_length=200)
    new_password: str = Field(min_length=16,max_length=200)

@app.post("/api/account/password")
def change_password(data:PasswordChange, response:Response,user=Depends(user_for)):
    if data.current_password == data.new_password:
        raise HTTPException(422,"Choose a new password")
    with db.tx() as con:
        row=con.execute("SELECT password_hash FROM users WHERE id=?",(user["id"],)).fetchone()
        if not row or not verify_password(data.current_password,row["password_hash"]):
            raise HTTPException(403,"Current password is incorrect")
        con.execute("UPDATE users SET password_hash=? WHERE id=?",(hash_password(data.new_password),user["id"]))
        # Revoke all sessions, including the current browser, after password change.
        con.execute("DELETE FROM sessions WHERE user_id=?",(user["id"],))
        db.audit(con,user["id"],"password_changed","users",user["id"])
    response.delete_cookie(COOKIE_NAME,path="/")
    return {"changed":True,"relogin_required":True}

@app.get("/api/dashboard")
def dashboard(user=Depends(user_for)):
    with db.read() as con:
        def count(table,where="1=1"):
            return con.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]
        return {
            "threads":count("threads"),
            "pending_drafts":count("drafts","state='pending'"),
            "approved_knowledge":count("knowledge","status='approved'"),
            "pending_rules":count("rules","status='pending'"),
            "scenarios":count("scenarios"),
            "sent":count("drafts","state='sent'"),
            "latest_audit":[dict(x) for x in con.execute(
                "SELECT action,entity,created_at FROM audit ORDER BY id DESC LIMIT 8").fetchall()],
            "integration":{"openai":settings.ai_ready(),"meta":settings.meta_ready(),"auto_send":False}
        }

@app.get("/api/settings")
def integration_status(user=Depends(OWNER)):
    return {"openai_ready":settings.ai_ready(),"openai_model":settings.OPENAI_MODEL,
        "instagram_ready":settings.meta_ready(),"instagram_account_configured":bool(settings.META_IG_USER_ID),
        "environment":settings.APP_ENV,
        "auto_send_enabled":False, "note":"All live Instagram sends require human approval."}

class KnowledgeIn(BaseModel):
    title:str=Field(min_length=4,max_length=150)
    body:str=Field(min_length=20,max_length=10000)
    category:Literal["brand","engineering","sales","faq","policy","content","other"]="other"

@app.get("/api/knowledge")
def list_knowledge(user=Depends(user_for)):
    with db.read() as con:
        return [dict(x) for x in con.execute("SELECT id,title,body,category,status,created_at,reviewed_at FROM knowledge ORDER BY id DESC LIMIT 300")]

@app.post("/api/knowledge")
def add_knowledge(data:KnowledgeIn,user=Depends(EDITOR)):
    with db.tx() as con:
        cur=con.execute("INSERT INTO knowledge(title,body,category,status,created_by,created_at) VALUES(?,?,?,'pending',?,?)",
            (data.title.strip(),data.body.strip(),data.category,user["id"],db.now()))
        db.audit(con,user["id"],"knowledge_proposed","knowledge",cur.lastrowid)
        return {"id":cur.lastrowid,"status":"pending"}

class DecisionIn(BaseModel):
    decision:Literal["approved","rejected"]

@app.post("/api/knowledge/{id}/review")
def review_knowledge(id:int,data:DecisionIn,user=Depends(OWNER)):
    with db.tx() as con:
        cur=con.execute("UPDATE knowledge SET status=?,reviewed_by=?,reviewed_at=? WHERE id=? AND status='pending'",
            (data.decision,user["id"],db.now(),id))
        if cur.rowcount!=1: raise HTTPException(409,"Item missing or already reviewed")
        db.audit(con,user["id"],"knowledge_"+data.decision,"knowledge",id)
        return {"id":id,"status":data.decision}

class RuleIn(BaseModel):
    title:str=Field(min_length=4,max_length=150)
    instruction:str=Field(min_length=10,max_length=1500)
    scope:Literal["global","sales","engineering","support","content"]="global"

@app.get("/api/rules")
def list_rules(user=Depends(user_for)):
    with db.read() as con:
        return [dict(x) for x in con.execute("SELECT id,title,instruction,scope,status,version,created_at FROM rules ORDER BY id DESC LIMIT 250")]

@app.post("/api/rules")
def add_rule(data:RuleIn,user=Depends(EDITOR)):
    with db.tx() as con:
        cur=con.execute(
            "INSERT INTO rules(title,instruction,scope,status,created_by,created_at) VALUES(?,?,?,'pending',?,?)",
            (data.title.strip(),data.instruction.strip(),data.scope,user["id"],db.now()))
        db.audit(con,user["id"],"rule_proposed","rules",cur.lastrowid)
        return {"id":cur.lastrowid,"status":"pending"}

@app.post("/api/rules/{id}/review")
def review_rule(id:int,data:DecisionIn,user=Depends(OWNER)):
    with db.tx() as con:
        cur=con.execute("UPDATE rules SET status=?,reviewed_by=?,reviewed_at=? WHERE id=? AND status='pending'",
            (data.decision,user["id"],db.now(),id))
        if cur.rowcount!=1: raise HTTPException(409,"Rule missing or already reviewed")
        db.audit(con,user["id"],"rule_"+data.decision,"rules",id)
        return {"id":id,"status":data.decision}

@app.get("/api/threads")
def list_threads(user=Depends(EDITOR)):
    with db.read() as con:
        return [dict(x) for x in con.execute(
            "SELECT t.*, (SELECT COUNT(*) FROM drafts d JOIN messages m ON m.id=d.message_id "
            "WHERE m.thread_id=t.id AND d.state='pending') AS pending_count "
            "FROM threads t ORDER BY last_received_at DESC LIMIT 200")]

@app.get("/api/threads/{id}")
def thread(id:int,user=Depends(EDITOR)):
    with db.read() as con:
        th=con.execute("SELECT * FROM threads WHERE id=?",(id,)).fetchone()
        if not th: raise HTTPException(404,"Thread not found")
        rows=con.execute(
            "SELECT m.id,m.direction,m.body,m.status,m.received_at,m.remote_object_id,"
            " d.id AS draft_id,d.text AS draft_text,d.state AS draft_state,d.risk,d.specialty,d.generated_by,d.citations "
            "FROM messages m LEFT JOIN drafts d ON d.message_id=m.id WHERE m.thread_id=? ORDER BY m.id LIMIT 250",
            (id,)).fetchall()
        return {"thread":dict(th),"messages":[dict(x) for x in rows]}

class DemoIn(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    text:str=Field(min_length=2,max_length=2800)
    kind:Literal["dm","comment"]="dm"

def ingest(platform,kind,remote_user_id,label,text,event_key,remote_object_id=None,received_at=None):
    received_at=received_at or db.now()
    with db.tx() as con:
        try:
            con.execute("INSERT INTO events(event_key,received_at) VALUES(?,?)",(event_key,db.now()))
        except Exception as e:
            if "UNIQUE" in str(e):
                return None
            raise
        con.execute(
            "INSERT INTO threads(platform,kind,remote_user_id,label,status,last_received_at) "
            "VALUES(?,?,?,?,'open',?) ON CONFLICT(platform,kind,remote_user_id) "
            "DO UPDATE SET last_received_at=excluded.last_received_at,label=excluded.label",
            (platform,kind,remote_user_id,label,received_at))
        tid=con.execute("SELECT id FROM threads WHERE platform=? AND kind=? AND remote_user_id=?",
            (platform,kind,remote_user_id)).fetchone()[0]
        cur=con.execute(
            "INSERT INTO messages(thread_id,external_id,direction,body,remote_object_id,status,received_at) "
            "VALUES(?,?,'in',?,?,'new',?)",
            (tid,event_key,text[:settings.AI_INPUT_LIMIT],remote_object_id,received_at))
        db.audit(con,"webhook" if platform=="instagram" else "demo","message_received","messages",cur.lastrowid,
            {"channel":kind,"platform":platform})
        return {"thread_id":tid,"message_id":cur.lastrowid}

@app.post("/api/demo/message")
def demo_message(data:DemoIn,user=Depends(EDITOR)):
    # No external sends occur on demo threads.
    key="demo:"+secrets.token_hex(16)
    item=ingest("demo",data.kind,data.name.strip().lower(),data.name.strip(),data.text,key)
    return {"created":True,**item,"note":"Worker will prepare a draft, no Instagram send"}

@app.post("/api/agent/preview")
def agent_preview(data:DemoIn,user=Depends(EDITOR)):
    d=create_reply(data.text)
    return {"text":d.text,"specialty":d.specialty,"risk":d.risk,"citations":d.citations,
            "generated_by":d.generated_by,"note":"Preview only; not sent"}

class ApproveIn(BaseModel):
    text:str=Field(min_length=2,max_length=1800)

def within_window(when,kind):
    # Conservative safety gate; server never trusts model to decide eligibility.
    try:
        date=datetime.fromisoformat(when)
        seconds=(datetime.now(timezone.utc)-date.astimezone(timezone.utc)).total_seconds()
        return 0<=seconds<(24*3600 if kind=="dm" else 7*24*3600)
    except (TypeError,ValueError):
        return False

@app.post("/api/drafts/{id}/approve")
def approve_draft(id:int,data:ApproveIn,user=Depends(EDITOR)):
    with db.tx() as con:
        row=con.execute(
            "SELECT d.*,m.received_at,m.remote_object_id,t.platform,t.kind,t.remote_user_id "
            "FROM drafts d JOIN messages m ON m.id=d.message_id "
            "JOIN threads t ON t.id=m.thread_id WHERE d.id=?",(id,)).fetchone()
        if not row: raise HTTPException(404,"Draft not found")
        if row["state"] not in ("pending","failed"): raise HTTPException(409,"Already handled")
        if row["platform"]=="instagram":
            if not settings.meta_ready():
                raise HTTPException(409,"Meta credentials not configured")
            if not within_window(row["received_at"],row["kind"]):
                raise HTTPException(409,"Reply window expired; manual handling required")
            state="sending"
        else:
            state="approved"
        con.execute("UPDATE drafts SET text=?,state=?,decided_by=?,decided_at=?,error=NULL WHERE id=?",
            (data.text.strip(),state,user["id"],db.now(),id))
        db.audit(con,user["id"],"draft_approved","drafts",id,{"platform":row["platform"]})
        platform,kind,remote_id,remote_object=row["platform"],row["kind"],row["remote_user_id"],row["remote_object_id"]
    if platform=="demo":
        return {"id":id,"state":"approved","note":"Demo mode: no external message sent"}
    try:
        external_id=send_reply(kind=kind,recipient=remote_id,body=data.text.strip(),reply_to=remote_object)
    except Exception:
        with db.tx() as con:
            con.execute("UPDATE drafts SET state='failed',error='Meta sending failed; inspect service logs' WHERE id=? AND state='sending'",(id,))
            db.audit(con,"system","send_failed","drafts",id)
        raise HTTPException(502,"Meta did not confirm delivery; check Instagram before retrying to prevent duplicates")
    with db.tx() as con:
        con.execute("UPDATE drafts SET state='sent',external_reply_id=? WHERE id=? AND state='sending'",(external_id,id))
        db.audit(con,"system","send_confirmed","drafts",id)
    return {"id":id,"state":"sent"}

@app.post("/api/drafts/{id}/reject")
def reject_draft(id:int,user=Depends(EDITOR)):
    with db.tx() as con:
        cur=con.execute("UPDATE drafts SET state='rejected',decided_by=?,decided_at=? WHERE id=? AND state='pending'",(user["id"],db.now(),id))
        if cur.rowcount!=1: raise HTTPException(409,"Not pending")
        db.audit(con,user["id"],"draft_rejected","drafts",id)
    return {"id":id,"state":"rejected"}

class ScenarioIn(BaseModel):
    topic:str=Field(min_length=5,max_length=300)
    audience:str=Field(min_length=3,max_length=100)
    style:str=Field(min_length=3,max_length=100)

@app.post("/api/scenarios")
def generate_scenario(data:ScenarioIn,user=Depends(EDITOR)):
    body,producer=create_scenario(data.topic,data.audience,data.style)
    with db.tx() as con:
        cur=con.execute("INSERT INTO scenarios(topic,audience,style,body,generated_by,author_id,created_at) VALUES(?,?,?,?,?,?,?)",
            (data.topic,data.audience,data.style,body,producer,user["id"],db.now()))
        db.audit(con,user["id"],"scenario_generated","scenarios",cur.lastrowid,{"producer":producer})
        return {"id":cur.lastrowid,"body":body,"generated_by":producer}

@app.get("/api/scenarios")
def scenarios(user=Depends(user_for)):
    with db.read() as con:
        return [dict(x) for x in con.execute("SELECT id,topic,audience,style,body,generated_by,created_at FROM scenarios ORDER BY id DESC LIMIT 150")]

@app.get("/api/audit")
def audit_log(user=Depends(OWNER)):
    with db.read() as con:
        return [dict(x) for x in con.execute("SELECT id,actor,action,entity,entity_id,created_at FROM audit ORDER BY id DESC LIMIT 150")]

@app.get("/webhooks/instagram")
def webhook_verify(request:Request):
    p=request.query_params
    if p.get("hub.mode")=="subscribe" and settings.META_VERIFY_TOKEN and hmac.compare_digest(
            p.get("hub.verify_token",""),settings.META_VERIFY_TOKEN):
        return Response(content=p.get("hub.challenge",""),media_type="text/plain")
    raise HTTPException(403,"Verification failed")

def meta_timestamp(value):
    try:
        date=datetime.fromtimestamp(int(value)/1000,timezone.utc)
        if abs((datetime.now(timezone.utc)-date).total_seconds())>7*24*3600:
            return None
        return date.isoformat(timespec="seconds")
    except (ValueError,TypeError,OverflowError):
        return None

@app.post("/webhooks/instagram")
async def webhook_receive(request:Request):
    body=await request.body()
    if len(body)>200_000:
        raise HTTPException(413,"Payload too large")
    if not verify_webhook(body,request.headers.get("X-Hub-Signature-256",""),settings.META_APP_SECRET):
        raise HTTPException(403,"Invalid webhook signature")
    try:
        payload=json.loads(body)
    except ValueError:
        raise HTTPException(400,"Invalid JSON")
    if payload.get("object")!="instagram":
        return {"received":True}
    accepted=0
    for entry in payload.get("entry",[])[:30]:
        if str(entry.get("id"))!=settings.META_IG_USER_ID:
            continue
        for event in entry.get("messaging",[])[:100]:
            msg=event.get("message") or {}
            if msg.get("is_echo") or not isinstance(msg.get("text"),str):
                continue
            sender=str((event.get("sender") or {}).get("id") or "")
            mid=str(msg.get("mid") or "")
            stamp=meta_timestamp(event.get("timestamp"))
            if not sender or not mid or not stamp or len(sender)>120: continue
            if ingest("instagram","dm",sender,"Instagram · "+sender[-8:],msg["text"],
                      "dm:"+mid,mid,stamp):
                accepted+=1
        for change in entry.get("changes",[])[:100]:
            if change.get("field") not in ("comments","live_comments"):
                continue
            val=change.get("value") or {}
            comment_id=str(val.get("id") or "")
            sender=str((val.get("from") or {}).get("id") or "")
            body_text=val.get("text")
            if not comment_id or not sender or not isinstance(body_text,str):continue
            if ingest("instagram","comment",sender,"Comment · "+sender[-8:],body_text,
                      "comment:"+comment_id,comment_id):
                accepted+=1
    return {"received":True,"accepted":accepted}
