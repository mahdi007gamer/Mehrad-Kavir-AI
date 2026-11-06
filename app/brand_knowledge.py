"""Idempotent curated Mehrad Kavir knowledge pack.

Never re-writes existing documents, edits, approvals, or user-authored rules.
All external source content is still subject to the normal owner review flow.

The pack separates:
- facts the owner previously supplied;
- general non-design operating guidance;
- unverified marketing/technical claims requiring explicit owner review.
"""
import hashlib
import json
from pathlib import Path

from . import db

PACK_FILE=Path(__file__).resolve().parent/"data"/"mehrad_brand_pack.json"
ALLOWED_CATEGORIES={"brand","engineering","sales","faq","policy","content","other"}
ALLOWED_EVIDENCE={"owner_confirmed","operating_guideline","engineering_guidance",
                  "owner_claim_needs_proof","live_source_required"}

def checksum(title,category,body):
    payload=json.dumps([title,category,body],ensure_ascii=False,separators=(",",":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def load_pack():
    with PACK_FILE.open("r",encoding="utf-8") as f:
        pack=json.load(f)
    if not isinstance(pack.get("documents"),list) or len(pack["documents"])<15:
        raise ValueError("Brand knowledge pack is incomplete")
    seen=set()
    for d in pack["documents"]:
        if not isinstance(d,dict) or not isinstance(d.get("key"),str):
            raise ValueError("Malformed knowledge document")
        if d["key"] in seen:raise ValueError("Duplicate brand document ID")
        seen.add(d["key"])
        if d.get("category") not in ALLOWED_CATEGORIES:
            raise ValueError("Unsupported knowledge category")
        if d.get("status") not in ("approved","pending"):
            raise ValueError("Unsupported knowledge approval state")
        if d.get("evidence_class") not in ALLOWED_EVIDENCE:
            raise ValueError("Missing verified provenance classification")
        if not 4<=len(d.get("title",""))<=150 or not 20<=len(d.get("body",""))<=10000:
            raise ValueError("Invalid knowledge title/body length")
        if d.get("status")=="approved" and d.get("evidence_class") in (
            "owner_claim_needs_proof","live_source_required"):
            raise ValueError("Unverified evidence must never be seeded as approved")
    return pack

def apply_pack(con):
    """Call during DB initialization, in one transaction, after schema migration."""
    pack=load_pack()
    added=0
    for doc in pack["documents"]:
        existing=con.execute(
            "SELECT knowledge_id FROM brand_knowledge_pack_entries WHERE seed_key=?",
            (doc["key"],)).fetchone()
        if existing:
            # Preserve all owner edits, review decisions and versions on upgrade.
            continue
        source_type=("curated_owner_context" if doc["evidence_class"]=="owner_confirmed"
                     else "curated_guidance" if doc["status"]=="approved"
                     else "curated_review_required")
        cur=con.execute(
            "INSERT INTO knowledge(title,body,category,status,version,source_type,"
            "created_by,reviewed_by,created_at,reviewed_at) "
            "VALUES(?,?,?,?,1,?,NULL,NULL,?,?)",
            (doc["title"],doc["body"],doc["category"],doc["status"],source_type,
             db.now(),db.now() if doc["status"]=="approved" else None))
        con.execute(
            "INSERT INTO brand_knowledge_pack_entries "
            "(seed_key,knowledge_id,evidence_class,pack_version,source_fingerprint,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (doc["key"],cur.lastrowid,doc["evidence_class"],pack["version"],
             checksum(doc["title"],doc["category"],doc["body"]),db.now()))
        added+=1
    if added:
        db.audit(con,"system","brand_knowledge_pack_installed","knowledge",pack["version"],
                 {"added":added,"version":pack["version"]})
    return added
