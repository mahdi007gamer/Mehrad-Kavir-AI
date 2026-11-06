"""v0.2 regression tests: encrypted connections, review gates and update tickets."""
import base64
import json
import secrets
import pytest
from fastapi.testclient import TestClient
from app import db,settings
from app.main import app
from app import integrations

@pytest.fixture()
def owner(tmp_path,monkeypatch):
    env={
        "DB_PATH":str(tmp_path/"v2.sqlite3"),
        "BOOTSTRAP_ADMIN_EMAIL":"owner@example.test",
        "BOOTSTRAP_ADMIN_PASSWORD":"test-only-initial-password-4567",
        "OPENAI_API_KEY":"",
        "OPENAI_MODEL":"gpt-5-mini",
        "META_ACCESS_TOKEN":"",
        "META_APP_SECRET":"",
        "META_VERIFY_TOKEN":"",
        "META_IG_USER_ID":"",
        "META_GRAPH_VERSION":"v25.0",
        "APP_REVISION":"a"*40,
        "AUTO_REPLY_ENABLED":False,
        "COOKIE_SECURE":False,
        "APP_ENV":"development",
    }
    for name,value in env.items():monkeypatch.setattr(settings,name,value)
    monkeypatch.setenv("VAULT_ENCRYPTION_KEY",base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
    with TestClient(app) as client:
        auth=client.post("/api/auth/login",json={"email":"owner@example.test","password":env["BOOTSTRAP_ADMIN_PASSWORD"]})
        assert auth.status_code==200,auth.text
        yield client,{"X-CSRF-Token":auth.json()["csrf"]}

def test_secure_openai_configuration(owner):
    c,h=owner
    key="sk-"+"test-do-not-use-"*3
    assert c.get("/api/integrations").json()["vault_ready"] is True
    assert c.post("/api/integrations/openai",json={"api_key":key,"model":"gpt-5-mini"}).status_code==403
    saved=c.post("/api/integrations/openai",headers=h,json={"api_key":key,"model":"gpt-5-mini"})
    assert saved.status_code==200,saved.text
    assert settings.ai_ready()
    data=c.get("/api/integrations").json()
    assert data["openai"]["fields"]["OPENAI_API_KEY"]["configured"]
    assert data["openai"]["fields"]["OPENAI_API_KEY"]["value"] is None
    with db.read() as con:
        ciphertext=con.execute("SELECT ciphertext FROM integration_secrets WHERE name='OPENAI_API_KEY'").fetchone()[0]
    assert key.encode() not in bytes(ciphertext)
    assert c.post("/api/integrations/openai",headers=h,json={"model":"gpt-4.1-mini"}).status_code==200
    assert settings.effective("OPENAI_API_KEY")==key
    assert c.post("/api/integrations/openai/disconnect",headers=h).json()["disconnected"]
    assert not settings.ai_ready()

def test_meta_configuration_must_belong_to_mehrad(owner,monkeypatch):
    c,h=owner
    token="IGQVJ"+"test1234567890"*4
    resp=c.post("/api/integrations/meta",headers=h,json={
        "ig_user_id":"17841400000000000",
        "access_token":token,
        "app_secret":"0123456789abcdef0123456789abcdef",
        "verify_token":"mehrad-private-test-verification",
        "graph_version":"v25.0"})
    assert resp.status_code==200,resp.text
    assert settings.meta_ready()
    with db.read() as con:
        raw=con.execute("SELECT ciphertext FROM integration_secrets WHERE name='META_ACCESS_TOKEN'").fetchone()[0]
    assert token.encode() not in bytes(raw)
    class FakeResponse:
        status_code=200
        def json(self):return {"id":"17841400000000000","username":"another-brand","account_type":"BUSINESS"}
    class FakeClient:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def get(self,*args,**kwargs):return FakeResponse()
    monkeypatch.setattr(integrations.httpx,"Client",FakeClient)
    checked=c.post("/api/integrations/meta/test",headers=h)
    assert checked.status_code==409
    assert not c.get("/api/integrations").json()["meta"]["verified"]

def test_document_edit_requires_review(owner):
    c,h=owner
    documents=c.get("/api/knowledge").json()
    doc=next(d for d in documents if d["status"]=="approved")
    newtext="این متن به صورت پیشنهادی ثبت می‌شود و نباید پیش از تأیید توسط کارشناس وارد دانش فعال گردد."
    r=c.post("/api/knowledge/"+str(doc["id"])+"/revisions",headers=h,json={
        "base_version":doc["version"],"title":"سند به‌روزشده تأییدشده",
        "body":newtext,"category":"brand"})
    assert r.status_code==200,r.text
    revision_id=r.json()["revision_id"]
    assert c.get("/api/knowledge/"+str(doc["id"])+"/history").json()["current"]["body"]==doc["body"]
    assert c.post("/api/knowledge/revisions/"+str(revision_id)+"/review",headers=h,
      json={"decision":"approved"}).status_code==200
    current=c.get("/api/knowledge/"+str(doc["id"])+"/history").json()["current"]
    assert current["version"]==doc["version"]+1
    assert current["body"]==newtext

def test_import_jobs_staged_not_approved(owner,monkeypatch):
    c,h=owner
    r=c.post("/api/import/jobs",headers=h,json={"provider":"website"})
    assert r.status_code==200
    job=r.json()["id"]
    from app import worker
    from app import importers
    def fake_import(job_id,provider):
        assert job_id==job and provider=="website"
        return 1 if importers.stage_document(job,"website","https://mehradkavir.com/faq",
          "تست ورود داده","محتوای رسمی تأییدنشده برای آزمون صف بررسی، بدون امکان ارتقای خودکار به دانش سازمانی مهراد کویر.") else 0
    monkeypatch.setattr(importers,"run_import_job",fake_import)
    assert worker.run_import_once() is True
    staging=c.get("/api/import/documents").json()
    assert len(staging)==1 and staging[0]["status"]=="pending"
    assert c.post("/api/import/documents/"+str(staging[0]["id"])+"/review",headers=h,
      json={"decision":"approved"}).status_code==200
    assert c.get("/api/import/documents").json()[0]["status"]=="approved"
    assert c.get("/api/knowledge").json()[0]["source_type"]=="website"

def test_auto_policy_fail_closed(owner):
    c,h=owner
    r=c.post("/api/automation/policies",headers=h,json={
      "keyword":"سلام","template":"سلام، به مهراد کویر خوش آمدید. موضوع پروژه خود را بفرمایید."})
    assert r.status_code==200
    assert r.json()["enabled"] is False
    result=c.post("/api/automation/policies/"+str(r.json()["id"])+"/toggle",
      headers=h,json={"enabled":True})
    assert result.status_code==409

def test_update_requires_owner_and_matching_latest_sha(owner,monkeypatch):
    c,h=owner
    from app import updates
    monkeypatch.setattr(updates,"remote_head",lambda force=False:{"sha":"b"*40,"message":"Trusted test commit","date":"2026-11-06","url":"https://github.com/mahdi007gamer/Mehrad-Kavir-AI/commit/"+"b"*40})
    assert c.post("/api/updates/approve",json={"sha":"b"*40}).status_code==403
    assert c.post("/api/updates/approve",headers=h,json={"sha":"c"*40}).status_code==409
    r=c.post("/api/updates/approve",headers=h,json={"sha":"b"*40})
    assert r.status_code==200,r.text
    assert r.json()["state"]=="approved"
    assert c.post("/api/updates/approve",headers=h,json={"sha":"b"*40}).status_code==409
