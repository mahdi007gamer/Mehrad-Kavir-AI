"""Private integration wizard with encrypted credentials and real provider tests.

Only the owner can read metadata or mutate credentials. Never return raw tokens.
"""
import re
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from . import settings,db
from .security import role_required
from .vault import cipher, write_batch, erase_provider, SECRETS

router=APIRouter()
OWNER=role_required("owner")
VALID_MODEL=re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{1,79}$")
VALID_GRAPH=re.compile(r"^v\d{1,2}\.\d{1,2}$")
VALID_ID=re.compile(r"^\d{4,35}$")

def status_one(provider):
    names=(["OPENAI_API_KEY","OPENAI_MODEL"] if provider=="openai" else
           ["META_ACCESS_TOKEN","META_APP_SECRET","META_VERIFY_TOKEN","META_IG_USER_ID","META_GRAPH_VERSION"])
    values={key:settings.effective(key) for key in names}
    with db.read() as con:
        check=con.execute("SELECT provider,status,account_label,checked_at FROM integration_checks WHERE provider=?",
                         (provider,)).fetchone()
    return {
        "provider":provider,
        "fields":{name:{"configured":bool(values[name]),"value":None if name in SECRETS else (values[name] or None)}
                  for name in names},
        "last_test":dict(check) if check else None,
        "configured":(bool(values["OPENAI_API_KEY"]) if provider=="openai" else
                      all(values.get(key) for key in ("META_ACCESS_TOKEN","META_APP_SECRET","META_VERIFY_TOKEN","META_IG_USER_ID"))),
        "verified":bool(check and check["status"]=="ok"),
        "notes":("A successful Instagram token check does not prove messaging/webhook App Review permission."
                 if provider=="meta" else "A model-list check validates the current OpenAI project credential.")
    }

@router.get("/api/integrations")
def summary(user=Depends(OWNER)):
    try:
        cipher()
        vault_ready=True
    except RuntimeError:
        vault_ready=False
    return {"vault_ready":vault_ready,
            "openai":status_one("openai"),"meta":status_one("meta"),
            "expected_instagram":"mehradkavir",
            "webhook_path":"/webhooks/instagram",
            "meta_required_permissions":["instagram_business_basic",
                "instagram_business_manage_messages","instagram_business_manage_comments",
                "instagram_business_content_publish"],
            "oauth_available":False}

class OpenAIConfig(BaseModel):
    api_key:str|None=Field(default=None,max_length=300)
    model:str=Field(min_length=2,max_length=80)

@router.post("/api/integrations/openai")
def save_openai(data:OpenAIConfig,user=Depends(OWNER)):
    if not VALID_MODEL.fullmatch(data.model):
        raise HTTPException(422,"Invalid model identifier")
    data_out={"OPENAI_MODEL":data.model}
    if data.api_key is not None:
        value=data.api_key.strip()
        if value and (len(value)<18 or not value.startswith("sk-")):
            raise HTTPException(422,"OpenAI API key format is invalid")
        data_out["OPENAI_API_KEY"]=value
    try:
        write_batch(data_out,user["id"])
    except RuntimeError:
        raise HTTPException(409,"Vault encryption key not configured. Run updated installer.")
    with db.tx() as con:
        con.execute("DELETE FROM integration_checks WHERE provider='openai'")
    return {"saved":True,"provider":"openai","configured":bool(settings.effective("OPENAI_API_KEY"))}

class MetaConfig(BaseModel):
    access_token:str|None=Field(default=None,max_length=3000)
    app_secret:str|None=Field(default=None,max_length=300)
    verify_token:str|None=Field(default=None,max_length=300)
    ig_user_id:str=Field(min_length=4,max_length=35)
    graph_version:str=Field(default="v25.0",max_length=12)

@router.post("/api/integrations/meta")
def save_meta(data:MetaConfig,user=Depends(OWNER)):
    if not VALID_ID.fullmatch(data.ig_user_id):
        raise HTTPException(422,"Instagram User ID must be numeric")
    if not VALID_GRAPH.fullmatch(data.graph_version):
        raise HTTPException(422,"Graph API version must look like v25.0")
    out={"META_IG_USER_ID":data.ig_user_id,"META_GRAPH_VERSION":data.graph_version}
    for field,key in (("access_token","META_ACCESS_TOKEN"),("app_secret","META_APP_SECRET"),("verify_token","META_VERIFY_TOKEN")):
        val=getattr(data,field)
        if val is not None:
            val=val.strip()
            if val and (len(val)<12 or len(val)>3000):
                raise HTTPException(422,field+" is not long enough")
            out[key]=val
    try:
        write_batch(out,user["id"])
    except RuntimeError:
        raise HTTPException(409,"Vault encryption key not configured. Run updated installer.")
    with db.tx() as con:
        con.execute("DELETE FROM integration_checks WHERE provider='meta'")
    return {"saved":True,"provider":"meta","configured":settings.meta_ready()}

@router.post("/api/integrations/{provider}/disconnect")
def disconnect(provider:str,user=Depends(OWNER)):
    if provider not in ("openai","meta"):
        raise HTTPException(404,"Unknown integration provider")
    try:
        erase_provider(provider,user["id"])
    except RuntimeError:
        raise HTTPException(409,"Vault unavailable; disconnect the legacy environment secrets on the host.")
    with db.tx() as con:
        con.execute("DELETE FROM integration_checks WHERE provider=?",(provider,))
    return {"disconnected":True,"provider":provider,
            "note":"Any token still valid at its provider should be revoked there as well."}

def record_test(provider,ok,account=None):
    with db.tx() as con:
        con.execute(
            "INSERT INTO integration_checks(provider,status,account_label,checked_at) VALUES(?,?,?,?) "
            "ON CONFLICT(provider) DO UPDATE SET status=excluded.status,"
            "account_label=excluded.account_label,checked_at=excluded.checked_at",
            (provider,"ok" if ok else "failed",account,db.now()))
        db.audit(con,"connection-check","integration_test","integration_checks",provider,{"success":ok})

@router.post("/api/integrations/openai/test")
def check_openai(user=Depends(OWNER)):
    key=settings.effective("OPENAI_API_KEY")
    model=settings.effective("OPENAI_MODEL")
    if not key:raise HTTPException(409,"Enter an OpenAI API key first")
    if not VALID_MODEL.fullmatch(model):
        raise HTTPException(422,"Configured model ID is invalid")
    try:
        with httpx.Client(timeout=15,trust_env=False,follow_redirects=False) as client:
            resp=client.get("https://api.openai.com/v1/models/"+model,
                            headers={"Authorization":"Bearer "+key})
        ok=resp.status_code==200
        record_test("openai",ok,model if ok else None)
        if not ok:raise HTTPException(502,"OpenAI model access check failed (HTTP "+str(resp.status_code)+"). Check project key/model.")
        return {"ok":True,"provider":"openai","model":model}
    except httpx.RequestError:
        record_test("openai",False)
        raise HTTPException(502,"Could not reach OpenAI API")

@router.post("/api/integrations/meta/test")
def check_meta(user=Depends(OWNER)):
    access=settings.effective("META_ACCESS_TOKEN")
    ident=settings.effective("META_IG_USER_ID")
    version=settings.effective("META_GRAPH_VERSION")
    if not access or not ident or not VALID_GRAPH.fullmatch(version):
        raise HTTPException(409,"Save Meta access token, IG account ID and API version first")
    try:
        with httpx.Client(timeout=15,trust_env=False,follow_redirects=False) as client:
            resp=client.get(f"https://graph.instagram.com/{version}/me",
                params={"fields":"id,username,account_type"},headers={"Authorization":"Bearer "+access})
        if resp.status_code!=200:
            record_test("meta",False)
            raise HTTPException(502,"Meta account check failed (HTTP "+str(resp.status_code)+")")
        data=resp.json()
        username=str(data.get("username","")).lstrip("@").lower()
        account_id=str(data.get("id",""))
        ok=(username=="mehradkavir" and account_id==ident)
        record_test("meta",ok,"@mehradkavir" if ok else None)
        if not ok:
            raise HTTPException(409,"Token does not belong to @mehradkavir with the configured account ID")
        return {"ok":True,"provider":"meta","account":"@mehradkavir",
                "note":"Account token verified. Webhook subscriptions and advanced permissions must still be approved by Meta."}
    except httpx.RequestError:
        record_test("meta",False)
        raise HTTPException(502,"Could not reach Meta Instagram API")
