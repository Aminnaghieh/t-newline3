# 📋 چک‌لیست و برنامه کامل چالش لیارا (Liara Challenge) - **نسخه نهایی هماهنگ با ویدئو و معیارهای داوری**

## 🎯 هدف کلی ( مطابق چشم‌انداز چالش)
ساخت یک **SRE Agent / Technical Copilot** هوشمند برای پلتفرم لیارا که:
1. **راه‌اندازی اولیه و اولین دیپلوی** - راهنمای انتخاب روش استقرار، بررسی نیازمندی‌ها، پیشنهاد پلن، پیکربندی، دیپلوی، تنظیم دامنه
2. **مدیریت دیپلوی و عملیات زیرساخت** - انتشار نسخه جدید، پیکربندی/مدیریت سرویس از طریق API، بررسی وضعیت و خطاهای دیپلوی، خودکارسازی عملیات تکراری
3. **پایش و نگهداری** - بررسی سلامت سرویس (CPU/RAM)، دریافت و تحلیل لاگ‌ها، بررسی مشکلات (کندی، اختلال، افزایش مصرف)، پیشنهاد بهبود، اقدامات اصلاحی
4. **عیب‌یابی هوشمند** - جمع‌آوری اطلاعات خطا (مثلا HTTP 500)، بررسی لاگ‌ها/مصادر/مصرف، شناسایی و اولویت‌بندی علل، ارائه راهکار، اجرای اصلاح با مجوز و بررسی نتیجه
5. **Human-in-the-Loop** - تأیید پیش از عملیات حساس (تغییر تنظیمات پرریسک، ری‌استارت، تغییر پلن)، تمایز عملیات کم‌ریسک/حساس، نمایش نتیجه و خطاها
6. **UX برتر** - ساده‌سازی پیچیدگی زیرساخت، درخواست با حداقل دانش فنی، درک وضعیت، ارزیابی پیشنهادها، تأیید اجرا

---

## ✅ چک‌لیست نیازمندی‌های اصلی (مطابق ۴ قابلیت اصلی ویدیو)

### ۱️⃣ قابلیت: راه‌اندازی اولیه و اولین دیپلوی (Initial Setup & Deployment) - **امتیاز: ۱۰۰/۳۰۰**
- [ ] **اتصال امن به لیارا** - API Token/OAuth، ذخیره امن Credentials
- [ ] **تحلیل هوشمند پروژه** - تشخیص زبان، فریم‌ورک، package.json/requirements.txt/go.mod، پورت، دستور استارت
- [ ] **پیشنهاد پلن بهینه** - Mapping نیازهای پروژه به پلن‌های لیارا (CPU, RAM, Disk, Bandwidth)
- [ ] **Wizard راه‌اندازی گام‌به‌گام** - نام اپلیکیشن، انتخاب پلن، متغیرهای محیطی، پورت، build command
- [ ] **تنظیم دامنه و SSL** - راهنمای اتصال دامنه (ایرنیک/سایر)، Rekord DNS، صدور SSL
- [ ] **دیپلوی با Human Approval** - نمایش خلاصه تغییرات، درخواست تأیید قبل از Deploy
- [ ] **Real-time Deploy Logs** - استریم لاگ‌های بیلد و استارت، نمایش پیشرفت
- [ ] **Post-deploy Verification** - Health check، دسترسی به URL، نمایش اطلاعات اتصال

### ۲️⃣ قابلیت: مدیریت دیپلوی و عملیات زیرساخت (Deployment & Operations) - **امتیاز: ۱۰۰/۳۰۰**
- [ ] **Deploy نسخه جدید** - Trigger از Git push / Manual / Scheduled
- [ ] **مدیریت سرویس از طریق API** - Start/Stop/Restart، Scale (Replicas)، Update Config/Env
- [ ] **بررسی وضعیت دیپلوی** - Build status، Deploy status، Rollback status
- [ ] **خطایابی دیپلوی** - Parse خطاهای بیلد (Dependency، Compile، Config)، پیشنهاد رفع
- [ ] **خودکارسازی عملیات تکراری** - Auto-deploy on merge، Scheduled backups، Cleanup old images
- [ ] **Rollback یک‌کلیک** - به نسخه قبلی پایدار، با تأیید کاربر

### ۳️⃣ قابلیت: پایش و نگهداری (Monitoring & Maintenance) - **امتیاز: ۵۰/۳۰۰**
- [ ] **متریک‌های زنده** - CPU%، Memory%، Disk I/O، Network I/O، Response Time (p50/p95/p99)
- [ ] **Health Checks** - Liveness/Readiness endpoints، Application-level checks
- [ ] **Log Aggregation & Streaming** - جمع‌آوری لاگ‌های stdout/stderr، فیلتر، جستجو، Real-time tail
- [ ] **Alerting هوشمند** - Threshold-based (CPU>80%)، Anomaly detection (Traffic spike)، Notification channels
- [ ] **تحلیل عملکرد** - شناسایی Bottleneckها، پیشنهاد Scale/Optimize، Cost optimization

### ۴️⃣ قابلیت: عیب‌یابی هوشمند (Intelligent Troubleshooting) - **امتیاز: ۱۰۰/۳۰۰**
- [ ] **Error Detection** - HTTP 5xx، CrashLoop، OOMKilled، Timeout، High Latency
- [ ] **Context Collection** - لاگ‌های مرتبط (pre/post crash)، Metrics snapshot، Deploy history، Config diff
- [ ] **Root Cause Analysis (RCA)** - دسته‌بندی: Resource Exhaustion / Code Bug / Config Error / Dependency Failure / Network Issue
- [ ] **Prioritized Hypotheses** - لیست علل محتمل با احتمال و اثر
- [ ] **Remediation Suggestions** - Scale up، Restart، Config fix، Code patch (با مثال)، Dependency update
- [ ] **Auto-Remediation (با مجوز)** - اجرای اقدامات کم‌ریسک (Restart، Clear Cache)، درخواست تأیید برای پرریسک (Scale، Rollback، Code change)
- [ ] **Verification Loop** - بررسی اثر اقدام، بازگشت به حالتnormal، گزارش نهایی

### ۵️⃣ قابلیت: Human-in-the-Loop & UX (عرضه در همه فازها) - **امتیاز: ۵۰/۳۰۰**
- [ ] **Risk Classification** - Low Risk (Auto-execute) vs High Risk (Require Approval)
- [ ] **Approval UI** - خلاصه عملیات، ریسک، گزینه‌های Confirm/Reject/Modify
- [ ] **Natural Language Interface** - Chat/CLI با زبان طبیعی فارسی/انگلیسی
- [ ] **Progress & Status Visibility** - Spinner، Progress bar، Step indicator، Live logs
- [ ] **Audit Trail** - تاریخچه کامل عملیات، چه کسی چه زمانی چه کرد
- [ ] **Error Transparency** - پیام خطای دوستانه، راهکار، لینک مستندات
---

## 🏗 معماری فنی (Technical Architecture) - **مستندات معماری برای تحویل MD**

### 🔌 یکپارچه‌سازی با لیارا (Liara API Integration) - **Endpoints واقعی از developers.liara.ir**

#### Base Configuration
- **Base URL**: `https://api.liara.ir`
- **Auth**: `Authorization: Bearer <API_TOKEN>` (JWT Bearer Token from Console)
- **WebSocket**: `wss://api.liara.ir?token=<api-token>&cmd=/bin/bash&project_id=<project-id>`

#### Core Endpoints Mapping (برای SRE Agent)
| قابلیت Agent | Endpoint | Method | Priority |
|--------------|----------|--------|----------|
| **List Projects** | `/v1/projects` | GET | 🔴 Critical |
| **Project Details** | `/v1/projects/{name}` | GET | 🔴 Critical |
| **Create Project** | `/v1/projects` | POST | 🔴 Critical |
| **Delete Project** | `/v1/projects/{name}` | DELETE | 🟡 High |
| **Restart App** | `/v1/projects/{name}/actions/restart` | POST | 🔴 Critical |
| **Scale On/Off** | `/v1/projects/{name}/actions/scale` | POST | 🟡 High |
| **Change Plan** | `/v1/projects/{name}/resize` | POST | 🟡 High |
| **Zero-Downtime** | `/v1/projects/{id}/zero-downtime/{enable\|disable}` | POST | 🟢 Medium |
| **Deploy Source** | `/v2/projects/{name}/sources` | POST (multipart) | 🔴 Critical |
| **Deploy Release** | `/v2/projects/{name}/releases` | POST | 🔴 Critical |
| **Get Releases** | `/v1/projects/{name}/releases?page=1&count=10` | GET | 🔴 Critical |
| **Deploy Events** | `/v1/projects/{name}/events` | GET | 🔴 Critical |
| **Metrics/Reports** | `/v1/projects/{name}/reports` | GET | 🔴 Critical |
| **Logs (Historical)** | `/v1/projects/{name}/logs?since=<timestamp>` | GET | 🔴 Critical |
| **Logs (Live)** | WebSocket (see above) | WS | 🟡 High |
| **Update Envs** | `/v1/projects/update-envs` | POST | 🔴 Critical |
| **List Domains** | `/v1/domains?project={name}` | GET | 🟡 High |
| **Create Domain** | `/v1/domains` | POST | 🟡 High |
| **Attach Domain** | `/v1/domains/set-project` | POST | 🟡 High |
| **Disks** | `/v1/projects/{name}/disks` | GET/POST | 🟢 Medium |
| **Disk Backups** | `/v1/projects/{name}/disks/{id}/backups` | GET/POST | 🟢 Medium |
| **User Info** | `/v1/me` | GET | 🟢 Medium |
| **Billing** | `/v1/billing` | GET | 🟢 Medium |
| **Git Integrations** | `/v1/user/git-integrations` | GET | 🟢 Medium |

#### Platforms Supported (for Create Project)
`nodejs`, `python`, `go`, `php`, `ruby`, `dotnet`, `static`, `docker`, `java`, `rust`, `deno`, `bun`

#### Plan IDs (Common)
`micro`, `small`, `medium`, `large`, `xlarge`, `xxlarge` — *Maintain local mapping table with CPU/RAM/Disk/Bandwidth/Price*

#### Implementation Requirements
- [ ] **Liara API Client (TypeScript)** - Wrapper کامل REST API با:
  - Authentication (API Token management، Token refresh)
  - Applications CRUD، Deployments، Domains، Metrics، Logs
  - Type-safe interfaces برای تمام endpoints (از OpenAPI spec تولید شده)
  - Retry logic با exponential backoff، Rate limiting handling، Error mapping
  - Multipart upload support برای `/v2/projects/{name}/sources`
- [ ] **Webhook Handling** - **نکته مهم**: لیارا webhook native برای deploy events نداره
  - Alternative: Poll `/v1/projects/{name}/events` هر ۳۰ ثانیه
  - یا GitHub/GitLab webhook برای trigger deploy
- [ ] **Real-time Log Streaming** - WebSocket برای لاگ‌های زنده بیلد و رانتایم
- [ ] **CLI Entry Point** - `liara-agent` با Subcommands: `init`، `deploy`، `monitor`، `debug`، `config`
- [ ] **Rate Limit Handling** - Conservative: 60 req/min read، 20 req/min write، Respect `Retry-After`
- [ ] **Graceful Degradation** - وقتی endpoint در دسترس نیست (مثل metrics)، به کاربر اطلاع دهید

### 🧠 موتور هوش مصنوعی (AI Engine)
- [ ] **LLM Provider Abstraction** - OpenAI / Anthropic / Local (Ollama) با Fallback
- [ ] **Specialized Prompt Templates** - برای هر Task:
  - Project Analysis → Plan Recommendation
  - Log Analysis → Root Cause Hypotheses
  - Metrics Analysis → Bottleneck Detection
  - Remediation Planning → Step-by-step Actions
- [ ] **RAG System** - Knowledge Base:
  - Liara Docs/API Specs، Common Error Patterns، Best Practices
  - Vector Store (Local: ChromaDB / Cloud: Pinecone)
- [ ] **Tool/Function Calling Schema** -yped Actions:
  - `liara.deploy`، `liara.scale`، `liara.restart`، `liara.get_logs`، `liara.get_metrics`
  - `github.create_pr`، `github.create_issue` (برای Coding Agent Bridge)
  - Risk Level Annotation هر Tool: `low` | `medium` | `high`

### 💾 مدیریت حالت و داده‌ها (State & Data Management)
- [ ] **Local SQLite Database** - Projects، Deployments، Conversations، Audit Logs
- [ ] **Encrypted Credentials Store** - OS Keychain / libsecret / Age encryption
- [ ] **Conversation Memory** - Session context، Multi-turn history، Project context
- [ ] **Metrics Time-series Buffer** - In-memory + Optional InfluxDB/Prometheus remote write
- [ ] **Audit Log** - Immutable، Timestamped، User/Action/Result/Error

### 🔒 امنیت و محدودیت‌ها (Security & Limitations)
- [ ] **API Limitation Handling** - Graceful degradation وقتی endpoint در دسترس نیست
- [ ] **Permission Scoping** - Read-only vs Write operations
- [ ] **Secrets Management** - Never log tokens، Mask sensitive values in output
- [ ] **Rate Limit Awareness** - Backoff، Cache، User notification

---

## 🎬 ویدیو دمو (Demo Video) - **الزامی، ~۵ دقیقه، ۱۰۰٪ برای داوری**

### سناریوهای نمایش (مجموع ~۵ دقیقه)
| سناریو | مدت | محتوای کلیدی |
|---------|-----|--------------|
| **۱. اولین دیپلوی** | ۹۰ ثانیه | `liara-agent init` → تحلیل پروژه → پیشنهاد پلن → تنظیم Env → Deploy با Approval → Live logs → URL فعال |
| **۲. عیب‌یابی هوشمند** | ۱۲۰ ثانیه | شبیه‌سازی HTTP 500 / High Latency → `liara-agent debug` → جمع‌آوری Context → RCA → پیشنهادها → Auto-fix (Restart) با Approval → Verification |
| **۳. مدیریت دیپلوی و Scale** | ۶۰ ثانیه | `liara-agent deploy` (نسخه جدید) → Rollback یک‌کلیک → Scale up با Approval |
| **۴. پایش و Alert** | ۶۰ ثانیه | `liara-agent monitor` → Live metrics → Alert trigger → پیشنهاد بهینه‌سازی |

### الزامات فنی ویدیو
- [ ] **Resolution**: 1080p (1920x1080) minimum
- [ ] **Audio**: صدای rõ (Mic باکیفیت) + توضیح فارسی - *اگر امکان صحبت نیست: بی‌صدا با کپشن/زیرنویس کامل*
- [ ] **Editing**: برش‌های ساده، بدون افکت‌های پیچیده، Focus روی Terminal/UI
- [ ] **Subtitles**: فارسی (الزامی) + انگلیسی (اختیاری اما توصیه)
- [ ] **Format**: MP4، H.264، < 500MB
- [ ] **Hosting**: GitHub Release / Google Drive / YouTube (Unlisted) - لینک در README

### چک‌لیست محتوای ویدیو
- [ ] نمایش **Real Terminal** (نه اسلاید)
- [ ] نشان دادن **Human Approval** در لحظه
- [ ] نمایش **AI Reasoning** (چه فکر می‌کند، چرا پیشنهاد می‌دهد)
- [ ] نمایش **Result Verification** (بعد از Fix، چک می‌شود حل شده؟)
- [ ] اشاره به **API Limitations** (اگر هست)
- [ ] Narration: "کاربر فقط X کرد، Agent بقیه را انجام داد"

---

## 📦 موارد تحویلی (Deliverables) - **دقیقاً مطابق بریف**

### ۱. MVP قابل اجرا (Executable MVP)
- [ ] **Binary/Package** - `liara-agent` قابل نصب و اجرا (npm / Go binary / Docker)
- [ ] **Quick Start** - نصب تا اولین دیپلوی < ۵ دقیقه
- [ ] **Configuration** - `liara-agent config` برای توکن، پیش‌فرض‌ها
- [ ] **Documentation In-line** - `--help`، Interactive guides

### ۲. مستندات فنی (ARCHITECTURE.md) - **در ریشه ریپو**
- [ ] **معماری کوتاه** - دیاگرام متنی (Mermaid) + توضیح لایه‌ها
- [ ] **نحوه اتصال به API لیارا** - Endpoints استفاده شده، Auth flow، Rate limits
- [ ] **محدودیت‌های راهکار** - چه APIهایی در دسترس نیست، کارکردهای جایگزین
- [ ] **نحوه تعامل کاربر** - CLI Commands، Chat flows، Approval flows
- [ ] **Security Model** - Credential storage، Data flow، Audit logging

### ۳. ویدیو دمو (Demo Video)
- [ ] فایل ویدیو + لینک در README

### ۴. README کامل
- [ ] Problem Statement، Features، Architecture Summary
- [ ] Installation، Configuration، Usage Examples
- [ ] Demo Video Link، Screenshots/GIFs
- [ ] Limitations، Known Issues، Roadmap
- [ ] License (MIT/Apache 2.0)
---

## 🏗 Stack تکنولوژی پیشنهادی (بهینه برای تسریع و کیفیت)

| لایه | انتخاب پیشنهادی | دلیل استراتژیک |
|------|----------------|-----------------|
| **Core Language** | **TypeScript (Node.js/Bun)** | Type-safe، AI SDK ecosystem، سریع development، Cross-platform |
| **CLI Framework** | **Ink (React for CLI)** | UX غنی (Spinner، Input، Select، Live logs)، Component-based |
| **AI/LLM** | **Vercel AI SDK** | Tool calling، Streaming، Multi-provider، RAG helpers |
| **Liara API** | **Custom Client (OpenAPI-generated + Manual)** | کنترل کامل، Type-safe، Mock-friendly برای تست |
| **Local DB** | **SQLite (better-sqlite3 / Bun SQLite)** | Zero-config، Portable، Fast، Embedded |
| **Encryption** | **OS Keychain / @tauri-apps/plugin-store** | Secure credential storage cross-platform |
| **Log/Metric Streaming** | **WebSocket (ws) / Server-Sent Events** | Real-time، Simple، No extra infra |
| **Testing** | **Vitest (Unit/Integration) + Playwright (E2E CLI)** | Fast، Native ESM، Good DX |
| **Packaging** | **npm (pkg) یا GoReleaser (اگر Go)** | Cross-platform binary، Auto-updates |
| **Video Recording** | **OBS Studio / Asciinema (Terminal)** | High quality، Terminal-native option |

> **نکته**: اگر تیم Go ترجیح می‌دهد، معادل‌ها: Cobra/CLI، Go OpenAPI Generator، SQLite (modernc.org/sqlite)، Vercel AI SDK Go port یا LangChainGo.

---

## 📅 Timeline پیشنهادی (۴ هفته = ۲۸ روز) - **فوکوس بر تحویل‌های داوری**

### ✅ هفته ۱ (روز ۱-۷): Foundation & First Deploy MVP
| روز | تسک | خروجی |
|-----|------|-------|
| ۱-۲ | Project Setup، Liara API Client (Auth، Apps، Deployments، Logs، Metrics) | `liara-agent config` کار می‌کند، لیست اپلیکیشن‌ها |
| ۳-۴ | Project Analyzer (Detect: Node/Python/Go/Static، Port، Start Cmd، Dependencies) | `liara-agent analyze ./my-project` → JSON Report |
| ۵ | Plan Recommender (Mapping به پلن‌های لیارا، Cost estimation) | Interactive Plan Selection |
| ۶ | Deploy Wizard + Human Approval + Real-time Logs | **End-to-End: `liara-agent deploy` → Live URL** |
| ۷ | Refactor، Tests، Documentation Draft | **Milestone: First Deploy Scenario Ready for Video** |

### ✅ هفته ۲ (روز ۸-۱۴): Operations & Monitoring
| روز | تسک | خروجی |
|-----|------|-------|
| ۸-۹ | Service Management (Start/Stop/Restart/Scale/Config/Env Update) | `liara-agent service <action>` |
| ۱۰-۱۱ | Metrics Collection + Health Checks + Live Dashboard (Terminal UI) | `liara-agent monitor` → Live CPU/RAM/Net |
| ۱۲ | Log Aggregation + Streaming + Search/Filter | `liara-agent logs --follow --grep error` |
| ۱۳ | Alert Engine (Threshold + Anomaly) + Notification | Configurable Alert Rules |
| ۱۴ | Integration Tests، Polish، **Record Scenario 1 & 3 for Video** | **Milestone: Monitoring & Operations Ready** |
### ✅ هفته ۳ (روز ۱۵-۲۱): AI-Powered Troubleshooting (Core Differentiator)
| روز | تسک | خروجی |
|-----|------|-------|
| ۱۵-۱۶ | Error Detection Engine (HTTP 5xx، CrashLoop، OOM، Timeout، Latency) | Auto-detect + Classification |
| ۱۷-۱۸ | Context Collector (Logs window، Metrics snapshot، Deploy history، Config diff) | Rich Context Package |
| ۱۹ | RCA Engine (LLM + Rules) → Prioritized Hypotheses | `liara-agent debug` → Ranked Causes |
| ۲۰ | Remediation Generator (Scale، Restart، Config، Code Patch Suggestion) | Actionable Suggestions |
| ۲۱ | Auto-Remediation + Approval Gates + Verification Loop | **Full Debug→Fix→Verify Cycle** |
| ۲۲ | **Record Scenario 2 (Troubleshooting) for Video** | **Milestone: Intelligent Troubleshooting Ready** |

### ✅ هفته ۴ (روز ۲۲-۲۸): Polish، UX، Video، Docs، Submit
| روز | تسک | خروجی |
|-----|------|-------|
| ۲۲-۲۳ | UX Polish: Onboarding، Persian RTL، Error Messages، Progress UI، Keyboard Shortcuts | Delightful CLI Experience |
| ۲۴ | Security Audit، Credential Handling، Rate Limit Handling، API Limitation Notices | Production-ready |
| ۲۵ | **Complete Video Recording + Editing + Subtitles** | **Final Demo Video (5 min)** |
| ۲۶ | ARCHITECTURE.md + README + Final Testing | **All Deliverables Complete** |
| ۲۷ | Packaging، Release، Upload Video، GitHub Repo Public | **Ready to Submit** |
| ۲۸ | Buffer، Final Review، Submit | 🎉 **DONE** |

---

## ⚠️ ریسک‌ها و استراتژی‌های کاهش (محدث)

| ریسک | احتمال | اثر | استراتژی کاهش |
|------|--------|-----|----------------|
| **Liara API محدود/تغییر/Down** | بالا | بحرانی | **Mock Server از روز ۱**، Contract Tests، Graceful Degradation، Clear User Messages |
| **ویدیو دمو به موقع آماده نشود** | بالا | بحرانی | **Parallel Track: روز ۷، ۱۴، ۲۱ Record می‌کنیم**، نه روز ۲۵! |
| **AI Debugging دقت پایین** | متوسط | بالا | Hybrid: Rule-based First (High Precision) → LLM برای Reasoning، Golden Test Cases |
| **Human-in-the-loop UX گیج‌کننده** | متوسط | بالا | **Design-first**: Paper Prototype → User Test (۲ نفر) → Code |
| **Credential/Security Issues** | پایین | بالا | OS Keychain فقط، Audit Log تمام WriteOps، Pen-test ساده |
| **Cross-platform Bugs (Win/Mac/Linux)** | متوسط | متوسط | CI روی ۳ OS، Bun/Node برای Native Binary، Test Early |

---

## 🎯 معیارهای موفقیت (Mapping دقیق به جدول بارم‌بندی ۳۰۰ امتیازی)

| معیار داوری (امتیاز) | Kهای ماپی شده | Target ما |
|---------------------|---------------|-----------|
| **۱. عملکرد فنی و یکپارچه‌سازی (۱۰۰)** | Deploy Success Rate، API Coverage، Operations Completeness | >۹۵٪ Deploy Success، ۱۰۰٪ Core APIs، Full CRUD Operations |
| **۲. هوشمندی و حل مسئله (۱۰۰)** | RCA Accuracy، Fix Relevance، Verification Rate | >۸۵٪ RCA Accuracy برای Top 20 Error، >۶۰٪ Auto-fix با Approval، ۱۰۰٪ Verification Loop |
| **۳. تجربه کاربری (۵۰)** | Task Completion Time، Approval Clarity، Error Understanding | <۱۰ دقیقه First Deploy، ۱۰۰٪ Approval Clarity، Zero "Unknown Error" |
| **۴. پایداری، نگهداری، امنیت (۵۰)** | Monitoring Coverage، Automation Rate، Security Audit Pass | ۱۰۰٪ Metrics/Logs/Health، >۵۰٪ Ops Automated، Zero Credential Leak |

---

## 📝 نکات کلیدی غیرقابل انعطاف (Non-Negotiables از بریف و ویدئو)

> ✅ **Human-in-the-Loop الزامی** - هیچ عملیات حساسی بدون Approval اجرا نشود
> ✅ **ویدیو دمو ~۵ دقیقه الزامی** - بدون ویدیو = حذف از داوری
> ✅ **ARCHITECTURE.md الزامی** - باید در GitHub باشد
> ✅ **API Limitations شفاف** - اگر endpoint وجود نداشته باشد، به کاربر بگویید
> ✅ **UX > UI** - CLI/Chat با UX عالی بهتر از GUI با UX ضعیف
> ✅ **Real Demo** - ویدیو باید Terminal واقعی نشان دهد، نه اسلاید

---

## 🚀 مراحل بعدی - **تصمیم‌گیری برای شروع**

### تصمیم‌های لازم قبل از کد زدن:
| تصمیم | گزینه‌ها | پیشنهاد من |
|--------|----------|------------|
| **زبان اصلی** | TypeScript (Ink) / Go (Cobra/BubbleTea) / Python (Textual) | **TypeScript + Ink** - سریع‌ترین برای AI SDK + Rich CLI UX |
| **LLM Provider** | OpenAI (GPT-4o) / Anthropic (Claude 3.5) / Local (Ollama) / Hybrid | **Hybrid**: OpenAI Primary + Local Fallback (Cost/Privacy) |
| **Liara API Access** | دارید؟ / نیاز به راهنمای دریافت Token؟ | اگر ندارید: از امروز درخواست دهید (محدودیت ممکن است داشته باشد) |
| **Repo Strategy** | Private اول → Public در پایان / Public از ابتدا | **Private → Public at Submit** (Security، Clean History) |
| **First Milestone Target** | روز ۷: First Deploy Working | **Lock this date** |

---

**آیا این برنامه با دید شما هم‌خوانی دارد؟ کدام تصمیم‌ها را می‌خواهید نهایی کنیم تا از فردا (یا همین الان) کد زدن را آغاز کنیم؟** 🚀