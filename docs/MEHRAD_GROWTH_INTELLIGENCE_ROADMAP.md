# Mehrad Kavir Growth Intelligence OS
## نقشه مهندسی توسعه تا «مرکز فرماندهی رشد»

Version: Architecture Roadmap 1.1 · 2026-11-06 · Status: PLANNED (not implemented)

### مأموریت
رابطه پیوسته مشاهده داده → تشخیص مسئله → ارائه فرضیه و سؤال روشن‌ساز → پیشنهاد قابل آزمایش → تأیید انسانی → اقدام مجاز → سنجش نتیجه → حافظه تأییدشده.

شاخص اصلی موفقیت مهراد کویر: سرنخ واجد شرایط استعلام سازه خورشیدی و نرخ تبدیل به پیش‌فاکتور / قرارداد. تعداد ویو تنها شاخص کمکی است.

### هویت بصری تأییدشده
- فولادی اصلی: #1E2B39 — سهم 60 درصد
- آبی سازمانی: #006FFE — سهم 20 درصد
- خاکستری روشن: #F3F5F7 — سهم 15 درصد
- خاکستری میانی: #AEB8C2 — سهم 5 درصد
- ذغالی مکمل: #111A24
- لوگوی منبع: تصویری که مالک برند فرستاده است. SVG مخصوص رابط با همان ساختار در app/static/mehrad-kavir-logo.svg قرار دارد؛ برای امور چاپی PNG اصلی همچنان مرجع است.

### P0 — Instagram Intelligence
منبع آمار باید API رسمی Meta برای حساب حرفه‌ای دارای مجوز باشد. هر insight و media با ID، نوع، timestamp UTC، نسخه API، نام metric، metric_type، period، source و sync status نگهداری می‌شود.

داشبوردهای الزامی:
1. سلامت پیج: Reach، Views، Interactions و روند فالوئر فقط در صورت پشتیبانی و دریافت موفق.
2. تحلیل Reels: بررسی 3h/6h/12h/24h/48h/72h/7d با snapshot های واقعی، تفکیک trial و تغییرات انتشار در صورت دستی/قابل ثبت بودن.
3. Content Cohorts: مقایسه فقط رسانه‌های هم‌نوع و هم‌سن، میانه و بازه پراکندگی؛ ممنوعیت مقایسه خام یک ریلز ۳ ساعته با ۳۰ روزه.
4. تحلیل کانال: موضوع‌های پرتکرار دایرکت/کامنت، رضایت، شکایات، تاخیر در پاسخ و FAQ gaps.
5. attribution: محتوای منشأ، کلیک لینک، گفتگوی معتبر، استعلام پروژه، پیشنهاد و قرارداد، در صورت وجود لینک و رویداد واقعی.
6. Alert Center: رشد نامتعارف، افت نسبت به baseline، نامعتبرشدن توکن Meta، پیام مهم بی‌پاسخ و افزایش شکایت.

فرمول‌های پیشنهادی:
- Engagement / Reach = (likes + comments + saves + shares) / reach × 100 فقط با داده‌های در دسترس و سازگار.
- Save rate = saves / reach × 100.
- Share rate = shares / reach × 100.
- View/Reach ratio = views / reach؛ این عدد تعداد افراد یکتا نیست.
- Qualified lead rate = qualified RFQs / inbound leads × 100.
- Performance index = metric at same post age / median same-age same-format cohort.

باید موجودنبودن داده را NULL نمایش داد؛ صفر معادل missing نیست.
Metrics قدیمی از جمله impressions و plays در نسخه‌های جدید API منسوخ شده‌اند؛ catalogs نسخه‌بندی شوند.

### P0 — AI Growth Strategist
یک تحلیلگر دائمِ شواهد، نه یک تولیدکننده روایت غیرواقعی. هر توصیه باید شامل شواهد، تاریخ داده، سطح اطمینان، احتمال عوامل جایگزین، میزان اثر مورد انتظار به‌عنوان فرضیه، اقدام پیشنهادی، مسئول و معیار ارزیابی باشد.

نمونه سؤال هوشمند: «هدف ریلز آگاهی از برند بوده یا استعلام؟»، «کاور یا CTA پس از Share to Everyone تغییر کرده؟»، «این اعداد متعلق به چند ساعت پس از انتشارند؟». AI به جای حدس از مدیر سؤال می‌کند و پاسخ مورد تأیید را در پرونده آزمایش ذخیره می‌کند.

### P0 — Content Research Lab
برای هر محتوا: persona، ستون محتوا، pain point، visual hook در ۳ ثانیه اول، متن، صحنه‌ها، B-roll، گویندگی، کپشن، CTA، نسخه و نتیجه انتشار. ستون‌های مهراد کویر: خاک، باد، اقلیم، گالوانیزه، کوبشی/بتنی، مونوفیشیال/بایفیشیال، کارخانه، پروژه‌های اجرایی، هزینه مهندسی و پرسش‌های متداول.

عملکرد نسخه‌های مختلف فقط بر اساس داده منتشرشده ارزیابی شود؛ هیچ ادعای فنی، ظرفیت تولید، سابقه یا قیمت بدون مرجع مصوب تولید نشود.

### P0 — Smart RFQ & Sales CRM
استخراج حداقل اطلاعات لازم برای استعلام: شهر، ظرفیت، نوع سازه/فونداسیون، نوع پنل، آرایش، ارتفاع، شیب، باد/خاک در صورت وجود و زمان پروژه. وضعیت lead: new → qualifying → qualified → engineering review → quotation → won/lost.

موتور مکالمه تنها سؤال بعدی ضروری را مطرح کند. طراحی نهایی سازه، قیمت قطعی، تعهد زمان تحویل و قرارداد باید به افراد مجاز ارجاع شوند. ادغام با فرم سایت مهراد کویر و منبع UTM در فاز بعد.

### P0 — Governed Brain 2.0
لایه‌ها: Brand DNA، Verified Knowledge، Feedback Rules، Content Performance، CRM Context. حافظه جدید هرگز مستقیم از متن کامنت یا فایل وارد قوانین فعال نشود. مسیر: proposal → question → conflict check → owner review → versioning → evaluation → activation یا rollback.

عامل‌های مستقلِ محدود: تحلیلگر داده، نویسنده سناریو، کارشناس فروش، دستیار مهندسی، ناظر حریم خصوصی، بررسی‌کننده خروجی. نقش‌ها در Backend enforce شوند. مدل به رازها و اطلاعات خارج از دامنه کاری دسترسی نداشته باشد.

### P1 — Experiment Lab
تعریف hypothesis، owner، start/end، cohort، intervention، metric، baseline و guardrail. آزمایش هوک، کاور، زمان، CTA و قالب؛ بررسی تداخل عوامل و حجم نمونه؛ نتیجه همبستگی است مگر طراحی آزمایش شواهد علّی فراهم کند.

### P1 — Creative QA & Publishing
تقویم محتوا، تاییدیه انسانی، بازبینی هویت بصری/لوگو/خوانایی، آماده‌سازی خروجی مناسب Instagram، صف انتشار مجاز پس از تکمیل Meta OAuth و permissions. انتشار خودکار عمومی بدون approval پیش‌فرض ممنوع.

### P1 — Executive Command Center
گزارش هفتگی فارسی: چه رشدی اتفاق افتاده، منبع هر عدد، سه موفقیت قابل اتکا، سه ریسک، اقدامات پیشنهادی و مالک هر کار. مقایسه کسب‌وکار بر مبنای سرنخ واقعی و فروش.

### P2 — Competitor Radar
رصد محتوای عمومی و متریک‌های *قابل‌دسترسی به شکل مجاز*، تحلیل قالب‌ها، موضوعات، نحوه روایت. دسترسی به Insights خصوصی رقبا، پیام‌های خصوصی یا داده غیرمجاز ادعا نشود. Instagram Login برخی قابلیت‌های Facebook Login نظیر ads/tagging را ندارد.

### قابلیت‌های زیربنایی ضروری
- OAuth رسمی Meta، مدیریت scope، گردش و تمدید توکن؛ HTTPS webhook، idempotency و retry امن.
- PostgreSQL + pgvector برای مقیاس، Redis queue، object storage و backup رمزگذاری‌شده.
- RBAC owner/growth/sales/engineering/content/analyst/viewer و audit trail.
- ابزار AI با دسترسی محدود، محافظت Prompt Injection، SSRF و افشای اطلاعات.
- Kill switch و shadow mode برای خودکارسازی. روزشمار هزینه و توکن مصرفی.
- observability، CI، تست نفوذ مستقل پیش از استقرار عمومی، سیاست retention.
- مرجع فنی و تاریخ اعتبار برای هر ادعای مهندسی.

### مدل داده
instagram_accounts، media_posts، media_metric_snapshots، account_metric_snapshots،
metric_catalog، content_tags، content_versions، scenarios، experiments،
leads، lead_events، rfq_requirements، content_attribution، alerts،
knowledge_documents، knowledge_versions، feedback_proposals،
brand_rules، analytics_recommendations، approval_requests، audit_events، job_runs.

### مراحل تحویل
- F0 Brand identity: لوگو و پالت رسمی، تست رابط و امنیت.
- F1 Insights Foundation: OAuth، مجوزها، snapshots واقعی، داشبورد بدون داده ساختگی.
- F2 Growth Analyst: baselines، cohort analysis، علائم هشدار و توصیه مستند.
- F3 Feedback loop: عملکرد هر محتوا به بریف و سناریوی اصلی مرتبط شود.
- F4 Sales CRM: استعلام مهندسی و فالوآپ انسانی با ردیابی UTM.
- F5 Safe Autopilot: اجرای کنترل‌شده موارد کم‌ریسک پس از تست و تأیید.

### معیار پذیرش
- هر عدد قابل ردیابی به منبع، زمان و نسخه API باشد.
- عدم دسترسی مساوی صفر گزارش نشود.
- هیچ داده محرمانه‌ای به مدل یا نقش غیرمجاز منتقل نشود.
- زمان‌بندی و مقایسه عملکرد رسانه age-normalized باشد.
- ادعای مهندسی و اقدام پرریسک نیازمند تأیید باشد.
- در قطع API، سیستم fail closed و قابل بازیابی باشد.

### وضعیت واقعی
فقط زیرساخت نسخه 0.1.0 و موارد برندینگ فاز صفر کدنویسی شده‌اند. ماژول Instagram Insights و CRM در این سند **طرح توسعه** هستند و تا اتصال واقعی API و تست عملیاتی آماده استفاده نیستند.

### منابع
https://developers.facebook.com/docs/instagram-platform/
https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api
https://platform.openai.com/docs/
