"""Meta Instagram Login API. Real sends are never attempted without credentials."""
import httpx
from . import settings

def send_reply(*, kind, recipient, body, reply_to):
    if not settings.meta_ready():
        raise RuntimeError("Meta integration is not configured")
    base = f"https://graph.instagram.com/{settings.META_GRAPH_VERSION}"
    if kind == "dm":
        url = f"{base}/{settings.META_IG_USER_ID}/messages"
        payload = {"recipient":{"id":recipient}, "message":{"text":body[:1000]}}
    elif kind == "comment":
        if not reply_to:
            raise RuntimeError("Comment identifier missing")
        url = f"{base}/{reply_to}/replies"
        payload = {"message":body[:1000]}
    else:
        raise RuntimeError("Unknown message kind")
    with httpx.Client(timeout=20) as client:
        r = client.post(url,json=payload,headers={"Authorization":f"Bearer {settings.META_ACCESS_TOKEN}"})
        r.raise_for_status()
        result = r.json()
    if not result.get("id") and not result.get("message_id"):
        raise RuntimeError("Meta did not confirm reply")
    return str(result.get("id") or result.get("message_id"))
