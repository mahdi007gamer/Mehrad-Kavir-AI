import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from app import db, settings
from app.main import app
from app.brain import retrieve
from app.worker import run_once

@pytest.fixture()
def client(tmp_path, monkeypatch):
    for key,value in {
        "DB_PATH":str(tmp_path/"test.sqlite3"),
        "BOOTSTRAP_ADMIN_EMAIL":"admin@test.local",
        "BOOTSTRAP_ADMIN_PASSWORD":"test-only-admin-password-123456",
        "OPENAI_API_KEY":"",
        "META_APP_SECRET":"",
        "META_VERIFY_TOKEN":"",
        "META_IG_USER_ID":"",
        "META_ACCESS_TOKEN":"",
        "APP_ENV":"development",
        "COOKIE_SECURE":False
    }.items():
        monkeypatch.setattr(settings,key,value)
    with TestClient(app) as c:
        yield c

def auth(client):
    r=client.post("/api/auth/login",json={
        "email":"admin@test.local","password":"test-only-admin-password-123456"})
    assert r.status_code==200,r.text
    return {"X-CSRF-Token":r.json()["csrf"]}

def test_health_and_seed(client):
    assert client.get("/health").json()["status"]=="ok"
    assert client.get("/api/me").status_code==401
    auth(client)
    d=client.get("/api/dashboard").json()
    assert d["approved_knowledge"]>=34  # Original 2 plus curated approved knowledge
    assert d["integration"]["auto_send"] is False
    assert client.get("/api/settings").json()["instagram_ready"] is False

def test_failed_login_rate_limit(client):
    for _ in range(8):
        assert client.post("/api/auth/login",json={"email":"wrong@test.local","password":"wrong"}).status_code==401
    assert client.post("/api/auth/login",json={"email":"admin@test.local","password":"test-only-admin-password-123456"}).status_code==429

def test_knowledge_review_and_csrf(client):
    headers=auth(client)
    data={"title":"اطلاعات فنی نمونه","body":"این یک متن تأییدنشده برای اطمینان از مسیر تأیید و حافظه است.","category":"engineering"}
    assert client.post("/api/knowledge",json=data).status_code==403
    r=client.post("/api/knowledge",headers=headers,json=data)
    assert r.status_code==200
    id=r.json()["id"]
    assert id not in {x["id"] for x in retrieve("اطلاعات فنی نمونه","engineering")[0]}
    assert client.post(f"/api/knowledge/{id}/review",headers=headers,json={"decision":"approved"}).status_code==200
    assert id in {x["id"] for x in retrieve("اطلاعات فنی نمونه","engineering")[0]}
    assert client.post(f"/api/knowledge/{id}/review",headers=headers,json={"decision":"approved"}).status_code==409

def test_memory_approval(client):
    headers=auth(client)
    data={"title":"هوک تصویر قوی","instruction":"هوک ریلز با یک اتفاق تصویری قابل اجرا و مرتبط شروع شود.","scope":"content"}
    id=client.post("/api/rules",headers=headers,json=data).json()["id"]
    assert not any("اتفاق تصویری" in s for s in retrieve("هوک","content")[1])
    assert client.post(f"/api/rules/{id}/review",headers=headers,json={"decision":"approved"}).status_code==200
    assert any("اتفاق تصویری" in s for s in retrieve("هوک","content")[1])

def test_inbox_demo_and_draft(client):
    headers=auth(client)
    r=client.post("/api/demo/message",headers=headers,json={"name":"متقاضی","text":"قیمت سازه نیروگاه چقدر است؟","kind":"dm"})
    assert r.status_code==200
    assert run_once() is True
    assert run_once() is False
    detail=client.get("/api/threads/"+str(r.json()["thread_id"])).json()
    draft=detail["messages"][0]
    assert draft["draft_state"]=="pending"
    assert draft["generated_by"]=="fallback_no_api_key"
    id=draft["draft_id"]
    assert client.post(f"/api/drafts/{id}/approve",json={"text":"سلام، دریافت شد"}).status_code==403
    accepted=client.post(f"/api/drafts/{id}/approve",headers=headers,json={"text":"سلام، دریافت شد"})
    assert accepted.json()["state"]=="approved"
    assert client.post(f"/api/drafts/{id}/approve",headers=headers,json={"text":"دوباره"}).status_code==409
    assert client.get("/api/dashboard").json()["sent"]==0

def test_content_template_is_explicit(client):
    headers=auth(client)
    r=client.post("/api/scenarios",headers=headers,json={"topic":"سازه بایفیشیال","audience":"سرمایه‌گذار","style":"مهندسی"})
    assert r.status_code==200
    assert r.json()["generated_by"]=="template_no_api_key"
    assert "قالب آزمایشی" in r.json()["body"]

def test_webhook_signature_replay_and_verification(client,monkeypatch):
    monkeypatch.setattr(settings,"META_APP_SECRET","local-test-secret")
    monkeypatch.setattr(settings,"META_VERIFY_TOKEN","verify-test")
    monkeypatch.setattr(settings,"META_IG_USER_ID","12345")
    assert client.get("/webhooks/instagram",params={"hub.mode":"subscribe","hub.verify_token":"wrong","hub.challenge":"hi"}).status_code==403
    assert client.get("/webhooks/instagram",params={"hub.mode":"subscribe","hub.verify_token":"verify-test","hub.challenge":"hi"}).text=="hi"
    stamp=int(datetime.now(timezone.utc).timestamp()*1000)
    payload={"object":"instagram","entry":[{"id":"12345","messaging":[{"sender":{"id":"456"},"timestamp":stamp,"message":{"mid":"abc-001","text":"سلام، قیمت دارید؟"}}]}]}
    body=json.dumps(payload).encode()
    assert client.post("/webhooks/instagram",content=body).status_code==403
    sig=hmac.new(b"local-test-secret",body,hashlib.sha256).hexdigest()
    headers={"X-Hub-Signature-256":"sha256="+sig,"Content-Type":"application/json"}
    assert client.post("/webhooks/instagram",content=body,headers=headers).json()["accepted"]==1
    assert client.post("/webhooks/instagram",content=body,headers=headers).json()["accepted"]==0
    assert run_once() is True
    auth(client)
    assert client.get("/api/threads").json()[0]["platform"]=="instagram"

def test_meta_missing_blocks_send(client):
    headers=auth(client)
    with db.tx() as con:
        con.execute("INSERT INTO threads(platform,kind,remote_user_id,label,last_received_at) VALUES('instagram','dm','notoken','No token',?)",(db.now(),))
        tid=con.execute("SELECT id FROM threads ORDER BY id DESC LIMIT 1").fetchone()[0]
        con.execute("INSERT INTO messages(thread_id,external_id,direction,body,status,received_at) VALUES(?,?,'in','hello','new',?)",(tid,"test:notoken",db.now()))
    assert run_once()
    draft=client.get("/api/threads/"+str(tid)).json()["messages"][0]
    r=client.post(f'/api/drafts/{draft["draft_id"]}/approve',headers=headers,json={"text":"سلام"})
    assert r.status_code==409
    assert client.get("/api/threads/"+str(tid)).json()["messages"][0]["draft_state"]=="pending"

def test_security_headers(client):
    r=client.get("/")
    assert r.status_code==200
    assert r.headers["x-frame-options"]=="DENY"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert "BOOTSTRAP_ADMIN_PASSWORD" not in r.text
