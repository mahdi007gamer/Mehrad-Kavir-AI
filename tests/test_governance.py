"""Additional regression tests for approved learning and account credential rotation."""
import pytest
from fastapi.testclient import TestClient
from app import settings
from app.main import app
from app.brain import retrieve

@pytest.fixture()
def session(tmp_path, monkeypatch):
    old = "test_" + ("a" * 28)
    monkeypatch.setattr(settings,"DB_PATH",str(tmp_path/"extra.sqlite3"))
    monkeypatch.setattr(settings,"BOOTSTRAP_ADMIN_EMAIL","owner@local.test")
    monkeypatch.setattr(settings,"BOOTSTRAP_ADMIN_PASSWORD",old)
    monkeypatch.setattr(settings,"OPENAI_API_KEY","")
    monkeypatch.setattr(settings,"META_ACCESS_TOKEN","")
    monkeypatch.setattr(settings,"META_IG_USER_ID","")
    monkeypatch.setattr(settings,"META_APP_SECRET","")
    monkeypatch.setattr(settings,"META_VERIFY_TOKEN","")
    monkeypatch.setattr(settings,"APP_ENV","development")
    monkeypatch.setattr(settings,"COOKIE_SECURE",False)
    with TestClient(app) as c:
        response=c.post("/api/auth/login",json={"email":"owner@local.test","password":old})
        assert response.status_code==200
        yield c,{"X-CSRF-Token":response.json()["csrf"]},old

def test_credential_rotation_revokes_old_sessions(session):
    client,headers,old=session
    new="test_" + ("z" * 32)
    r=client.post("/api/account/password",headers=headers,json={
        "current_password":old,"new_password":new})
    assert r.status_code==200
    assert client.get("/api/me").status_code==401
    assert client.post("/api/auth/login",json={"email":"owner@local.test","password":old}).status_code==401
    assert client.post("/api/auth/login",json={"email":"owner@local.test","password":new}).status_code==200

def test_feedback_proposal_stays_pending_until_review(session,monkeypatch):
    from app import brain
    client,headers,_=session
    feedback={"feedback":"هوک ویدیوی قبلی ضعیف بود. شروع باید یک اتفاق فیزیکی و سؤال دقیق داشته باشد.","scope":"content"}
    assert client.post("/api/feedback/propose",headers=headers,json=feedback).status_code==409
    monkeypatch.setattr(settings,"OPENAI_API_KEY","test-mode")
    def fake_model(instructions,input_text,schema,name):
        assert name=="feedback_proposal"
        return {"title":"هوک مبتنی بر عمل", "instruction":"سه ثانیه اول با یک اتفاق تصویری قابل اجرا آغاز شود.",
                "clarifying_question":"","safe_to_propose":True}
    monkeypatch.setattr(brain,"call_model",fake_model)
    result=client.post("/api/feedback/propose",headers=headers,json=feedback)
    assert result.status_code==200
    identifier=result.json()["id"]
    assert result.json()["status"]=="pending"
    assert not any("اتفاق تصویری قابل اجرا" in x for x in retrieve("هوک","content")[1])
    assert client.post(f"/api/rules/{identifier}/review",headers=headers,json={"decision":"approved"}).status_code==200
    assert any("اتفاق تصویری قابل اجرا" in x for x in retrieve("هوک","content")[1])
