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
    txt("#currentPageName", ({dashboard:"نمای کلی",inbox:"صندوق پیام",insights:"تحلیل پیج",knowledge:"دانش برند",memory:"حافظه و یادگیری",content:"استودیو محتوا",security:"امنیت و اتصالات"})[page]);
    window.scrollTo({top:0,behavior:"smooth"});
    refreshCurrent();
  }
  async function refreshCurrent() {
    try {
      if (activePage === "dashboard") await dashboard();
      else if (activePage === "inbox") await inbox();
      else if (activePage === "insights") await insights();
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
    // There is intentionally no simulated metric source. This view does not claim real Insights integration.
    const data = await api("/api/dashboard");
    txt("#insightsStatus", data.integration.meta
      ? "اتصال پایه Meta در تنظیمات ثبت شده، اما مجوز و همگام‌سازی Instagram Insights هنوز پیاده‌سازی نشده است."
      : "اتصال Meta هنوز آماده نیست و ماژول جمع‌آوری Instagram Insights نیز در نقشه توسعه قرار دارد.");
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
  function record(obj,type) {
    const title=e(obj.title);
    const body=e(type==="rule"?obj.instruction:obj.body);
    const state=obj.status;
    const button=(state==="pending"&&user?.role==="owner")?'<div class="record-actions"><button class="btn small primary" data-review="'+type+':'+Number(obj.id)+':approved">تأیید</button><button class="btn small danger" data-review="'+type+':'+Number(obj.id)+':rejected">رد</button></div>':(type==="knowledge"&&state==="approved"?'<div class="record-actions"><button class="btn small ghost" data-edit-knowledge="'+Number(obj.id)+'">ویرایش سند / نسخه '+Number(obj.version||1)+'</button></div>':"");
    return '<div class="record"><div class="record-head"><h4>'+title+'</h4>'+chip(statusText[state]||state,state==="approved"?"success":state==="pending"?"warning":"danger")+'</div><p>'+body+'</p><small>'+e(type==="rule"?obj.scope:obj.category)+' · '+e(fmt(obj.created_at))+'</small>'+button+'</div>';
  }
  async function knowledge() {
    const items=await api("/api/knowledge");
    window.__knowledgeCache=Object.fromEntries(items.map(x=>[x.id,x]));
    txt("#knowledgeCount",items.length+" سند");
    $("#knowledgeList").innerHTML=items.length?items.map(x=>record(x,"knowledge")).join(""):feedEmpty("هیچ سندی ثبت نشده است.");
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
    const archive=ev.target.closest("[data-scenario]");
    if(archive){lastScenario=window.__scenarioCache?.[archive.dataset.scenario]||"";txt("#scenarioOutput",lastScenario);$("#scenarioOutput").classList.remove("empty");$("#copyScenario").disabled=!lastScenario;}
  });
  $("#loginForm").addEventListener("submit",ev=>{ev.preventDefault();login(ev.target);});
  $("#logoutBtn").addEventListener("click",async()=>{try{await api("/api/auth/logout",{method:"POST"});}catch{}csrf="";user=null;showLogin();});
  $("#refreshBtn").addEventListener("click",refreshCurrent);$("#inboxRefresh").addEventListener("click",refreshCurrent);
  $("#demoForm").addEventListener("submit",ev=>{ev.preventDefault();submitForm(ev.target,"/api/demo/message","پیام در صف پردازش ثبت شد",async result=>{selectedThread=result.thread_id;await inbox();});});
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
