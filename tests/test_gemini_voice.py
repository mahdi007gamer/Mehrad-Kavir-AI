"""Gemini integration and guarded inbound telephone system smoke/security tests."""
import base64
import json
import secrets
from urllib.parse import urlencode
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from app import db, settings
from app.main import app
from app import phone_calls, gemini_engine

@pytest.fixture()
def env(tmp_path,monkeypatch):
    for k,v in {
      "DB_PATH":str(tmp_path/"v03.sqlite3"),
      "BOOTSTRAP_ADMIN_EMAIL":"owner@example.local",
      "BOOTSTRAP_ADMIN_PASSWORD":"secure-local-pilot-test-password-123456",
      "OPENAI_API_KEY":"",
      "AI_PROVIDER":"openai",
      "GEMINI_API_KEY":"",
      "GEMINI_MODEL":"gemini-3.8-flash",
      "GEMINI_LIVE_MODEL":"gemini-3.8-live",
      "GEMINI_TTS_MODEL":"gemini-3.8-flash-tts",
      "GEMINI_VOICE":"Kore",
      "TWILIO_AUTH_TOKEN":"",
      "TWILIO_ACCOUNT_SID":"",
      "PHONE_PUBLIC_BASE_URL":"",
      "PHONE_RECEPTION_ENABLED":"false",
      "META_ACCESS_TOKEN":"",
      "META_IG_USER_ID":"",
      "META_APP_SECRET":"",
      "META_VERIFY_TOKEN":"",
      "APP_ENV":"development",
      "COOKIE_SECURE":False
    }.items():
        monkeypatch.setattr(settings,k,v)
    monkeypatch.setenv("VAULT_ENCRYPTION_KEY",base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
    with TestClient(app) as client:
        login=client.post("/api/auth/login",json={
            "email":"owner@example.local","password":"secure-local-pilot-test-password-123456"})
        assert login.status_code==200,login.text
        yield client,{"X-CSRF-Token":login.json()["csrf"]},monkeypatch

def test_gemini_encrypted_settings_provider_and_preview(env):
    client,h,monkeypatch=env
    key="AIza"+"no-real-google-credential-test-"*3
    payload={"api_key":key,"text_model":"gemini-3.8-flash",
             "live_model":"gemini-3.8-live","tts_model":"gemini-3.8-flash-tts","voice":"Kore"}
    assert client.post("/api/providers/gemini",json=payload).status_code==403
    result=client.post("/api/providers/gemini",headers=h,json=payload)
    assert result.status_code==200,result.text
    p=client.get("/api/providers").json()
    assert p["gemini"]["fields"]["GEMINI_API_KEY"]["configured"]
    assert p["gemini"]["fields"]["GEMINI_API_KEY"]["value"] is None
    with db.read() as con:
        raw=con.execute("SELECT ciphertext FROM integration_secrets WHERE name='GEMINI_API_KEY'").fetchone()[0]
    assert key.encode() not in bytes(raw)
    assert client.post("/api/providers/select",headers=h,json={"provider":"gemini"}).status_code==200
    assert client.get("/api/providers").json()["selected"]=="gemini"
    assert settings.ai_ready()
    from app import google_voice_settings
    monkeypatch.setattr(google_voice_settings,"tts_wav",lambda text:b"RIFF"+b"\0"*48)
    sound=client.post("/api/voice/preview",headers=h,json={"text":"سلام، مهراد کویر."})
    assert sound.status_code==200
    assert sound.headers["content-type"].startswith("audio/wav")
    assert sound.content.startswith(b"RIFF")
    assert client.post("/api/providers/gemini/disconnect",headers=h).json()["disconnected"]
    assert client.get("/api/providers").json()["selected"]=="openai"
    assert not settings.ai_ready()

def test_gemini_model_adapter_preserves_json_schema(env,monkeypatch):
    client,h,monkeypatch=env
    from app import brain
    from app.vault import write_batch
    write_batch({"AI_PROVIDER":"gemini","GEMINI_API_KEY":"test-google-key"},1)
    def mocked_structured(instructions,text,schema,name):
        assert "confidential" not in text
        assert schema["required"] == ["answer","risk","needs_human","reason","sources"]
        return {"answer":"لطفاً شهر پروژه را بفرمایید.","risk":"high",
                "needs_human":True,"reason":"Need engineering review","sources":[]}
    monkeypatch.setattr(gemini_engine,"structured",mocked_structured)
    result=brain.create_reply("برای سازه قیمت می‌خواهم.")
    assert result.generated_by=="gemini"
    assert result.risk=="high"
    assert "شهر پروژه" in result.text

def test_phone_webhook_requires_valid_twilio_signature(env):
    client,h,monkeypatch=env
    assert client.post("/voice/twilio/incoming",data={
      "AccountSid":"AC"+"a"*32,"CallSid":"CA"+"b"*32}).status_code==403
    from app.vault import write_batch
    account="AC"+"a"*32
    token="b"*32
    write_batch({"TWILIO_ACCOUNT_SID":account,"TWILIO_AUTH_TOKEN":token,
                 "PHONE_PUBLIC_BASE_URL":"https://voice.example.com",
                 "PHONE_RECEPTION_ENABLED":"true","GEMINI_API_KEY":"google-test"},1)
    url="https://voice.example.com/voice/twilio/incoming"
    data={"AccountSid":account,"CallSid":"CA"+"c"*32,"From":"+989121112233"}
    signer=RequestValidator(token)
    signature=signer.compute_signature(url,data)
    request=client.post("/voice/twilio/incoming",data=data,
              headers={"X-Twilio-Signature":signature})
    assert request.status_code==200,request.text
    assert "<Connect><Stream " in request.text
    assert "wss://voice.example.com/voice/twilio/media" in request.text
    assert "session" not in request.text or "ticket" in request.text
    assert client.post("/voice/twilio/incoming",data=data,
         headers={"X-Twilio-Signature":signature}).status_code==200
    with db.read() as con:
        assert con.execute("SELECT COUNT(*) FROM phone_calls").fetchone()[0]==1
    assert client.post("/voice/twilio/incoming",data=data,
         headers={"X-Twilio-Signature":"invalid"}).status_code==403

def test_no_implicit_call_consent(env):
    client,h,monkeypatch=env
    assert not phone_calls._explicit_contact_consent([
      ("assistant","شهر پروژه کجاست؟"),("caller","بله، در قم.")])
    assert not phone_calls._explicit_contact_consent([
      ("assistant","اجازه می‌دهید مشخصات برای پیگیری ثبت شود؟"),("caller","خیر")])
    assert phone_calls._explicit_contact_consent([
      ("assistant","اجازه می‌دهید مشخصات برای پیگیری ثبت شود؟"),("caller","بله، مشکلی نیست")])

def test_voice_lead_candidate_is_reviewed_before_crm(env,monkeypatch):
    client,h,monkeypatch=env
    from app import phone_calls as voice
    from app.vault import cipher
    sid="CA"+"1"*32
    with db.tx() as con:
        con.execute("INSERT INTO phone_calls(provider,call_sid,stream_token_hash,status,started_at) "
                    "VALUES('twilio',?,'x','ended',?)",(sid,db.now()))
        callid=con.execute("SELECT id FROM phone_calls WHERE call_sid=?",(sid,)).fetchone()[0]
    transcription=[
      ("assistant","سلام، من دستیار هوشمند مهراد کویر هستم. چه کاری انجام دهم؟"),
      ("caller","سلام، برای سازه یک نیروگاه سه مگاواتی در قم تماس گرفتم."),
      ("assistant","اجازه می‌دهید مشخصات تماس و پروژه برای پیگیری ثبت شود؟"),
      ("caller","بله، مشکلی نیست.")]
    monkeypatch.setattr(voice,"extract_lead_proposal",lambda transcript:{
      "consent_to_contact":True,"caller_name":"متقاضی تست",
      "company":"","project_city":"قم","capacity_mw":3.0,
      "foundation":"بتنی","panel_layout":"۲×۱۴",
      "request_summary":"استعلام سازه سه مگاواتی","requires_human":True,"confidence":"medium"})
    voice._store_consented_proposal(callid,"+989121112233",transcription)
    with db.read() as con:
        assert con.execute("SELECT COUNT(*) FROM leads").fetchone()[0]==0
        proposal=con.execute("SELECT id,details_ciphertext FROM phone_lead_proposals WHERE call_id=?",
                             (callid,)).fetchone()
    assert proposal is not None
    assert b"استعلام" not in bytes(proposal["details_ciphertext"])
    result=client.get("/api/voice/proposals/"+str(proposal["id"]))
    assert result.status_code==200
    assert result.json()["phone"]=="+989121112233"
    approve=client.post("/api/voice/proposals/"+str(proposal["id"])+"/review",
                        headers=h,json={"decision":"approved"})
    assert approve.status_code==200,approve.text
    assert approve.json()["lead_id"]>0
    assert client.post("/api/voice/proposals/"+str(proposal["id"])+"/review",
                       headers=h,json={"decision":"approved"}).status_code==409
    with db.read() as con:
        assert con.execute("SELECT COUNT(*) FROM leads").fetchone()[0]==1

def test_call_without_explicit_consent_persists_no_details(env,monkeypatch):
    client,h,monkeypatch=env
    from app import phone_calls as voice
    sid="CA"+"2"*32
    with db.tx() as con:
        con.execute("INSERT INTO phone_calls(provider,call_sid,stream_token_hash,status,started_at)"
                    "VALUES('twilio',?,'x','ended',?)",(sid,db.now()))
        callid=con.execute("SELECT id FROM phone_calls WHERE call_sid=?",(sid,)).fetchone()[0]
    # Even a broken model claiming consent must not create data without caller approval.
    monkeypatch.setattr(voice,"extract_lead_proposal",lambda txt:{
        "consent_to_contact":True,"caller_name":"Invalid automatic claim"})
    voice._store_consented_proposal(callid,"+989121112233",[
       ("assistant","شهر پروژه چیست؟"),("caller","بله، قم.")])
    with db.read() as con:
        row=con.execute("SELECT transcript_ciphertext,caller_ciphertext,consent_to_contact FROM phone_calls WHERE id=?",
                         (callid,)).fetchone()
        assert row["consent_to_contact"]==0
        assert row["transcript_ciphertext"] is None
        assert row["caller_ciphertext"] is None
        assert con.execute("SELECT COUNT(*) FROM phone_lead_proposals").fetchone()[0]==0
