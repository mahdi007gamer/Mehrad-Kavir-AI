"""Governed Mehrad Kavir knowledge pack regression tests."""
from pathlib import Path
import json

import pytest
from fastapi.testclient import TestClient
from app import db, settings
from app.main import app
from app.brain import retrieve
from app.brand_knowledge import load_pack

@pytest.fixture()
def client(tmp_path,monkeypatch):
    for key,value in {
        "DB_PATH":str(tmp_path/"knowledge-pack.sqlite3"),
        "BOOTSTRAP_ADMIN_EMAIL":"owner@local.test",
        "BOOTSTRAP_ADMIN_PASSWORD":"only-for-tests-strong-owner-password-4321",
        "OPENAI_API_KEY":"",
        "META_APP_SECRET":"",
        "META_VERIFY_TOKEN":"",
        "META_ACCESS_TOKEN":"",
        "META_IG_USER_ID":"",
        "APP_ENV":"development",
        "COOKIE_SECURE":False
    }.items():
        monkeypatch.setattr(settings,key,value)
    with TestClient(app) as c:
        auth=c.post("/api/auth/login",json={
            "email":"owner@local.test",
            "password":"only-for-tests-strong-owner-password-4321"})
        assert auth.status_code==200,auth.text
        yield c,{"X-CSRF-Token":auth.json()["csrf"]}

def test_curated_catalog_complete_and_classified(client):
    c,_=client
    pack=load_pack()
    assert len(pack["documents"])>=40
    response=c.get("/api/knowledge")
    assert response.status_code==200
    docs=response.json()
    curated=[d for d in docs if d["seed_key"]]
    assert len(curated)==len(pack["documents"])
    assert sum(d["status"]=="approved" for d in curated)>=30
    assert sum(d["status"]=="pending" for d in curated)>=8
    assert all(d["version"]==1 and not d["edited_since_pack"] for d in curated)
    assert all(d["evidence_class"] for d in curated)
    assert all(d["source_type"].startswith("curated_") for d in curated)
    assert all(d["status"]=="pending" for d in curated
               if d["evidence_class"] in ("owner_claim_needs_proof","live_source_required"))
    categories={d["category"] for d in curated}
    assert {"brand","sales","engineering","faq","policy","content"}.issubset(categories)
    titles=" ".join(d["title"] for d in curated)
    assert "۲×۴" in titles and "۲×۵" in titles
    assert "فونداسیون" in titles and "گالوانیزه" in titles
    assert "حافظه" not in titles or len(titles)>100

def test_pending_marketing_claim_not_in_active_ai_context(client):
    c,_=client
    docs=c.get("/api/knowledge").json()
    candidate=next(x for x in docs if x["seed_key"]=="capacity-150mw")
    assert candidate["status"]=="pending"
    chosen,_=retrieve("ظرفیت پروژه ۱۵۰ مگاوات مهراد کویر","sales")
    assert candidate["id"] not in {doc["id"] for doc in chosen}
    after=next(x for x in docs if x["seed_key"]=="product-pv-700-40")
    assert after["status"]=="approved"
    chosen,_=retrieve("میز ۲×۴ پنل ۷۰۰ وات ارتفاع ۴۰ سانتی متر","engineering")
    assert after["id"] in {doc["id"] for doc in chosen}

def test_reinstall_preserves_owner_revision_and_review(client):
    c,csrf=client
    docs=c.get("/api/knowledge").json()
    original=next(d for d in docs if d["seed_key"]=="brand-visual")
    changed="رنگ آبی سازمانی #006FFE و فولادی #1E2B39 ثابت بماند. نسخه ویرایش‌شده توسط مدیر در پایگاه دانش حفظ شود."
    proposed=c.post(f"/api/knowledge/{original['id']}/revisions",
        headers=csrf,json={
            "base_version":original["version"],
            "title":"هویت بصری تأییدشده و نسخه اصلاحی",
            "body":changed,"category":"brand"})
    assert proposed.status_code==200,proposed.text
    accept=c.post(f"/api/knowledge/revisions/{proposed.json()['revision_id']}/review",
        headers=csrf,json={"decision":"approved"})
    assert accept.status_code==200,accept.text
    claim=next(d for d in docs if d["seed_key"]=="capacity-150mw")
    assert c.post(f"/api/knowledge/{claim['id']}/review",headers=csrf,
                  json={"decision":"rejected"}).status_code==200
    before_count=len(docs)
    db.init_db()
    updated=c.get("/api/knowledge").json()
    assert len(updated)==before_count
    revised=next(d for d in updated if d["id"]==original["id"])
    assert revised["body"]==changed
    assert revised["version"]==original["version"]+1
    assert revised["edited_since_pack"] is True
    assert next(d for d in updated if d["id"]==claim["id"])["status"]=="rejected"
    with db.read() as con:
        audits=con.execute("SELECT COUNT(*) FROM audit WHERE action='brand_knowledge_pack_installed'").fetchone()[0]
    assert audits==1

def test_knowledge_ui_filters_and_provenance(client):
    c,_=client
    html=c.get("/").text
    js=(Path(__file__).resolve().parents[1]/"app"/"static"/"app.js").read_text(encoding="utf-8")
    for identifier in ('id="knowledgeSearch"','id="knowledgeCategoryFilter"',
                       'id="knowledgeStatusFilter"','id="knowledgeStats"'):
        assert identifier in html
    assert "evidenceLabels" in js
    assert "edited_since_pack" in js
    assert "renderKnowledgeList" in js

def test_no_private_data_or_unverified_external_web_claim(client):
    pack=load_pack()
    text="\n".join(d["body"] for d in pack["documents"])
    assert "OPENAI_API_KEY=" not in text
    assert "VAULT_ENCRYPTION_KEY=" not in text
    assert "ارسال رایگان" in text  # Explicitly prohibited as an unsupported promise.
    assert "نیازمند بررسی" in text
    assert pack["provenance_note"].lower().find("could not be verified")>=0
