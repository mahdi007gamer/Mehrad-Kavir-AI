"""Bounded, opt-in brand-source ingestion. NEVER auto-promotes unreviewed text."""
import hashlib
import ipaddress
import json
import re
import socket
from collections import deque
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

from . import db, settings

SITE = "https://mehradkavir.com/"
ALLOWED = {"mehradkavir.com","www.mehradkavir.com"}
USER_AGENT = "MehradKavirKnowledgeImporter/0.2 (+https://mehradkavir.com/)"
MAX_PAGES = 24
MAX_HTML = 850_000
MAX_BODY_CHARS = 14_000

def canonical_url(url):
    try:
        p = urlsplit(url)
        if p.scheme != "https" or (p.hostname or "").lower() not in ALLOWED:
            return None
        if p.username or p.password or p.port not in (None,443):
            return None
        if not p.path.startswith("/"):
            return None
        path = re.sub(r"/{2,}","/",p.path)
        if re.search(r"\.(?:png|jpg|jpeg|gif|webp|svg|pdf|zip|rar|mp4|avi|css|js|woff|ttf)$",path,re.I):
            return None
        if len(path)>180:
            return None
        return urlunsplit(("https",p.hostname.lower(),path,"",""))
    except ValueError:
        return None

def safe_dns():
    """Preflight deny local/private addresses; fixed-domain, no-redirect network policy."""
    for host in ALLOWED:
        infos=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
        for row in infos:
            addr=ipaddress.ip_address(row[4][0])
            if not addr.is_global:
                raise ValueError("Website DNS resolved to a non-public address")

class PageParser(HTMLParser):
    SKIP={"script","style","noscript","svg","footer","nav","form","header","iframe"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]
        self.title=[]
        self.heading=[]
        self.parts=[]
        self.links=[]
        self.in_title=0
        self.in_heading=0
    def handle_starttag(self,tag,attrs):
        tag=tag.lower()
        skip = (self.stack[-1][1] if self.stack else False) or tag in self.SKIP
        self.stack.append((tag,skip))
        if tag=="title" and not skip:self.in_title+=1
        if tag in ("h1","h2","h3") and not skip:self.in_heading+=1
        if tag=="a" and not skip:
            href=dict(attrs).get("href","")
            if href:self.links.append(href)
    def handle_endtag(self,tag):
        if tag=="title" and self.in_title:self.in_title-=1
        if tag in ("h1","h2","h3") and self.in_heading:self.in_heading-=1
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:
                self.stack=self.stack[:i]
                break
    def handle_data(self,data):
        if self.stack and self.stack[-1][1]:return
        content=" ".join(data.split())
        if len(content)<2:return
        if self.in_title:self.title.append(content)
        elif self.in_heading:
            self.heading.append(content)
            self.parts.append("\n## "+content+"\n")
        else:self.parts.append(content)

def download_page(client,url):
    r=client.get(url,headers={"User-Agent":USER_AGENT,"Accept":"text/html"})
    # Follow no redirects, explicit revalidation of the target host.
    if r.status_code in (301,302,303,307,308):
        target=canonical_url(urljoin(url,r.headers.get("location","")))
        if not target:raise ValueError("Redirect would leave allowlisted HTTPS hosts")
        r=client.get(target,headers={"User-Agent":USER_AGENT,"Accept":"text/html"})
    r.raise_for_status()
    if "text/html" not in r.headers.get("Content-Type","").lower():
        raise ValueError("Not an HTML page")
    if len(r.content)>MAX_HTML:
        raise ValueError("HTML page exceeds size limit")
    parser=PageParser()
    parser.feed(r.text[:MAX_HTML])
    title=" ".join(parser.title)[:200] or url
    body=" ".join(parser.parts)[:MAX_BODY_CHARS]
    return title,body,parser.links

def stage_document(job_id,provider,url,title,body):
    body=body.strip()[:MAX_BODY_CHARS]
    if len(body)<70:
        return False
    digest=hashlib.sha256(body.encode("utf8")).hexdigest()
    with db.tx() as con:
        cur=con.execute(
            "INSERT OR IGNORE INTO import_documents(job_id,provider,source_url,title,body,fingerprint,status,created_at) "
            "VALUES(?,?,?,?,?,?,'pending',?)",
            (job_id,provider,url,title[:180],body,digest,db.now()))
        return cur.rowcount==1

def website_import(job_id):
    safe_dns()
    robots=RobotFileParser()
    with httpx.Client(follow_redirects=False,timeout=httpx.Timeout(12,connect=5),trust_env=False) as client:
        # If robots.txt is inaccessible, do not assume the site permits automated crawling.
        rr=client.get(SITE+"robots.txt",headers={"User-Agent":USER_AGENT})
        if rr.status_code!=200:
            raise RuntimeError("robots.txt unavailable; import stopped for safety")
        robots.parse(rr.text.splitlines())
        queue=deque([SITE])
        seen=set()
        created=0
        while queue and len(seen)<MAX_PAGES:
            url=canonical_url(queue.popleft())
            if not url or url in seen:continue
            if not robots.can_fetch(USER_AGENT,url):continue
            seen.add(url)
            try:
                title,body,links=download_page(client,url)
                if stage_document(job_id,"website",url,title,body):created+=1
                for href in links[:140]:
                    new=canonical_url(urljoin(url,href))
                    if new and new not in seen and new not in queue:
                        queue.append(new)
            except (httpx.HTTPError,ValueError,UnicodeError):
                continue
        if not seen:
            raise RuntimeError("No permitted pages available to crawl")
        return created

def ig_fetch(path,params=None):
    if not settings.effective('META_ACCESS_TOKEN') or not settings.effective('META_IG_USER_ID'):
        raise RuntimeError("Meta access token or IG account ID missing")
    endpoint=f"https://graph.instagram.com/{settings.effective('META_GRAPH_VERSION')}/{path.lstrip('/')}"
    with httpx.Client(timeout=18,trust_env=False,follow_redirects=False) as client:
        r=client.get(endpoint,params=params or {},headers={
            "Authorization":"Bearer "+settings.effective('META_ACCESS_TOKEN'),
            "Accept":"application/json"})
    if r.status_code!=200:
        # Do not expose response body: it might include provider diagnostics or sensitive data.
        raise RuntimeError("Meta API error: HTTP "+str(r.status_code))
    return r.json()

def instagram_media_import(job_id):
    items=ig_fetch(f"{settings.effective('META_IG_USER_ID')}/media",{
        "fields":"id,caption,permalink,media_type,timestamp",
        "limit":50
    }).get("data",[])[:50]
    saved=0
    for item in items:
        media_id=str(item.get("id",""))[:80]
        permalink=str(item.get("permalink",""))[:500]
        caption=str(item.get("caption") or "")[:MAX_BODY_CHARS]
        if not media_id:continue
        with db.tx() as con:
            con.execute(
                "INSERT INTO instagram_media(media_id,permalink,caption,media_type,timestamp,last_synced_at) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(media_id) DO UPDATE SET "
                "caption=excluded.caption,permalink=excluded.permalink,media_type=excluded.media_type,"
                "timestamp=excluded.timestamp,last_synced_at=excluded.last_synced_at",
                (media_id,permalink,caption,str(item.get("media_type",""))[:35],
                 str(item.get("timestamp",""))[:40],db.now()))
        if caption:
            if stage_document(job_id,"instagram",permalink or "instagram:media:"+media_id,
                              "پست اینستاگرام مهراد کویر "+media_id,caption):
                saved+=1
    return saved

def metric_values(data):
    for result in data.get("data",[])[:10]:
        name=str(result.get("name",""))[:80]
        value=result.get("total_value",{}).get("value") if isinstance(result.get("total_value"),dict) else None
        if value is None:
            values=result.get("values",[])
            if values:
                value=values[-1].get("value")
        if isinstance(value,(int,float)) and not isinstance(value,bool):
            yield name,float(value)

def instagram_insights_import(job_id):
    count=0
    with db.read() as con:
        media=[dict(x) for x in con.execute(
            "SELECT media_id,media_type FROM instagram_media ORDER BY timestamp DESC LIMIT 12").fetchall()]
    wanted=[("account",settings.effective('META_IG_USER_ID'),["views","reach","profile_views"],"day")]
    for item in media:
        wanted.append(("media",item["media_id"],["views","reach","saved","shares"],"lifetime"))
    for kind,identifier,metrics,period in wanted:
        for metric in metrics:
            try:
                payload=ig_fetch(f"{identifier}/insights",{"metric":metric,"period":period})
                matches=list(metric_values(payload))
                value=next((v for k,v in matches if k==metric),None)
                available=value is not None
            except (httpx.HTTPError,RuntimeError,ValueError,TypeError):
                value,available=None,False
            with db.tx() as con:
                con.execute(
                    "INSERT INTO instagram_metrics(entity_type,entity_id,name,period,value,state,source,observed_at) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (kind,identifier,metric,period,value,
                     "available" if available else "unavailable","Meta Instagram API",db.now()))
            if available:count+=1
    return count

def run_import_job(job_id,provider):
    if provider=="website":return website_import(job_id)
    if provider=="instagram_media":return instagram_media_import(job_id)
    if provider=="instagram_insights":return instagram_insights_import(job_id)
    raise ValueError("Unsupported provider")
