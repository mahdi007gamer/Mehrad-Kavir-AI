"""Additional owner-only AI and telephony configurations. No secrets returned to UI."""
import re
from urllib.parse import urlsplit
import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from . import settings, db
from .security import role_required
from .vault import write_batch, erase_provider
from .gemini_engine import MODEL_ID,ALLOWED_VOICES,tts_wav

router=APIRouter()
OWNER=role_required("owner")
EDITOR=role_required("owner","editor")

def _state(provider):
    with db.read() as con:
        check=con.execute("SELECT status,label,checked_at FROM provider_checks WHERE provider=?",(provider,)).fetchone()
    return dict(check) if check else None

def _record(provider,ok,label=None):
    with db.tx() as con:
        con.execute(
            "INSERT INTO provider_checks(provider,status,label,checked_at) VALUES(?,?,?,?) "
            "ON CONFLICT(provider) DO UPDATE SET status=excluded.status,label=excluded.label,checked_at=excluded.checked_at",
            (provider,"ok" if ok else "failed",label,db.now()))
        db.audit(con,"connection-check","provider_test","provider_checks",provider,{"success":ok})

def _fields(names,secret_names):
    return {n:{"configured":bool(settings.effective(n)),
               "value":None if n in secret_names else (settings.effective(n) or None)} for n in names}

def _public_https(value):
    try:
        p=urlsplit(value)
        return p.scheme=="https" and p.hostname and "." in p.hostname and not p.username and not p.password and p.port in (None,443) and p.path in ("","/")
    except ValueError:return False

@router.get("/api/providers")
def providers(user=Depends(OWNER)):
    gemini_names=["GEMINI_API_KEY","GEMINI_MODEL","GEMINI_LIVE_MODEL","GEMINI_TTS_MODEL","GEMINI_VOICE"]
    phone_names=["TWILIO_ACCOUNT_SID","TWILIO_AUTH_TOKEN","PHONE_PUBLIC_BASE_URL","PHONE_RECEPTION_ENABLED"]
    return {
        "selected":settings.effective("AI_PROVIDER"),
        "gemini":{"fields":_fields(gemini_names,{"GEMINI_API_KEY"}),"test":_state("gemini"),
                  "text_ready":bool(settings.effective("GEMINI_API_KEY"))},
        "telephony":{"fields":_fields(phone_names,{"TWILIO_AUTH_TOKEN"}),
                     "test":_state("telephony"),
                     "enabled":settings.effective("PHONE_RECEPTION_ENABLED").lower()=="true",
                     "ready":bool(settings.effective("TWILIO_AUTH_TOKEN") and settings.effective("TWILIO_ACCOUNT_SID") and
                                  _public_https(settings.effective("PHONE_PUBLIC_BASE_URL"))),
                     "note":"Credential verification is not proof that a phone number or SIP trunk is provisioned."},
        "voice_types":["speech_preview","gemini_live_twilio_bridge"],
        "local_only":not settings.effective("PHONE_PUBLIC_BASE_URL")
    }

class GeminiSettings(BaseModel):
    api_key:str|None=Field(default=None,max_length=400)
    text_model:str=Field(default="gemini-3.8-flash",max_length=100)
    live_model:str=Field(default="gemini-3.8-live",max_length=100)
    tts_model:str=Field(default="gemini-3.8-flash-tts",max_length=100)
    voice:str=Field(default="Kore",max_length=35)

@router.post("/api/providers/gemini")
def save_gemini(data:GeminiSettings,user=Depends(OWNER)):
    if not all(MODEL_ID.fullmatch(x) for x in (data.text_model,data.live_model,data.tts_model)):
        raise HTTPException(422,"Invalid Gemini model ID")
    if data.voice not in ALLOWED_VOICES:raise HTTPException(422,"Unrecognized allowlisted voice")
    values={"GEMINI_MODEL":data.text_model,"GEMINI_LIVE_MODEL":data.live_model,
            "GEMINI_TTS_MODEL":data.tts_model,"GEMINI_VOICE":data.voice}
    if data.api_key is not None:
        key=data.api_key.strip()
        if key and (len(key)<20 or len(key)>400 or any(c.isspace() for c in key)):
            raise HTTPException(422,"Invalid Gemini API key format")
        values["GEMINI_API_KEY"]=key
    try:write_batch(values,user["id"])
    except RuntimeError:raise HTTPException(409,"Encrypted vault not initialized")
    with db.tx() as con:con.execute("DELETE FROM provider_checks WHERE provider='gemini'")
    return {"saved":True,"provider":"gemini"}

class SelectAI(BaseModel):
    provider:str
@router.post("/api/providers/select")
def select(data:SelectAI,user=Depends(OWNER)):
    if data.provider not in ("openai","gemini"):raise HTTPException(422,"Unknown AI provider")
    if data.provider=="gemini" and not settings.effective("GEMINI_API_KEY"):
        raise HTTPException(409,"Configure Gemini API first")
    if data.provider=="openai" and not settings.effective("OPENAI_API_KEY"):
        raise HTTPException(409,"Configure OpenAI API first")
    write_batch({"AI_PROVIDER":data.provider},user["id"])
    return {"selected":data.provider}

@router.post("/api/providers/gemini/test")
def test_gemini(user=Depends(OWNER)):
    key=settings.effective("GEMINI_API_KEY")
    model=settings.effective("GEMINI_MODEL")
    if not key:raise HTTPException(409,"Enter a Google AI Studio API key first")
    try:
        with httpx.Client(timeout=14,trust_env=False,follow_redirects=False) as client:
            resp=client.get("https://generativelanguage.googleapis.com/v1beta/models/"+model,
                            headers={"x-goog-api-key":key})
        ok=resp.status_code==200
        _record("gemini",ok,model if ok else None)
        if not ok:raise HTTPException(502,"Google Gemini credential/model check failed (HTTP "+str(resp.status_code)+")")
        return {"ok":True,"model":model,
                "note":"Model metadata accessible; this does not prove Live audio entitlement or TTS generation."}
    except httpx.RequestError:
        _record("gemini",False)
        raise HTTPException(502,"Cannot reach Google Gemini API")

class PhoneSettings(BaseModel):
    account_sid:str=Field(min_length=34,max_length=34)
    auth_token:str|None=Field(default=None,max_length=300)
    public_base_url:str=Field(min_length=12,max_length=200)
    enabled:bool=False

@router.post("/api/providers/telephony")
def save_phone(data:PhoneSettings,user=Depends(OWNER)):
    if not re.fullmatch(r"AC[a-f0-9]{32}",data.account_sid):
        raise HTTPException(422,"Twilio Account SID must be a valid AC identifier")
    if not _public_https(data.public_base_url):
        raise HTTPException(422,"Public base must be a plain HTTPS domain URL without path or port")
    values={"TWILIO_ACCOUNT_SID":data.account_sid,
            "PHONE_PUBLIC_BASE_URL":data.public_base_url.rstrip("/"),
            "PHONE_RECEPTION_ENABLED":"true" if data.enabled else "false"}
    if data.auth_token is not None:
        key=data.auth_token.strip()
        if key and not re.fullmatch(r"[A-Fa-f0-9]{32}",key):
            raise HTTPException(422,"Invalid Twilio Auth Token format")
        values["TWILIO_AUTH_TOKEN"]=key
    try:write_batch(values,user["id"])
    except RuntimeError:raise HTTPException(409,"Encrypted vault not initialized")
    with db.tx() as con:con.execute("DELETE FROM provider_checks WHERE provider='telephony'")
    return {"saved":True,"enabled":data.enabled,
            "warning":"Enabling requires public HTTPS/WSS, verified Twilio number and a working Live model."}

@router.post("/api/providers/telephony/test")
def test_phone(user=Depends(OWNER)):
    sid=settings.effective("TWILIO_ACCOUNT_SID")
    token=settings.effective("TWILIO_AUTH_TOKEN")
    if not sid or not token:raise HTTPException(409,"Configure Twilio credentials first")
    try:
        with httpx.Client(timeout=14,trust_env=False,follow_redirects=False,auth=(sid,token)) as client:
            r=client.get(f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json")
        ok=r.status_code==200
        _record("telephony",ok,"Account authenticated" if ok else None)
        if not ok:raise HTTPException(502,"Twilio account authentication failed (HTTP "+str(r.status_code)+")")
        return {"ok":True,"note":"Twilio credential authenticated; inbound phone number and media webhook not yet checked."}
    except httpx.RequestError:
        _record("telephony",False)
        raise HTTPException(502,"Cannot reach Twilio API")

@router.post("/api/providers/{provider}/disconnect")
def disconnect(provider:str,user=Depends(OWNER)):
    if provider not in ("gemini","telephony"):raise HTTPException(404,"Unknown provider")
    try:erase_provider(provider,user["id"])
    except RuntimeError:raise HTTPException(409,"Encrypted vault unavailable")
    with db.tx() as con:con.execute("DELETE FROM provider_checks WHERE provider=?",(provider,))
    if provider=="gemini" and settings.effective("AI_PROVIDER")=="gemini":
        write_batch({"AI_PROVIDER":"openai"},user["id"])
    return {"disconnected":True,"provider":provider}

class SpeechPreview(BaseModel):
    text:str=Field(min_length=2,max_length=600)

@router.post("/api/voice/preview")
def voice_preview(data:SpeechPreview,user=Depends(EDITOR)):
    if not settings.effective("GEMINI_API_KEY"):
        raise HTTPException(409,"Connect Google Gemini API first")
    try:audio=tts_wav(data.text)
    except Exception:
        # Never leak provider errors or tokens to browser.
        raise HTTPException(502,"Google voice preview failed; inspect selected TTS model and account access")
    return Response(content=audio,media_type="audio/wav",
                    headers={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})
