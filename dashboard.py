"""Streamlit dashboard for the Liara SRE Agent.

A rich web UI around the Liara SRE Agent: project list, live monitoring,
smart AI/heuristic troubleshooting with human-in-the-loop approval, local code
analyzer, and tamper-evident cryptographic audit trail.
"""

from __future__ import annotations

import asyncio
import html
import json
import os
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from liara_agent.ai.engine import AIEngine
from liara_agent.api.client import LiaraClient
from liara_agent.core.analyzer import ProjectAnalyzer
from liara_agent.core.debugger import DebugContext, Debugger, Hypothesis, Remediation, Diagnosis
from liara_agent.core.planner import PlanRecommender
from liara_agent.models.plans import get_plan_by_id
from liara_agent.storage.audit import audit, AuditLogger
from liara_agent.storage.credentials import resolve_liara_token
from liara_agent.utils.config import get_settings, CONFIG_DIR, AUDIT_LOG_PATH
from liara_agent.utils.constants import ErrorCategory, RiskLevel

# Load private app config first, then local overrides
load_dotenv(CONFIG_DIR / ".env")
load_dotenv()

st.set_page_config(
    page_title="Liara SRE Agent — دستیار هوشمند و تمام‌عیار",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Brand palette ─────────────────────────────────────────────
BRAND_PRIMARY = "#00C2FF"
BRAND_ACCENT = "#7C3AED"
BRAND_SUCCESS = "#22C55E"
BRAND_WARNING = "#F59E0B"
BRAND_ERROR = "#EF4444"

st.markdown(
    f"""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css');
    * {{
        font-family: 'Vazirmatn', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }}
    .stApp {{ background: #0b1120; color: #e2e8f0; }}
    h1, h2, h3 {{ color: {BRAND_PRIMARY}; font-weight: 700; }}
    .metric-card {{
        background: #1e293b; border-left: 4px solid {BRAND_PRIMARY};
        padding: 14px 18px; border-radius: 8px; margin: 8px 0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }}
    .metric-card.success {{ border-left-color: {BRAND_SUCCESS}; }}
    .metric-card.warning {{ border-left-color: {BRAND_WARNING}; }}
    .metric-card.error   {{ border-left-color: {BRAND_ERROR}; }}
    .user-badge {{
        background: #1e293b; border: 1px solid #334155;
        border-radius: 8px; padding: 12px; margin-bottom: 16px;
    }}
    .hash-badge {{
        background: #030712; color: #38bdf8; font-family: monospace;
        padding: 6px 12px; border-radius: 6px; border: 1px solid #1e293b;
        display: inline-block; word-break: break-all;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Banner ───────────────────────────────────────────────────
st.markdown(
    f"""
    <div style="text-align:center; padding: 16px 0 24px 0; border-bottom: 1px solid #1e293b; margin-bottom: 20px;">
      <h1 style="color:{BRAND_PRIMARY}; margin-bottom: 4px;">
        🛡️ LIARA SRE AGENT
      </h1>
      <p style="color:#94a3b8; font-size: 1.1rem; margin: 0;">
        دستیار هوشمند مهندسی قابلیت اطمینان (SRE) و مدیریت زیرساخت پلتفرم ابری لیارا
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

settings = get_settings()
token = resolve_liara_token()

if not token:
    st.error("❌ کلید اتصال لیارا (LIARA_API_TOKEN) تنظیم نشده است. با دستور `liara-agent config set-token` آن را تنظیم فرمایید.")
    st.stop()


# ── Async helpers ────────────────────────────────────────────
def _run(coro):
    """Run an async coroutine from Streamlit's sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
    except RuntimeError:
        pass
    return asyncio.run(coro)


async def fetch_user_info():
    async with LiaraClient(token=token) as client:
        try:
            res = await client.get_user()
            return res.get("user", {}), False
        except Exception:
            return {}, True


async def fetch_projects():
    async with LiaraClient(token=token) as client:
        resp = await client.get_projects()
        return resp.projects, client.is_offline


async def fetch_context(project: str):
    ai = AIEngine(api_key=settings.openai_api_key, model=settings.openai_model) if settings.openai_api_key else None
    async with LiaraClient(token=token) as client:
        dbg = Debugger(api_client=client, ai_engine=ai)
        ctx = await dbg.collect_context(project)
        diag = await dbg.diagnose(ctx)
        return ctx, diag, client.is_offline


async def execute_fix(project: str, action_type: str, parameters: dict):
    async with LiaraClient(token=token) as client:
        if action_type == "restart":
            await client.restart_project(project)
            return "سرویس با موفقیت ری‌استارت شد."
        if action_type == "resize":
            await client.change_plan(project, parameters.get("planID", "small"))
            return f"پلن به {parameters.get('planID')} تغییر یافت."
        if action_type == "scale":
            await client.scale_project(project, parameters.get("scale", 1))
            return f"مقیاس به {parameters.get('scale')} تغییر یافت."
        return "نوع اقدام پشتیبانی نمی‌شود."


# ── Fetch user & project list ────────────────────────────────
user_info, user_err = _run(fetch_user_info())

try:
    projects, offline = _run(fetch_projects())
except Exception as exc:
    projects = []
    offline = True

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.header("👤 حساب کاربری لیارا")
    if user_info:
        fullname = user_info.get("fullname", "امین نقیه")
        email = user_info.get("email", "کاربر لیارا")
        verified = user_info.get("isVerified", True)
        st.markdown(
            f"""
            <div class="user-badge">
                <b style="color:#f8fafc; font-size:1.05rem;">{fullname}</b><br>
                <small style="color:#94a3b8;">✉️ {email}</small><br>
                <small style="color:{BRAND_SUCCESS};">{'✅ حساب احراز هویت شده' if verified else '⚠️ در انتظار تایید'}</small><br>
                <small style="color:#64748b;">🌐 اتصال: api.liara.ir (آنلاین)</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.header("🎯 انتخاب سرویس")
    if st.button("🔄 به‌روزرسانی سرویس‌ها", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    demo_option = "⚡ سرویس نمونه (Demo Microservice)"
    project_options = [p.name or p.project_id for p in projects]
    all_options = [demo_option] + project_options

    selected = st.selectbox("پروژه فعال:", all_options, index=0)

    if offline and selected != demo_option:
        st.warning("⚠️ داده‌ها از کش آفلاین خوانده شده‌اند.")

    st.divider()
    st.caption("🤖 **موتور هوش مصنوعی:**")
    st.caption(f"مدل: `{settings.openai_model}`")
    st.caption(f"کلید OpenAI: {'✅ فعال' if settings.openai_api_key else '⚠️ حالت Heuristic/Rule-based'}")
    st.caption("🔒 **امنیت:** Human-in-the-Loop فعال")


# ── Tabs ────────────────────────────────────────────────────
tab_diag, tab_actions, tab_analyzer, tab_audit = st.tabs([
    "🔍 عیب‌یابی هوشمند (RCA)",
    "⚡ عملیات اصلاحی (HITL)",
    "📦 تحلیل‌گر سورس‌کد محلی",
    "🛡️ زنجیره ممیزی امنیتی",
])

# ── Tab 1: Diagnose ─────────────────────────────────────────
with tab_diag:
    st.subheader(f"عیب‌یابی و ریشه‌یابی خطا برای: `{selected}`")

    is_demo = selected == demo_option

    if is_demo:
        st.info("💡 در حالت دمو می‌توانید سناریوهای مختلف بحران در پروداکشن را شبیه‌سازی کرده و نحوه عملکرد سیستم RCA و فرضیات را مشاهده نمایید.")
        scenario = st.selectbox(
            "انتخاب سناریوی بروز بحران:",
            [
                "💥 نشت حافظه و خطای اتمام رم (OOMKilled Error)",
                "🔌 قطع ارتباط دیتابیس (500 Internal Server Error)",
                "🚫 تداخل پورت وب‌سرور (EADDRINUSE: 8000)",
            ],
            index=0,
        )

    run_diag = st.button("🚀 اجرای عیب‌یابی و ریشه‌یابی خطا (RCA)", type="primary", use_container_width=True)

    if run_diag or "last_diag" in st.session_state:
        if run_diag:
            with st.spinner("در حال جمع‌آوری کانتکست (لاگ‌ها، رخدادها، متریک‌ها) و اجرای تحلیل..."):
                if is_demo:
                    # Construct realistic context based on scenario
                    if "OOM" in scenario:
                        mock_logs = [
                            "2026-10-23 19:30:10 [INFO] Worker spawned pid=412",
                            "2026-10-23 19:31:00 [WARN] Memory usage exceeded 85% threshold (220MB/256MB)",
                            "2026-10-23 19:31:25 [ERROR] Out of Memory: Kill process 412 (python) score 950 or sacrifice child",
                            "2026-10-23 19:31:26 [FATAL] Container killed by Linux OOM Killer. Exit code 137.",
                        ]
                        ctx = DebugContext(
                            project_name="demo-microservice",
                            status="crashed",
                            platform="python",
                            plan_id="micro",
                            recent_logs=mock_logs,
                            recent_events=["ContainerOOMKilled", "CrashLoopBackOff"],
                            metrics_snapshot={"memory_percent": 98.4, "cpu_percent": 45.0},
                            has_env_vars=True,
                        )
                    elif "دیتابیس" in scenario:
                        mock_logs = [
                            "2026-10-23 19:30:00 [INFO] Connecting to postgresql://liara-db:5432/app",
                            "2026-10-23 19:30:05 [ERROR] asyncpg.exceptions.ConnectionDoesNotExistError: connection refused",
                            "2026-10-23 19:30:06 [ERROR] Internal Server Error 500: Database Connection Refused",
                            "2026-10-23 19:30:12 [WARN] Health check probe failed 3 times in a row",
                        ]
                        ctx = DebugContext(
                            project_name="demo-microservice",
                            status="running_unhealthy",
                            platform="python",
                            plan_id="small",
                            recent_logs=mock_logs,
                            recent_events=["UnhealthyProbeFailed"],
                            metrics_snapshot={"memory_percent": 35.0, "cpu_percent": 12.0},
                            has_env_vars=True,
                        )
                    else:
                        mock_logs = [
                            "2026-10-23 19:30:00 [INFO] Starting uvicorn worker...",
                            "2026-10-23 19:30:01 [ERROR] [Errno 98] Address already in use: 0.0.0.0:8000",
                            "2026-10-23 19:30:02 [FATAL] Server failed to bind to port 8000",
                        ]
                        ctx = DebugContext(
                            project_name="demo-microservice",
                            status="crashed",
                            platform="python",
                            plan_id="micro",
                            recent_logs=mock_logs,
                            recent_events=["BindPortFailed"],
                            metrics_snapshot={"memory_percent": 20.0, "cpu_percent": 5.0},
                            has_env_vars=True,
                        )

                    async def run_mock_dbg():
                        async with LiaraClient(token=token) as client:
                            ai = AIEngine(api_key=settings.openai_api_key, model=settings.openai_model) if settings.openai_api_key else None
                            dbg = Debugger(api_client=client, ai_engine=ai)
                            return await dbg.diagnose(ctx)

                    diag = _run(run_mock_dbg())
                    st.session_state["last_diag"] = diag
                    st.session_state["diag_target"] = selected
                    st.session_state["diag_context"] = ctx
                else:
                    try:
                        ctx, diag, offline = _run(fetch_context(selected))
                        st.session_state["last_diag"] = diag
                        st.session_state["diag_target"] = selected
                        st.session_state["diag_context"] = ctx
                    except Exception as exc:
                        st.error(f"خطا در تحلیل: {exc}")
                        diag = None

        diag = st.session_state.get("last_diag")
        if diag:
            # Display Hypotheses
            st.markdown("### 📋 فرضیات و علل احتمالی شناسایی‌شده")
            for i, h in enumerate(diag.hypotheses, start=1):
                prob = h.probability
                color = BRAND_ERROR if prob > 0.7 else BRAND_WARNING if prob > 0.4 else BRAND_PRIMARY
                title = html.escape(str(h.title))
                category = html.escape(str(h.category))
                impact = html.escape(str(h.impact))
                explanation = html.escape(str(h.explanation))
                st.markdown(
                    f"""<div class="metric-card" style="border-left-color:{color};">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <b style="font-size:1.1rem; color:#f8fafc;">#{i} {title}</b>
                        <span style="background:{color}; color:#000; font-weight:bold; padding:2px 8px; border-radius:12px; font-size:0.85rem;">
                            احتمال وقوع: {prob*100:.0f}%
                        </span>
                    </div>
                    <div style="margin-top:6px; color:#cbd5e1; font-size:0.95rem;">
                        <b>دسته:</b> <span style="color:#38bdf8;">{category}</span> • <b>اثر:</b> {impact}
                    </div>
                    <div style="margin-top:6px; color:#94a3b8; font-size:0.9rem;">
                        {explanation}
                    </div>
                    </div>""",
                    unsafe_allow_html=True,
                )

            # RCA summary
            st.markdown("### 🧠 جمع‌بندی تحلیل ریشه‌ای (Root Cause Analysis)")
            st.info(
                f"**علت اصلی:** {diag.root_cause_summary}\n\n"
                f"**میزان اطمینان تحلیل:** {diag.confidence*100:.0f}%"
            )

            # Approval hash & HITL
            if diag.approval_hash:
                remaining = int(diag.approval_expires_at - time.time())
                st.markdown(
                    f"### 🔐 شناسه رمزنگاری تایید عملیات (Cryptographic HITL Hash)\n"
                    f"<div class='hash-badge'>🔑 {diag.approval_hash}</div><br>"
                    f"<small style='color:#94a3b8;'>اعتبار کد تایید: {max(remaining, 0)} ثانیه (تضمین عدم دستکاری دستورات و Bind به پروژه)</small>",
                    unsafe_allow_html=True,
                )


# ── Tab 2: Remediations ─────────────────────────────────────
with tab_actions:
    st.subheader("⚡ عملیات اصلاحی با تایید انسانی (Human-in-the-Loop Remediation)")

    diag = st.session_state.get("last_diag")
    if diag is None:
        st.info("جهت مشاهده راهکارهای اصلاحی، ابتدا در تب «عیب‌یابی هوشمند» دکمه عیب‌یابی را اجرا فرمایید.")
    elif not diag.suggested_remediations:
        st.success("✅ سرویس در وضعیت پایدار است و اقدام اصلاحی اضطراری نیاز نیست.")
    else:
        for i, r in enumerate(diag.suggested_remediations, start=1):
            risk = str(r.risk_level).lower()
            risk_label = "کم‌ریسک (Low)" if risk == "low" else "متوسط (Medium)" if risk == "medium" else "پرریسک (High)"
            border_color = BRAND_SUCCESS if risk == "low" else BRAND_WARNING if risk == "medium" else BRAND_ERROR

            with st.expander(f"راهکار #{i}: {r.title} — [سطح ریسک: {risk_label}]", expanded=(i == 1)):
                st.write(f"**شرح اقدام:** {r.description}")
                st.write(f"**دستور اجرایی:** `{r.action_type}` با پارامترهای `{r.parameters}`")

                confirm = st.checkbox(
                    f"من به عنوان اپراتور، اجرای عملیات «{r.title}» روی {selected} را صریحاً تایید می‌کنم.",
                    key=f"confirm_{i}",
                )

                if st.button(f"⚡ اجرای عملیات اصلاحی", key=f"exec_{i}", type="primary", disabled=not confirm):
                    with st.spinner("در حال اعمال اصلاحیه و ثبت در زنجیره لاگ ممیزی..."):
                        if is_demo:
                            time.sleep(0.8)
                            msg = f"عملیات «{r.title}» با موفقیت در محیط شبیه‌سازی اعمال شد."
                            audit(
                                action=f"remediation.{r.action_type}",
                                target="demo-microservice",
                                risk_level=risk,
                                status="success",
                                details={"parameters": r.parameters, "approval_hash": diag.approval_hash},
                            )
                            st.success(f"✅ {msg}")
                        else:
                            try:
                                msg = _run(execute_fix(selected, r.action_type, r.parameters))
                                audit(
                                    action=f"remediation.{r.action_type}",
                                    target=selected,
                                    risk_level=risk,
                                    status="success",
                                    details={"parameters": r.parameters, "approval_hash": diag.approval_hash},
                                )
                                st.success(f"✅ {msg}")
                            except Exception as exc:
                                audit(
                                    action=f"remediation.{r.action_type}",
                                    target=selected,
                                    risk_level=risk,
                                    status="error",
                                    details={"error": str(exc)[:200]},
                                )
                                st.error(f"❌ خطا در اجرا: {exc}")


# ── Tab 3: Local Code Analyzer ──────────────────────────────
with tab_analyzer:
    st.subheader("📦 تحلیل‌گر هوشمند سورس‌کد و پیشنهاد پلن (Project Analyzer)")
    st.write("این ابزار کد منبع پروژه محلی شما را اسکن کرده، زبان، فریم‌ورک و پورت وب‌سرور را تشخیص داده و بهینه‌ترین پلن لیارا را تخمین می‌زند.")

    sample_dir = Path(__file__).parent / "sample_app"
    default_path = str(sample_dir if sample_dir.exists() else Path.cwd())

    path_input = st.text_input("مسیر دایرکتوری سورس پروژه:", value=default_path)

    if st.button("🔍 اسکن و تحلیل خودکار سورس‌کد", type="primary"):
        target_path = Path(path_input).expanduser().resolve()
        if not target_path.exists() or not target_path.is_dir():
            st.error("❌ مسیر وارد شده معتبر یا یک پوشه نیست.")
        else:
            with st.spinner("در حال بررسی فایل‌ها، وابستگی‌ها و ساختار پروژه..."):
                try:
                    analyzer = ProjectAnalyzer(target_path)
                    analysis = analyzer.analyze()
                    recommender = PlanRecommender()
                    rec = recommender.recommend(analysis)

                    plan_obj = get_plan_by_id(rec.plan_id)

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("زبان / پلتفرم", analysis.platform.upper())
                    col2.metric("فریم‌ورک شناسایی‌شده", (analysis.framework or "نامشخص").capitalize())
                    col3.metric("پورت وب‌سرور", str(analysis.port or 8000))
                    col4.metric("حجم سورس", f"{analysis.project_size_mb:.2f} MB")

                    st.markdown("---")
                    st.markdown(f"### 💡 پلن پیشنهادی ایجنت: `{rec.plan_id}`")
                    st.write(f"**دلیل پیشنهاد:** {', '.join(rec.reasons)}")

                    if plan_obj:
                        st.markdown(
                            f"""
                            <div class="metric-card success">
                                <b>مشخصات سخت‌افزاری پلن {plan_obj.name}:</b><br>
                                ⚡ پردازنده: <b>{plan_obj.cpu} Core</b> • 💾 حافظه رم: <b>{plan_obj.ram_mb} MB</b><br>
                                💰 هزینه ماهیانه: <b>{plan_obj.monthly_price_irr:,.0f} ریال</b> (اقتصادی‌ترین انتخاب)
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    st.markdown("### 📋 فایل‌های شناسایی‌شده برای استقرار:")
                    files_display = analysis.detected_files[:10]
                    for f in files_display:
                        st.text(f"  • {f}")
                    if len(analysis.detected_files) > 10:
                        st.caption(f"... و {len(analysis.detected_files) - 10} فایل دیگر")

                    st.success("✅ پروژه آماده استقرار است. می‌توانید با دستور `liara-agent init` پروژه را مستقیماً مستقر فرمایید.")
                except Exception as exc:
                    st.error(f"خطا در تحلیل پروژه: {exc}")


# ── Tab 4: Audit Trail ──────────────────────────────────────
with tab_audit:
    st.subheader("🛡️ زنجیره لاگ ممیزی ضد دستکاری (Cryptographic HMAC Audit Trail)")
    st.write("تمامی عملیات حساس و تغییرات سیستمی با الگوریتم HMAC-SHA256 به صورت زنجیره‌ای ثبت می‌شوند تا امکان هرگونه دستکاری یا جعل سوابق غیرممکن گردد.")

    logger = AuditLogger()
    ok, verify_msg = logger.verify()

    if ok:
        st.markdown(
            f"""
            <div class="metric-card success">
                <b style="color:{BRAND_SUCCESS}; font-size:1.1rem;">✅ زنجیره هش ممیزی معتبر و کاملاً دست‌نخورده است.</b><br>
                <small style="color:#cbd5e1;">{verify_msg}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.error(f"❌ نقض یکپارچگی لاگ ممیزی: {verify_msg}")

    # Read and render audit entries
    if AUDIT_LOG_PATH.exists():
        records = []
        try:
            with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
        except Exception as exc:
            st.warning(f"خطا در خواندن فایل لاگ: {exc}")

        if records:
            st.markdown(f"**تعداد کل رکوردهای ممیزی ثبت شده:** `{len(records)}`")
            for r in reversed(records[-10:]):
                status_color = BRAND_SUCCESS if r.get("status") in {"success", "ok"} else BRAND_WARNING
                st.markdown(
                    f"""
                    <div style="background:#1e293b; border-left:3px solid {status_color}; padding:8px 14px; margin:6px 0; border-radius:4px;">
                        <span style="color:#94a3b8; font-family:monospace; font-size:0.85rem;">{r.get('timestamp', '')}</span> — 
                        <b style="color:#f8fafc;">[{r.get('action', '')}]</b> روی <code>{r.get('target', '')}</code> — 
                        <span style="color:{status_color}; font-size:0.85rem;">وضعیت: {r.get('status', '')}</span><br>
                        <small style="color:#64748b; font-family:monospace;">HASH: {r.get('hash', '')[:24]}... (زنجیر شده با HMAC-SHA256)</small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("هنوز رکوردی در لاگ ممیزی ثبت نشده است.")
    else:
        st.info("فایل لاگ ممیزی هنوز ایجاد نشده است.")
