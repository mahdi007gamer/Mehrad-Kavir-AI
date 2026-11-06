/* Mehrad Kavir AI — dependency-free admin client. All user data escaped. */
(() => {
  "use strict";
  let csrf = "", user = null, activePage = "dashboard", selectedThread = null, lastScenario = "";
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));
  const e = (v) => String(v ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const statusText = { pending:"در انتظار تأیید", approved:"تأییدشده", rejected:"ردشده", sent:"ارسال‌شده", sending:"در حال ارسال", failed:"نیازمند بررسی", low:"کم‌خطر", medium:"متوسط", high:"حساس" };
  const fmt = (v) => { try { return new Intl.DateTimeFormat("fa-IR", {dateStyle:"short",timeStyle:"short"}).format(new Date(v)); } catch { return v || "—"; } };
  const txt = (s, value) => { const el = $(s); if (el) el.textContent = value; };
  const feedEmpty = (msg) => '<div class="empty">' + e(msg) + '</div>';
  const encode = (o) => JSON.stringify(o);
  const getForm = (form) => Object.fromEntries(new FormData(form).entries());
  function notify(msg, isError = false) {
    const f = $("#flash"); f.textContent = msg; f.classList.toggle("err", isError); f.classList.remove("hidden");
    clearTimeout(notify.timeout); notify.timeout = setTimeout(() => f.classList.add("hidden"), 5500);
  }
  async function api(path, {method="GET", body}={}) {
    const headers = {"Accept":"application/json"};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (method !== "GET") headers["X-CSRF-Token"] = csrf;
    const res = await fetch(path, {method,headers,credentials:"same-origin",body:body === undefined ? undefined : encode(body)});
    let payload;
    try { payload = await res.json(); } catch { payload = {}; }
    if (res.status === 401 && path !== "/api/auth/login") showLogin();
    if (!res.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "خطای ارتباط با سرور (" + res.status + ")");
    return payload;
  }
  function showLogin() { $("#appShell").classList.add("hidden"); $("#loginView").classList.remove("hidden"); }
  function showApp() { $("#loginView").classList.add("hidden"); $("#appShell").classList.remove("hidden"); }
  async function bootstrap() {
    try {
      const data = await api("/api/me");
      csrf = data.csrf; user = data.user; txt("#userEmail", user.email); txt("#userRole", {owner:"مالک سیستم",editor:"کارشناس",viewer:"مشاهده‌گر"}[user.role] || user.role);
      showApp(); await refreshCurrent();
    } catch { showLogin(); }
  }
  async function login(form) {
    const btn = form.querySelector("button"); btn.disabled = true; txt("#loginError","");
    try {
      const data = await api("/api/auth/login",{method:"POST",body:{email:$("#loginEmail").value,password:$("#loginPassword").value}});
      csrf=data.csrf; user=data.user; $("#loginPassword").value=""; txt("#userEmail",user.email);
      txt("#userRole",{owner:"مالک سیستم",editor:"کارشناس",viewer:"مشاهده‌گر"}[user.role]||user.role);
      showApp(); await refreshCurrent();
    } catch (err) { txt("#loginError",err.message); } finally {btn.disabled=false;}
  }
  function go(page) {
    if (!$("#page-"+page)) return;
    activePage=page;
    $$(".page").forEach(x=>x.classList.toggle("active",x.id==="page-"+page));
    $$(".nav-link").forEach(x=>x.classList.toggle("active",x.dataset.page===page));
    txt("#currentPageName", ({dashboard:"نمای کلی",inbox:"صندوق پیام",insights:"تحلیل پیج",crm:"مدیریت استعلام‌ها",phone:"منشی تلفنی",automation:"پاسخ‌های خودکار",knowledge:"دانش برند",memory:"حافظه و یادگیری",content:"استودیو محتوا",security:"امنیت و اتصالات"})[page]);
    window.scrollTo({top:0,behavior:"smooth"});
    refreshCurrent();
  }
  async function refreshCurrent() {
    try {
      if (activePage === "dashboard") await dashboard();
      else if (activePage === "inbox") await inbox();
      else if (activePage === "insights") await insights();
      else if (activePage === "crm") await crm();
      else if (activePage === "phone") await phone();
      else if (activePage === "automation") await automation();
      else if (activePage === "knowledge") await knowledge();
      else if (activePage === "memory") await rules();
      else if (activePage === "content") await scenarios();
      else if (activePage === "security") await security();
    } catch (err) {notify(err.message,true);}
  }
  async function dashboard() {
    const d=await api("/api/dashboard");
    txt("#statThreads",d.threads); txt("#statDrafts",d.pending_drafts); txt("#statKnowledge",d.approved_knowledge);
    txt("#statScenarios",d.scenarios); txt("#navPending",d.pending_drafts);
    txt("#aiHealth",d.integration.openai?"متصل به مدل":"حالت قالب آزمایشی");
    txt("#metaHealth",d.integration.meta?"تنظیم شده":"نیازمند اتصال");
    $("#aiBadge").classList.toggle("online",d.integration.openai);
    $("#metaBadge").classList.toggle("online",d.integration.meta);
    const names={bootstrap:"راه‌اندازی مدیر سیستم",login:"ورود مدیر",message_received:"دریافت پیام",draft_created:"ساخت پیش‌نویس",
      knowledge_proposed:"پیشنهاد سند",knowledge_approved:"تأیید دانش",rule_proposed:"پیشنهاد قانون",rule_approved:"تأیید قانون",
      scenario_generated:"تولید سناریو",draft_approved:"تأیید پاسخ",send_confirmed:"ثبت ارسال موفق",send_failed:"خطای ارسال"};
    $("#activityFeed").innerHTML=d.latest_audit.length?d.latest_audit.map(x=>'<div class="activity"><div class="circle">◎</div><div class="details"><b>'+e(names[x.action]||x.action)+'</b><small>'+e(x.entity)+'</small></div><small class="subtle">'+e(fmt(x.created_at))+'</small></div>').join(""):feedEmpty("هنوز رویدادی ثبت نشده است.");
  }
  function chip(label,kind="") {return '<span class="chip '+e(kind)+'">'+e(label)+'</span>';}
  async function insights() {
    const data=await api("/api/analytics");
    const metrics=data.latest_metrics||[];
    const account=(metric)=>{
      const row=metrics.find(x=>x.entity_type==="account"&&x.name===metric&&x.state==="available");
      return row?new Intl.NumberFormat("fa-IR").format(row.value):"—";
    };
    txt("#igViews",account("views"));
    txt("#igReach",account("reach"));
    txt("#igEngagement","—"); // Not computable without compatible engagement and reach observations.
    const leads=data.leads_by_stage||{};
    const qualified=Object.entries(leads).filter(([stage])=>["qualified","engineering","quotation","won"].includes(stage)).reduce((n,[,value])=>n+Number(value||0),0);
    txt("#igQualifiedLeads",new Intl.NumberFormat("fa-IR").format(qualified));
    const observed=metrics.filter(x=>x.state==="available");
    txt("#insightsStatus", observed.length?
      ("داده‌های معتبر دریافت شده: "+observed.length+" شاخص. آخرین Snapshot: "+fmt(observed[0].observed_at)+". منبع: Meta Instagram API") :
      "هنوز آمار معتبر از Meta Instagram API ثبت نشده است. از «دانش برند» فهرست پست‌ها و سپس دریافت Insights را اجرا کنید.");
    $("#igMediaList").innerHTML=data.media.length?data.media.map(x=>{
      const observations=metrics.filter(m=>m.entity_type==="media"&&m.entity_id===x.media_id&&m.state==="available");
      const view=observations.find(m=>m.name==="views");
      return '<div class="record"><div class="record-head"><h4>'+e(x.media_type||"Post")+'</h4>'+
        chip(view?"Views: "+view.value:"بدون آمار معتبر")+'</div><p>'+e((x.caption||"بدون کپشن").slice(0,380))+'</p>'+
        '<small>'+e(fmt(x.timestamp))+' · آخرین دریافت: '+e(fmt(x.last_synced_at))+'</small>'+
        (x.permalink?'<p><a href="'+e(x.permalink)+'" target="_blank" rel="noopener noreferrer">مشاهده رسانه در اینستاگرام</a></p>':"")+
        '</div>';
    }).join(""):feedEmpty("هنوز پست و ریلزی از Meta دریافت نشده است.");
  }

  const leadStages={new:"جدید",qualifying:"تکمیل مشخصات",qualified:"واجد شرایط",engineering:"بررسی فنی",quotation:"پیش‌فاکتور",won:"موفق",lost:"ناموفق"};
  async function crm(){
    const entries=await api("/api/leads");
    $("#leadsList").innerHTML=entries.length?entries.map(x=>
      '<div class="record"><div class="record-head"><h4>'+e(x.name)+'</h4>'+chip(leadStages[x.stage]||x.stage)+'</div>'+
      '<small>'+e(x.project_city||"مکان مشخص نشده")+' · '+e(x.capacity_mw===null?"ظرفیت نامعلوم":x.capacity_mw+" مگاوات")+
      ' · '+e(fmt(x.updated_at))+'</small><p>'+e(x.details||"نیازمند تکمیل مشخصات")+'</p>'+
      '<label>مرحله پیگیری</label><select data-lead-stage="'+Number(x.id)+'">'+
      Object.entries(leadStages).map(([key,label])=>'<option value="'+key+'"'+(key===x.stage?" selected":"")+'>'+e(label)+'</option>').join("")+
      '</select></div>').join(""):feedEmpty("هنوز استعلامی ثبت نشده است.");
  }

  async function automation(){
    const [state,policies]=await Promise.all([api("/api/automation/status"),api("/api/automation/policies")]);
    txt("#autoPolicyStatus",state.server_enabled?
      (state.meta_ready?"کلید فعال‌سازی سرور روشن است؛ قوانین محدود می‌توانند بررسی شوند.":"کلید سرور روشن است، اما Meta هنوز آماده نیست."):
      "کلید توقف سرور فعال است؛ AUTO_REPLY_ENABLED=false. هیچ پاسخ خودکاری ارسال نمی‌شود.");
    $("#autoPoliciesList").innerHTML=policies.length?policies.map(x=>
      '<div class="record"><div class="record-head"><h4>'+e(x.keyword)+'</h4>'+chip(x.enabled?"فعال":"خاموش",x.enabled?"success":"")+'</div>'+
      '<p>'+e(x.template)+'</p><button class="btn small '+(x.enabled?"danger":"ghost")+
      '" data-toggle-policy="'+Number(x.id)+':'+(x.enabled?"false":"true")+'">'+(x.enabled?"غیرفعال کردن":"فعال‌کردن")+
      '</button></div>').join(""):feedEmpty("قانونی تعریف نشده است.");
  }

  async function inbox() {
    const threads=await api("/api/threads");
    const list=$("#threadsList");
    list.innerHTML=threads.length?threads.map(t=>'<button class="thread-item '+(selectedThread===t.id?"selected":"")+'" data-thread="'+Number(t.id)+'"><span class="thread-icon">'+(t.kind==="dm"?"✉":"☷")+'</span><span class="thread-label"><b>'+e(t.label)+'</b><small>'+e(t.platform)+" · "+e(t.kind)+" · "+e(fmt(t.last_received_at))+'</small></span>'+(t.pending_count?'<em>'+Number(t.pending_count)+'</em>':"")+'</button>').join(""):feedEmpty("هنوز گفتگویی ثبت نشده. از شبیه‌ساز پایین استفاده کنید.");
    if (threads.length && (!selectedThread || !threads.find(x=>x.id===selectedThread))) selectedThread=threads[0].id;
    if (selectedThread) await loadThread(selectedThread);
  }
  async function loadThread(id) {
    selectedThread=id;
    const data=await api("/api/threads/"+id);
    txt("#threadTitle",data.thread.label);
    txt("#threadKind",data.thread.platform+" / "+(data.thread.kind==="dm"?"دایرکت":"کامنت"));
    $$(".thread-item").forEach(x=>x.classList.toggle("selected",Number(x.dataset.thread)===id));
    const holder=$("#conversationMessages");
    holder.innerHTML=data.messages.map(m=>{
      const parts=['<div class="message '+(m.direction==="out"?"outgoing":"")+'">'+e(m.body)+'<small>'+e(fmt(m.received_at))+'</small></div>'];
      if (m.draft_id) {
        const canReview=(m.draft_state==="pending"||m.draft_state==="failed") && user.role!=="viewer";
        parts.push('<div class="draft"><div class="draft-head"><b>✦ پیشنهاد '+e(m.specialty)+'</b>'+chip(statusText[m.draft_state]||m.draft_state,m.draft_state==="pending"?"warning":m.draft_state==="sent"?"success":"")+'</div><div class="subtle">ریسک: '+e(statusText[m.risk]||m.risk)+' · منبع: '+e(m.generated_by)+'</div>');
        if (canReview) parts.push('<textarea id="draft-text-'+Number(m.draft_id)+'" maxlength="1800">'+e(m.draft_text)+'</textarea><div class="draft-actions"><button class="btn primary small" data-approve="'+Number(m.draft_id)+'">تأیید پاسخ</button><button class="btn danger small" data-reject="'+Number(m.draft_id)+'">رد پاسخ</button></div>');
        else parts.push('<p>'+e(m.draft_text)+'</p>');
        if(data.thread.platform==="demo")parts.push('<small class="subtle">آزمایشی: پیام واقعی ارسال نخواهد شد.</small>');
        parts.push('</div>');
      } else if (m.status==="new"||m.status==="processing") parts.push('<div class="micro">در صف پردازش AI…</div>');
      return parts.join("");
    }).join("") || feedEmpty("گفتگو خالی است.");
    holder.scrollTop=holder.scrollHeight;
  }
  async function actDraft(id,action) {
    if (action==="approve") {
      const input=$("#draft-text-"+id);
      if (!input?.value.trim()) return notify("پاسخ خالی است",true);
      if (!window.confirm("پاسخ را تأیید می‌کنید؟ برای پیام زنده، پس از تأیید تلاش برای ارسال انجام می‌شود.")) return;
      const result=await api("/api/drafts/"+id+"/approve",{method:"POST",body:{text:input.value}});
      notify(result.state==="sent"?"ارسال توسط Meta تأیید شد":"پیش‌نویس آزمایشی تأیید شد؛ ارسال خارجی انجام نشد");
    } else {
      await api("/api/drafts/"+id+"/reject",{method:"POST"});
      notify("پاسخ رد شد.");
    }
    await loadThread(selectedThread);
  }
  const knowledgeCategoryLabels={
    brand:"هویت برند",engineering:"مهندسی/محصول",sales:"فروش/استعلام",
    faq:"سؤالات متداول",policy:"سیاست و امنیت",content:"محتوا",other:"سایر"
  };
  const evidenceLabels={
    owner_confirmed:"اطلاعات اعلام‌شده توسط مدیر",
    operating_guideline:"راهنمای عملیاتی",
    engineering_guidance:"راهنمای عمومی فنی؛ نه طراحی نهایی",
    owner_claim_needs_proof:"ادعای نیازمند سند و بررسی مدیر",
    live_source_required:"نیازمند منبع زنده و قابل‌تأیید"
  };
  function record(obj,type) {
    const title=e(obj.title),textBody=String(type==="rule"?obj.instruction:obj.body);
    const state=obj.status;
    const button=(state==="pending"&&user?.role==="owner")?
      '<div class="record-actions"><button class="btn small primary" data-review="'+type+':'+Number(obj.id)+':approved">تأیید</button><button class="btn small danger" data-review="'+type+':'+Number(obj.id)+':rejected">رد</button></div>':
      (type==="knowledge"&&state==="approved"?
       '<div class="record-actions"><button class="btn small ghost" data-edit-knowledge="'+Number(obj.id)+'">ویرایش سند / نسخه '+Number(obj.version||1)+'</button></div>':"");
    if(type!=="knowledge")
      return '<div class="record"><div class="record-head"><h4>'+title+'</h4>'+
        chip(statusText[state]||state,state==="approved"?"success":state==="pending"?"warning":"danger")+
        '</div><p>'+e(textBody)+'</p><small>'+e(obj.scope)+' · '+e(fmt(obj.created_at))+'</small>'+button+'</div>';
    const origin=obj.evidence_class?e(evidenceLabels[obj.evidence_class]||obj.evidence_class):
      obj.source_type==="manual"?"سند ثبت‌شده دستی":
      obj.source_type==="website"?"سایت / پس از تأیید مدیر":
      obj.source_type==="instagram"?"اینستاگرام / پس از تأیید مدیر":"سند اولیه سیستم";
    const label=e(knowledgeCategoryLabels[obj.category]||obj.category);
    const preview=textBody.length>325?
      '<p>'+e(textBody.slice(0,325))+'…</p><details class="knowledge-expand"><summary>مشاهده متن کامل سند</summary><p>'+e(textBody)+'</p></details>':
      '<p>'+e(textBody)+'</p>';
    const edited=obj.edited_since_pack?
      '<small class="knowledge-edited">نسخه اولیه توسط مدیر ویرایش شده</small>':"";
    return '<div class="record knowledge-record"><div class="record-head"><h4>'+title+'</h4>'+
      chip(statusText[state]||state,state==="approved"?"success":state==="pending"?"warning":"danger")+
      '</div><div class="knowledge-tags"><small>'+label+'</small><small>'+origin+'</small>'+
      (obj.seed_key?'<small>بسته دانش '+e(obj.pack_version||"")+'</small>':"")+'</div>'+
      preview+'<small>نسخه '+Number(obj.version||1)+' · '+e(fmt(obj.created_at))+'</small>'+
      edited+button+'</div>';
  }
  function renderKnowledgeList() {
    const items=window.__knowledgeItems||[];
    const q=String($("#knowledgeSearch")?.value||"").trim().toLowerCase().replaceAll("ي","ی").replaceAll("ك","ک");
    const category=$("#knowledgeCategoryFilter")?.value||"all";
    const status=$("#knowledgeStatusFilter")?.value||"all";
    const shown=items.filter(d=>
      (category==="all"||d.category===category)&&
      (status==="all"||d.status===status)&&
      (!q||(d.title+" "+d.body+" "+(knowledgeCategoryLabels[d.category]||"")).toLowerCase().replaceAll("ي","ی").replaceAll("ك","ک").includes(q))
    );
    txt("#knowledgeCount",shown.length+" از "+items.length+" سند");
    const approved=items.filter(d=>d.status==="approved").length;
    const pending=items.filter(d=>d.status==="pending").length;
    const edits=items.filter(d=>d.edited_since_pack).length;
    $("#knowledgeStats").innerHTML=
      '<span class="knowledge-stat"><strong>'+approved+'</strong> تأییدشده</span>'+
      '<span class="knowledge-stat"><strong>'+pending+'</strong> نیازمند بررسی</span>'+
      '<span class="knowledge-stat"><strong>'+edits+'</strong> ویرایش‌شده</span>';
    $("#knowledgeList").innerHTML=shown.length?
      shown.map(x=>record(x,"knowledge")).join(""):
      feedEmpty("سندی با این فیلتر پیدا نشد. موضوع یا وضعیت را تغییر دهید.");
  }
  async function knowledge() {
    const items=await api("/api/knowledge");
    window.__knowledgeCache=Object.fromEntries(items.map(x=>[x.id,x]));
    window.__knowledgeItems=items;
    renderKnowledgeList();
    await refreshImports();
  }

  async function refreshImports() {
    try {
      const [jobs,docs]=await Promise.all([api("/api/import/jobs"),api("/api/import/documents")]);
      $("#importJobList").innerHTML=jobs.length?jobs.map(x=>
        '<div class="record"><div class="record-head"><h4>'+e(x.provider)+'</h4>'+
        chip(x.state,x.state==="completed"?"success":x.state==="failed"?"danger":"warning")+
        '</div><small>'+e(fmt(x.created_at))+' · موارد دریافت‌شده: '+Number(x.processed)+'</small>'+
        (x.error?'<p>'+e(x.error)+'</p>':"")+'</div>').join(""):feedEmpty("هنوز واردسازی شروع نشده.");
      $("#stagedDocs").innerHTML=docs.length?docs.map(x=>
        '<div class="record"><div class="record-head"><h4>'+e(x.title)+'</h4>'+
        chip(statusText[x.status]||x.status,x.status==="approved"?"success":x.status==="pending"?"warning":"")+
        '</div><small>'+e(x.provider)+" · "+e(x.source_url)+'</small><p>'+e(x.body.slice(0,1100))+
        (x.body.length>1100?"...":"")+'</p>'+
        (x.status==="pending"&&user.role==="owner"?
          '<div class="record-actions"><button class="btn primary small" data-review-import="'+Number(x.id)+':approved">تأیید ورود به حافظه</button>'+
          '<button class="btn danger small" data-review-import="'+Number(x.id)+':rejected">رد</button></div>':"")+
        '</div>').join(""):feedEmpty("موردی در صف بررسی نیست.");
    } catch(err) {notify(err.message,true);}
  }

  async function showKnowledgeEditor(id) {
    const doc=window.__knowledgeCache?.[id];
    if(!doc)return notify("سند انتخاب‌شده موجود نیست",true);
    const form=$("#knowledgeEditForm");
    for(const name of ["id","base_version","title","category","body"]){
      const v=name==="id"?id:name==="base_version"?doc.version:doc[name];
      form.elements.namedItem(name).value=v;
    }
    await loadKnowledgeHistory(id);
    form.scrollIntoView({behavior:"smooth",block:"center"});
  }

  async function loadKnowledgeHistory(id) {
    const result=await api("/api/knowledge/"+id+"/history");
    $("#revisionList").innerHTML=result.revisions.length?
      result.revisions.map(r=>
        '<div class="record"><div class="record-head"><h4>نسخه پیشنهادی '+(Number(r.base_version)+1)+'</h4>'+
        chip(statusText[r.status]||r.status,r.status==="approved"?"success":r.status==="pending"?"warning":"")+
        '</div><small>'+e(fmt(r.created_at))+'</small><p>'+e(r.title)+': '+e(r.body.slice(0,400))+'</p>'+
        (r.status==="pending"&&user.role==="owner"?
          '<div class="record-actions"><button class="btn primary small" data-review-revision="'+Number(r.id)+':approved">تأیید اصلاح</button>'+
          '<button class="btn danger small" data-review-revision="'+Number(r.id)+':rejected">رد اصلاح</button></div>':"")+
        '</div>').join(""):feedEmpty("هنوز ویرایشی ثبت نشده.");
  }

  async function rules() {
    const items=await api("/api/rules");
    txt("#rulesCount",items.length+" قانون");
    $("#rulesList").innerHTML=items.length?items.map(x=>record(x,"rule")).join(""):feedEmpty("هنوز بازخوردی ثبت نشده.");
  }
  async function review(kind,id,decision) {
    if(!window.confirm((decision==="approved"?"تأیید":"رد")+" این مورد قطعی شود؟"))return;
    await api("/api/"+(kind==="rule"?"rules":"knowledge")+"/"+id+"/review",{method:"POST",body:{decision}});
    notify("وضعیت با موفقیت به‌روز شد.");
    await refreshCurrent();
  }
  async function scenarios() {
    const rows=await api("/api/scenarios");
    $("#scenarioList").innerHTML=rows.length?rows.map(x=>'<button class="record scenario-entry" data-scenario="'+Number(x.id)+'"><div class="record-head"><h4>'+e(x.topic)+'</h4>'+chip(x.generated_by==="openai"?"AI":"قالب")+'</div><small>'+e(x.audience)+" · "+e(fmt(x.created_at))+'</small></button>').join(""):feedEmpty("سناریویی هنوز ثبت نشده است.");
    window.__scenarioCache=Object.fromEntries(rows.map(x=>[x.id,x.body]));
  }
  async function security() {
    const d=await api("/api/integrations");
    const statuses=[
      ["OpenAI Responses API","مدل: "+(d.openai.fields.OPENAI_MODEL.value||"تنظیم نشده"),d.openai],
      ["Meta Instagram API","حساب: @mehradkavir",d.meta]
    ];
    $("#integrationCards").innerHTML=statuses.map(x=>{
      const xStatus=x[2].verified?"اتصال آزمایش‌شده":x[2].configured?"تنظیم‌شده، نیازمند تست":"تنظیم نشده";
      return '<div class="integration-card"><span>◉</span><div><b>'+e(x[0])+'</b><small>'+e(x[1])+'</small></div><em>'+e(xStatus)+'</em></div>';
    }).join("");
    const vault=$("#vaultStatus");
    vault.textContent=d.vault_ready?
      "صندوق امن فعال است: کلیدهای شما فقط به‌صورت رمزگذاری‌شده ذخیره می‌شوند. مقدار موجود پس از ذخیره قابل مشاهده نیست.":
      "صندوق رمزنگاری هنوز راه‌اندازی نشده است. فایل نصب جدید START-WINDOWS.bat را اجرا کنید.";
    vault.classList.toggle("err",!d.vault_ready);
    const openai=$("#openaiConnectForm");
    const meta=$("#metaConnectForm");
    const model=d.openai.fields.OPENAI_MODEL?.value || "gpt-5-mini";
    if(!openai.querySelector("[name=model]").matches(":focus"))
      openai.querySelector("[name=model]").value=model;
    const confId=d.meta.fields.META_IG_USER_ID?.value || "";
    if(!meta.querySelector("[name=ig_user_id]").matches(":focus"))
      meta.querySelector("[name=ig_user_id]").value=confId;
    if(!meta.querySelector("[name=graph_version]").matches(":focus"))
      meta.querySelector("[name=graph_version]").value=d.meta.fields.META_GRAPH_VERSION?.value || "v25.0";
    for(const [form,fields] of [[openai,["api_key"]],[meta,["access_token","app_secret","verify_token"]]]){
      for(const name of fields){
        const el=form.querySelector('[name="'+name+'"]');
        const key=({"api_key":"OPENAI_API_KEY","access_token":"META_ACCESS_TOKEN",
                    "app_secret":"META_APP_SECRET","verify_token":"META_VERIFY_TOKEN"})[name];
        const configured=name==="api_key"?d.openai.fields[key]?.configured:d.meta.fields[key]?.configured;
        el.placeholder=configured?"قبلاً ثبت شده؛ برای حفظ مقدار خالی بگذارید":"مقدار جدید را اینجا وارد کنید";
      }
    }
    $("#metaWebhookUrl").value=window.location.origin+"/webhooks/instagram";
    txt("#openaiTestResult",d.openai.last_test?
      ("آخرین تست: "+(d.openai.last_test.status==="ok"?"موفق":"ناموفق")+" • "+fmt(d.openai.last_test.checked_at)):"هنوز آزمایش نشده");
    txt("#metaTestResult",d.meta.last_test?
      ("آخرین تست حساب: "+(d.meta.last_test.status==="ok"?"موفق":"ناموفق")+" • "+fmt(d.meta.last_test.checked_at)):"حساب هنوز آزمایش نشده");
    await loadUpdates();
    await loadProviders();
    const audit=await api("/api/audit");
    $("#auditRecords").innerHTML=audit.length?audit.map(x=>'<div class="record"><div class="record-head"><h4>'+e(x.action)+'</h4><small>'+e(fmt(x.created_at))+'</small></div><small>'+e(x.actor)+" · "+e(x.entity)+" #"+e(x.entity_id)+'</small></div>').join(""):feedEmpty("لاگی ثبت نشده است.");
  }

  async function loadUpdates() {
    const status=$("#updateStatus"), button=$("#updateApproveBtn");
    button.disabled=true;button.dataset.sha="";
    try {
      const r=await api("/api/updates/status");
      const short=s=>s&&s!=="unknown"?s.slice(0,10):"نامشخص";
      const state=r.request?.state||"";
      status.textContent="نسخه نصب‌شده: "+short(r.installed_sha)+" | آخرین نسخه رسمی: "+short(r.latest_sha)+
        (r.installed_known?(r.available?" | نسخه جدید موجود است.":" | نسخه نصب‌شده به‌روز است."):" | یک‌بار نصب‌کننده را اجرا کنید تا نسخه ثبت شود.")+
        (state?" | آخرین درخواست: "+state:"");
      if(r.available && r.installed_known && !["approved","applying"].includes(state)){
        button.disabled=false;button.dataset.sha=r.latest_sha;
      }
    }catch(err){status.textContent="دریافت نسخه GitHub ناموفق بود؛ اتصال اینترنت یا GitHub را بررسی کنید.";button.disabled=true;}
  }

  function setFormValue(form,name,value) {
    const el=form?.elements?.namedItem(name);
    if(el && !el.matches(":focus") && value!==null && value!==undefined)
      el.value=value;
  }
  async function loadProviders(){
    const d=await api("/api/providers");
    const g=$("#geminiConnectForm"),t=$("#telephonyConnectForm");
    for(const [key,name] of Object.entries({
      GEMINI_MODEL:"text_model",GEMINI_LIVE_MODEL:"live_model",
      GEMINI_TTS_MODEL:"tts_model",GEMINI_VOICE:"voice"}))
      setFormValue(g,name,d.gemini.fields[key]?.value);
    g.elements.namedItem("api_key").placeholder=
      d.gemini.fields.GEMINI_API_KEY?.configured?"کلید ثبت شده؛ برای حفظ خالی بگذارید":"Google AI Studio API Key";
    for(const [key,name] of Object.entries({
      TWILIO_ACCOUNT_SID:"account_sid",PHONE_PUBLIC_BASE_URL:"public_base_url"}))
      setFormValue(t,name,d.telephony.fields[key]?.value);
    t.elements.namedItem("enabled").checked=d.telephony.enabled;
    t.elements.namedItem("auth_token").placeholder=
      d.telephony.fields.TWILIO_AUTH_TOKEN?.configured?"توکن قبلاً ثبت شده؛ برای حفظ خالی بگذارید":"Twilio Auth Token";
    $("#aiProviderSelect").value=d.selected;
    $("#geminiTestResult").textContent=d.gemini.test?
      ("آخرین تست Google AI: "+(d.gemini.test.status==="ok"?"موفق":"ناموفق")+" · "+fmt(d.gemini.test.checked_at)):
      "Google Gemini هنوز تست نشده است.";
    $("#telephonyTestResult").textContent=d.telephony.test?
      ("آخرین تست حساب Twilio: "+(d.telephony.test.status==="ok"?"موفق":"ناموفق")+
       " · "+fmt(d.telephony.test.checked_at)+"؛ آزمایش شماره و تماس واقعی همچنان لازم است."):
      "حساب Twilio هنوز تست نشده است؛ برای تماس واقعی شماره و HTTPS/WSS نیز لازم است.";
  }

  async function phone(){
    const [calls,providers]=await Promise.all([api("/api/voice/calls"),api("/api/providers")]);
    const ready=providers.gemini.text_ready&&providers.telephony.ready&&providers.telephony.enabled;
    txt("#phoneStatus",ready?
      "تنظیمات دریافت تماس فعال است؛ برای مکالمه واقعی باید شماره Twilio، Webhook عمومی و مدل Gemini Live را عملیاتی تست کنید.":
      "این قابلیت فعلاً پذیرای تماس واقعی نیست. ابتدا کلید Google AI و تنظیمات Twilio را در بخش امنیت و اتصالات وارد کنید.");
    $("#phoneCallsList").innerHTML=calls.length?calls.map(x=>
      '<div class="record"><div class="record-head"><h4>تماس #'+Number(x.id)+'</h4>'+
       chip(x.status,x.status==="ended"?"success":x.status==="failed"?"danger":"warning")+'</div>'+
       '<small>'+e(fmt(x.started_at))+(x.duration_seconds?" · "+Number(x.duration_seconds)+" ثانیه":"")+
       '</small><p>ثبت مشخصات با رضایت: '+(x.consent_to_contact?"بله":"خیر")+'</p>'+
       (x.proposal_id?'<button class="btn small ghost" data-call-proposal="'+Number(x.proposal_id)+'">مشاهده درخواست و بررسی</button>':
         '<small>هنوز پرونده پیشنهادی قابل بررسی وجود ندارد.</small>')+'</div>').join(""):
       feedEmpty("هنوز تماس واقعی در سیستم ثبت نشده است.");
  }

  async function openCallProposal(id){
    const info=await api("/api/voice/proposals/"+id);
    const vals=info.details||{};
    const heading='<div class="record"><div class="record-head"><h4>پرونده تماس #'+Number(id)+'</h4>'+
       chip(statusText[info.state]||info.state,info.state==="pending"?"warning":"success")+'</div>';
    const fields=Object.entries({
      "نام":vals.caller_name,"شرکت":vals.company,"شهر پروژه":vals.project_city,
      "ظرفیت MW":vals.capacity_mw,"فونداسیون":vals.foundation,"آرایش پنل":vals.panel_layout,
      "شماره تماس":info.phone,"شرح درخواست":vals.request_summary,
      "میزان اطمینان":vals.confidence});
    const body=fields.filter(([,v])=>v!==null&&v!==undefined&&String(v).trim())
      .map(([key,value])=>'<div class="health-row"><span>'+e(key)+'</span><b>'+e(value)+'</b></div>').join("");
    const controls=info.state==="pending"?
      '<div class="button-row"><button class="btn primary small" data-review-call="'+Number(id)+':approved">تأیید و ثبت در CRM</button>'+
      '<button class="btn danger small" data-review-call="'+Number(id)+':rejected">رد درخواست</button></div>':"";
    $("#phoneProposalDetails").innerHTML=heading+body+
      '<details><summary>رونوشت تماس پس از رضایت</summary><p class="call-transcript">'+e(info.transcript)+'</p></details>'+
      controls+'</div>';
    $("#phoneProposalDetails").scrollIntoView({behavior:"smooth",block:"center"});
  }

  async function submitProvider(provider,form) {
    const btn=form.querySelector("[type=submit]");btn.disabled=true;
    try{
      const payload=getForm(form);
      const secrets=provider==="gemini"?["api_key"]:["auth_token"];
      for(const name of secrets)if(!payload[name])delete payload[name];
      if(provider==="telephony")payload.enabled=Boolean(form.elements.namedItem("enabled").checked);
      await api("/api/providers/"+provider,{method:"POST",body:payload});
      for(const field of secrets)form.elements.namedItem(field).value="";
      notify("تنظیمات "+provider+" با رمزنگاری ذخیره شد. حالا اتصال را آزمایش کنید.");
      await loadProviders();
    }catch(err){notify(err.message,true);}
    finally{btn.disabled=false;}
  }

  async function testProvider(provider,btn){
    btn.disabled=true;
    try{
      const result=await api("/api/providers/"+provider+"/test",{method:"POST"});
      notify(provider==="gemini"?"کلید و مدل متن گوگل تأیید شد. صدای Live را جداگانه تست کنید.":
        "اعتبارسنجی حساب Twilio موفق بود. شماره واقعی و مسیر صوت هنوز نیازمند تست‌اند.");
      await loadProviders();
    }catch(err){notify("خطای اتصال: "+err.message,true);}
    finally{btn.disabled=false;}
  }

  async function submitIntegration(provider,form) {
    const btn=form.querySelector("[type=submit]");btn.disabled=true;
    try {
      const payload=getForm(form);
      const secrets=provider==="openai"?["api_key"]:["access_token","app_secret","verify_token"];
      for(const name of secrets)if(!payload[name])delete payload[name];
      await api("/api/integrations/"+provider,{method:"POST",body:payload});
      for(const name of secrets)form.querySelector('[name="'+name+'"]').value="";
      notify("تنظیمات با موفقیت به‌صورت رمزگذاری‌شده ثبت شدند. حالا دکمه آزمایش اتصال را بزنید.");
      await security();
    }catch(err){notify(err.message,true);}finally{btn.disabled=false;}
  }

  async function testIntegration(provider,btn) {
    btn.disabled=true;
    try{
      const result=await api("/api/integrations/"+provider+"/test",{method:"POST"});
      notify(provider==="meta"?"توکن حساب @mehradkavir تأیید شد. وب‌هوک و مجوز پیام‌رسانی هنوز باید بررسی شوند.":"دسترسی OpenAI و مدل انتخابی با موفقیت تأیید شد.");
      await security();
    }catch(err){notify("تست اتصال ناموفق: "+err.message,true);await security().catch(()=>{});}
    finally{btn.disabled=false;}
  }

  async function submitForm(form, endpoint, msg, follow) {
    const button=form.querySelector("[type=submit]"); button.disabled=true;
    try {
      const result=await api(endpoint,{method:"POST",body:getForm(form)});
      form.reset(); notify(msg);
      if (follow) await follow(result);
      else await refreshCurrent();
    } catch (err) {notify(err.message,true);} finally {button.disabled=false;}
  }
  document.addEventListener("click",async ev=>{
    const nav=ev.target.closest("[data-page],[data-goto]");
    if(nav){go(nav.dataset.page||nav.dataset.goto);return;}
    const th=ev.target.closest("[data-thread]");
    if(th){try{await loadThread(Number(th.dataset.thread));}catch(err){notify(err.message,true);}return;}
    const approval=ev.target.closest("[data-approve],[data-reject]");
    if(approval){try{await actDraft(Number(approval.dataset.approve||approval.dataset.reject),approval.dataset.approve?"approve":"reject");}catch(err){notify(err.message,true);}return;}
    const reviewButton=ev.target.closest("[data-review]");
    if(reviewButton){const [kind,id,decision]=reviewButton.dataset.review.split(":");try{await review(kind,Number(id),decision);}catch(err){notify(err.message,true);}return;}
    const editDoc=ev.target.closest("[data-edit-knowledge]");
    if(editDoc){try{await showKnowledgeEditor(Number(editDoc.dataset.editKnowledge));}catch(err){notify(err.message,true);}return;}
    const importBtn=ev.target.closest("[data-start-import]");
    if(importBtn){
      const provider=importBtn.dataset.startImport;
      if(!confirm("اطلاعات منبع "+provider+" در صف بررسی ثبت شود؟ هیچ مدرکی بدون تأیید وارد حافظه نمی‌شود."))return;
      importBtn.disabled=true;
      try{await api("/api/import/jobs",{method:"POST",body:{provider}});notify("درخواست واردسازی در صف پردازش ثبت شد.");await refreshImports();}
      catch(err){notify(err.message,true);}finally{importBtn.disabled=false;}
      return;
    }
    const importReview=ev.target.closest("[data-review-import]");
    if(importReview){
      const [id,decision]=importReview.dataset.reviewImport.split(":");
      if(!confirm("وضعیت این سند "+(decision==="approved"?"تأیید":"رد")+" شود؟"))return;
      try{await api("/api/import/documents/"+id+"/review",{method:"POST",body:{decision}});notify("نتیجه بررسی ذخیره شد.");await knowledge();}
      catch(err){notify(err.message,true);}
      return;
    }
    const revisionReview=ev.target.closest("[data-review-revision]");
    if(revisionReview){
      const [id,decision]=revisionReview.dataset.reviewRevision.split(":");
      const docId=Number($("#knowledgeEditForm").elements.namedItem("id").value);
      if(!confirm("اصلاح سند "+(decision==="approved"?"تأیید":"رد")+" شود؟"))return;
      try{await api("/api/knowledge/revisions/"+id+"/review",{method:"POST",body:{decision}});notify("نسخه بررسی شد.");await knowledge();if(docId)await loadKnowledgeHistory(docId);}
      catch(err){notify(err.message,true);}
      return;
    }
    const policy=ev.target.closest("[data-toggle-policy]");
    if(policy){
      const [id,value]=policy.dataset.togglePolicy.split(":");
      if(!confirm("وضعیت قانون اتوماسیون تغییر کند؟"))return;
      try{await api("/api/automation/policies/"+id+"/toggle",{method:"POST",body:{enabled:value==="true"}});notify("وضعیت سیاست ثبت شد.");await automation();}
      catch(err){notify(err.message,true);}
      return;
    }
    const openProposal=ev.target.closest("[data-call-proposal]");
    if(openProposal){try{await openCallProposal(Number(openProposal.dataset.callProposal));}
      catch(err){notify(err.message,true);}return;}
    const reviewCall=ev.target.closest("[data-review-call]");
    if(reviewCall){
      const [id,decision]=reviewCall.dataset.reviewCall.split(":");
      if(!confirm(decision==="approved"?
          "با تأیید این پرونده، اطلاعات پیشنهادی هوش مصنوعی به CRM وارد می‌شود. مشخصات را بررسی کرده‌اید؟":
          "پرونده پیشنهادی رد شود؟"))return;
      try{
        await api("/api/voice/proposals/"+id+"/review",{method:"POST",body:{decision}});
        notify("نتیجه بررسی تماس ثبت شد.");
        await phone();await openCallProposal(Number(id));
      }catch(err){notify(err.message,true);}return;
    }
    const newTester=ev.target.closest("[data-test-provider]");
    if(newTester){await testProvider(newTester.dataset.testProvider,newTester);return;}
    const discProvider=ev.target.closest("[data-disconnect-provider]");
    if(discProvider){
      const provider=discProvider.dataset.disconnectProvider;
      if(!confirm("اتصال "+provider+" از صندوق کلیدها قطع شود؟ توکن را در سرویس اصلی نیز لغو کنید."))return;
      discProvider.disabled=true;
      try{
        await api("/api/providers/"+provider+"/disconnect",{method:"POST"});
        notify("اتصال قطع شد.");await loadProviders();
      }catch(err){notify(err.message,true);}finally{discProvider.disabled=false;}
      return;
    }
    const archive=ev.target.closest("[data-scenario]");
    if(archive){lastScenario=window.__scenarioCache?.[archive.dataset.scenario]||"";txt("#scenarioOutput",lastScenario);$("#scenarioOutput").classList.remove("empty");$("#copyScenario").disabled=!lastScenario;}
  });
  $("#loginForm").addEventListener("submit",ev=>{ev.preventDefault();login(ev.target);});
  $("#logoutBtn").addEventListener("click",async()=>{try{await api("/api/auth/logout",{method:"POST"});}catch{}csrf="";user=null;showLogin();});
  $("#refreshBtn").addEventListener("click",refreshCurrent);$("#inboxRefresh").addEventListener("click",refreshCurrent);
  $("#demoForm").addEventListener("submit",ev=>{ev.preventDefault();submitForm(ev.target,"/api/demo/message","پیام در صف پردازش ثبت شد",async result=>{selectedThread=result.thread_id;await inbox();});});
  $("#leadForm").addEventListener("submit",ev=>{ev.preventDefault();submitForm(ev.target,"/api/leads","درخواست در CRM ثبت شد.");});
  $("#autoPolicyForm").addEventListener("submit",ev=>{ev.preventDefault();submitForm(ev.target,"/api/automation/policies","قانون ذخیره شد و به‌صورت پیش‌فرض خاموش است.");});
  document.addEventListener("change",async ev=>{
    const input=ev.target.closest("[data-lead-stage]");
    if(!input)return;
    try{await api("/api/leads/"+Number(input.dataset.leadStage)+"/stage",
      {method:"POST",body:{stage:input.value}});notify("مرحله استعلام ثبت شد.");await crm();}
    catch(err){notify(err.message,true);await crm();}
  });
  $("#knowledgeEditForm").addEventListener("submit",async ev=>{
    ev.preventDefault();
    const form=ev.target,data=getForm(form),id=Number(data.id);
    if(!id)return notify("ابتدا یک سند تأییدشده را انتخاب کنید.",true);
    const btn=form.querySelector("[type=submit]");btn.disabled=true;
    try{
      await api("/api/knowledge/"+id+"/revisions",{method:"POST",
        body:{base_version:Number(data.base_version),title:data.title,body:data.body,category:data.category}});
      notify("ویرایش در صف تأیید مدیر ثبت شد.");await knowledge();await loadKnowledgeHistory(id);
    }catch(err){notify(err.message,true);}finally{btn.disabled=false;}
  });
  $("#knowledgeSearch").addEventListener("input",renderKnowledgeList);
  $("#knowledgeCategoryFilter").addEventListener("change",renderKnowledgeList);
  $("#knowledgeStatusFilter").addEventListener("change",renderKnowledgeList);
  $("#knowledgeForm").addEventListener("submit",ev=>{ev.preventDefault();submitForm(ev.target,"/api/knowledge","سند پیشنهادی ثبت شد.");});
  $("#feedbackForm").addEventListener("submit",async ev=>{
    ev.preventDefault();
    const form=ev.target, btn=form.querySelector("[type=submit]");
    btn.disabled=true;
    try{
      const r=await api("/api/feedback/propose",{method:"POST",body:getForm(form)});
      const panel=$("#feedbackResult");
      panel.classList.remove("hidden");
      if(r.needs_clarification){
        panel.textContent="هوش مصنوعی به توضیح بیشتری نیاز دارد: "+r.question;
      }else{
        panel.textContent="قانون پیشنهادی (در انتظار تأیید مدیر): "+r.title+" — "+r.instruction;
        form.reset();await rules();
      }
    }catch(err){notify(err.message,true);}finally{btn.disabled=false;}
  });
  $("#ruleForm").addEventListener("submit",ev=>{ev.preventDefault();submitForm(ev.target,"/api/rules","قانون پیشنهادی ثبت شد.");});
  $("#scenarioForm").addEventListener("submit",async ev=>{ev.preventDefault();const form=ev.target; const btn=form.querySelector("[type=submit]");btn.disabled=true;txt("#scenarioOutput","در حال پردازش توسط موتور محتوا…");try{const r=await api("/api/scenarios",{method:"POST",body:getForm(form)});lastScenario=r.body;txt("#scenarioOutput",r.body);$("#scenarioOutput").classList.remove("empty");$("#copyScenario").disabled=false;notify(r.generated_by==="openai"?"سناریو تولید شد.":"قالب آزمایشی ساخته شد؛ اتصال مدل را بررسی کنید.");await scenarios();}catch(err){notify(err.message,true);}finally{btn.disabled=false;}});
  $("#updateCheckBtn").addEventListener("click",async ev=>{
    ev.target.disabled=true;
    try{await api("/api/updates/check",{method:"POST"});await loadUpdates();notify("آخرین تغییرات GitHub بررسی شدند.");}
    catch(err){notify(err.message,true);}finally{ev.target.disabled=false;}
  });
  $("#updateApproveBtn").addEventListener("click",async ev=>{
    const btn=ev.target,sha=btn.dataset.sha;
    if(!/^[a-f0-9]{40}$/.test(sha))return;
    if(!confirm("این نسخه رسمی GitHub را برای نصب روی همین سیستم تأیید می‌کنی؟ پیش از نصب از پایگاه داده نسخه پشتیبان گرفته می‌شود."))return;
    btn.disabled=true;
    try{
      const r=await api("/api/updates/approve",{method:"POST",body:{sha}});
      notify("آپدیت تأیید و در صف عامل محلی قرار گرفت. تا پایان نصب وضعیت سرویس را بررسی کنید.");
      await loadUpdates();
    }catch(err){notify(err.message,true);await loadUpdates();}
  });
  $("#geminiConnectForm").addEventListener("submit",ev=>{
    ev.preventDefault();submitProvider("gemini",ev.target);
  });
  $("#telephonyConnectForm").addEventListener("submit",ev=>{
    ev.preventDefault();submitProvider("telephony",ev.target);
  });
  $("#saveAiProvider").addEventListener("click",async ev=>{
    ev.target.disabled=true;
    try{
      const provider=$("#aiProviderSelect").value;
      await api("/api/providers/select",{method:"POST",body:{provider}});
      notify("مغز پیش‌فرض روی "+provider+" تنظیم شد.");
    }catch(err){notify(err.message,true);}
    finally{ev.target.disabled=false;}
  });
  $("#phoneRefreshBtn").addEventListener("click",()=>phone().catch(err=>notify(err.message,true)));
  $("#voicePreviewForm").addEventListener("submit",async ev=>{
    ev.preventDefault();
    const btn=ev.target.querySelector("[type=submit]");
    btn.disabled=true;txt("#voicePreviewResult","در حال درخواست تولید نمونه صوت...");
    try{
      const response=await fetch("/api/voice/preview",{
        method:"POST",credentials:"same-origin",
        headers:{"Content-Type":"application/json","X-CSRF-Token":csrf},
        body:JSON.stringify(getForm(ev.target))
      });
      if(!response.ok)throw Error("Google TTS پاسخ معتبر نداد. کلید، مدل و دسترسی API را بررسی کنید.");
      const audio=$("#voicePreviewAudio");
      if(audio.dataset.lastUrl)URL.revokeObjectURL(audio.dataset.lastUrl);
      const url=URL.createObjectURL(await response.blob());
      audio.src=url;audio.dataset.lastUrl=url;audio.classList.remove("hidden");
      txt("#voicePreviewResult","نمونه صوتی تولید شد. برای شنیدن دکمه پخش را بزنید.");
      await audio.play().catch(()=>{});
    }catch(err){notify(err.message,true);txt("#voicePreviewResult",err.message);}
    finally{btn.disabled=false;}
  });
  $("#openaiConnectForm").addEventListener("submit",ev=>{ev.preventDefault();submitIntegration("openai",ev.target);});
  $("#metaConnectForm").addEventListener("submit",ev=>{ev.preventDefault();submitIntegration("meta",ev.target);});
  document.addEventListener("click",async ev=>{
    const tester=ev.target.closest("[data-test-integration]");
    if(tester){await testIntegration(tester.dataset.testIntegration,tester);return;}
    const disc=ev.target.closest("[data-disconnect-integration]");
    if(disc){
      const provider=disc.dataset.disconnectIntegration;
      if(!window.confirm("اتصال "+provider+" را قطع می‌کنید؟ توکن ثبت‌شده در صندوق امن خالی خواهد شد."))return;
      disc.disabled=true;
      try{
        await api("/api/integrations/"+provider+"/disconnect",{method:"POST"});
        notify("اتصال قطع شد. برای ابطال کامل، توکن را در سرویس اصلی هم لغو کنید.");
        await security();
      }catch(err){notify(err.message,true);}finally{disc.disabled=false;}
    }
  });
  $("#passwordForm").addEventListener("submit",async ev=>{
    ev.preventDefault();
    const form=ev.target, btn=form.querySelector("[type=submit]");
    btn.disabled=true;
    try{
      const result=await api("/api/account/password",{method:"POST",body:getForm(form)});
      if(result.relogin_required){csrf="";user=null;form.reset();showLogin();notify("رمز تغییر کرد. همه نشست‌ها بسته شدند؛ دوباره وارد شوید.");}
    }catch(err){notify(err.message,true);}finally{btn.disabled=false;}
  });
  $("#copyScenario").addEventListener("click",async()=>{try{await navigator.clipboard.writeText(lastScenario);notify("متن سناریو کپی شد");}catch{notify("کپی امکان‌پذیر نیست",true);}});
  function tick(){txt("#clock",new Intl.DateTimeFormat("fa-IR",{weekday:"short",day:"numeric",month:"short"}).format(new Date()));}
  tick();setInterval(tick,60_000);
  setInterval(()=>{if(user && activePage==="inbox")inbox().catch(()=>{});},12_000);
  setInterval(()=>{if(user&&activePage==="security")loadUpdates().catch(()=>{});},90000);
  bootstrap();
})();
