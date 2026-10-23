"""Streamlit dashboard for the Liara SRE Agent.

A thin web wrapper around the existing CLI logic: project list, live
monitoring, and one-click debug with human-in-the-loop approval.
"""

from __future__ import annotations

import asyncio
import os
import time

import streamlit as st
from dotenv import load_dotenv

from liara_agent.ai.engine import AIEngine
from liara_agent.api.client import LiaraClient
from liara_agent.core.debugger import Debugger
from liara_agent.utils.config import get_settings

load_dotenv()

st.set_page_config(
    page_title="Liara SRE Agent",
    page_icon="🛡️",
    layout="wide",
)

# ── Brand palette (matches theme.py) ─────────────────────────
BRAND_PRIMARY = "#00C2FF"
BRAND_ACCENT = "#7C3AED"
BRAND_SUCCESS = "#22C55E"
BRAND_WARNING = "#F59E0B"
BRAND_ERROR = "#EF4444"

st.markdown(
    f"""
    <style>
    .stApp {{ background: #0f172a; color: #e2e8f0; }}
    h1, h2, h3 {{ color: {BRAND_PRIMARY}; }}
    .metric-card {{
        background: #1e293b; border-left: 4px solid {BRAND_PRIMARY};
        padding: 12px; border-radius: 6px; margin: 6px 0;
    }}
    .success {{ border-left-color: {BRAND_SUCCESS}; }}
    .warning {{ border-left-color: {BRAND_WARNING}; }}
    .error   {{ border-left-color: {BRAND_ERROR}; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Banner ───────────────────────────────────────────────────
st.markdown(
    f"""
    <div style="text-align:center; padding: 20px 0;">
      <h1 style="color:{BRAND_PRIMARY}; font-family:monospace;">
        🛡️ LIARA SRE AGENT
      </h1>
      <p style="color:#94a3b8;">Intelligent SRE Agent for Liara PaaS • Task Force</p>
    </div>
    """,
    unsafe_allow_html=True,
)

settings = get_settings()
token = settings.liara_api_token

if not token:
    st.error("❌ LIARA_API_TOKEN تنظیم نشده است. فایل .env را بررسی کنید.")
    st.stop()


# ── Async helpers ────────────────────────────────────────────
def _run(coro):
    """Run an async coroutine from Streamlit's sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Streamlit sometimes has a running loop; use a fresh one.
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
    except RuntimeError:
        pass
    return asyncio.run(coro)


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


# ── Sidebar: project picker ─────────────────────────────────
with st.sidebar:
    st.header("⚙️ تنظیمات")
    if st.button("🔄 بارگذاری مجدد پروژه‌ها", use_container_width=True):
        st.cache_data.clear()

    try:
        projects, offline = _run(fetch_projects())
    except Exception as exc:
        st.error(f"خطا در دریافت پروژه‌ها: {exc}")
        st.stop()

    if offline:
        st.warning("⚠️ داده‌ها از کش آفلاین خوانده شدند.")

    if not projects:
        st.info("هیچ پروژه‌ای یافت نشد.")
        st.stop()

    names = [p.name or p.project_id for p in projects]
    selected = st.selectbox("پروژه", names, index=0)

    st.divider()
    st.caption(f"مدل: `{settings.openai_model}`")
    st.caption(f"تیم: `{os.getenv('LIARA_TEAM_ID', 'personal')}`")


# ── Tabs ────────────────────────────────────────────────────
tab_diag, tab_actions = st.tabs(["🔍 عیب‌یابی هوشمند", "⚡ عملیات"])

# ── Tab 1: diagnose ─────────────────────────────────────────
with tab_diag:
    st.subheader(f"عیب‌یابی پروژه: `{selected}`")

    if st.button("🚀 اجرای عیب‌یابی", type="primary", use_container_width=True):
        with st.spinner("در حال جمع‌آوری کانتکست و تحلیل..."):
            try:
                ctx, diag, offline = _run(fetch_context(selected))
            except Exception as exc:
                st.error(f"خطا: {exc}")
                st.stop()

        if offline:
            st.warning("⚠️ حالت آفلاین — داده‌ها ممکن است قدیمی باشند.")

        # Hypotheses
        st.markdown("### 📋 فرضیات و علل احتمالی")
        for i, h in enumerate(diag.hypotheses, start=1):
            color = BRAND_ERROR if h.probability > 0.7 else BRAND_WARNING if h.probability > 0.4 else BRAND_PRIMARY
            st.markdown(
                f"""<div class="metric-card" style="border-left-color:{color};">
                <b>#{i} {h.title}</b> — {h.probability*100:.0f}%<br>
                <small>دسته: {h.category} • اثر: {h.impact}</small><br>
                <small>{h.explanation}</small>
                </div>""",
                unsafe_allow_html=True,
            )

        # RCA summary
        st.markdown("### 🧠 نتیجه‌گیری")
        st.info(
            f"**علت اصلی:** {diag.root_cause_summary}\n\n"
            f"**درجه اطمینان:** {diag.confidence*100:.0f}%"
        )

        # Approval hash
        if diag.approval_hash:
            remaining = int(diag.approval_expires_at - time.time())
            st.markdown(
                f"### 🔐 کد تأیید عملیات\n"
                f"`{diag.approval_hash}` — اعتبار: {max(remaining,0)} ثانیه"
            )

        # Store diagnosis in session for the action tab
        st.session_state["diag"] = diag
        st.session_state["diag_ts"] = time.time()

# ── Tab 2: actions ──────────────────────────────────────────
with tab_actions:
    st.subheader("عملیات پیشنهادی")

    diag = st.session_state.get("diag")
    if diag is None:
        st.info("ابتدا در تب «عیب‌یابی هوشمند» یک تحلیل اجرا کنید.")
    elif not diag.suggested_remediations:
        st.success("هیچ اقدام اصلاحی فوری نیاز نیست.")
    else:
        # Expiry check
        if diag.approval_expires_at and time.time() > diag.approval_expires_at:
            st.error("❌ کد تأیید منقضی شده است. لطفاً دوباره عیب‌یابی را اجرا کنید.")
        else:
            for i, r in enumerate(diag.suggested_remediations, start=1):
                risk = str(r.risk_level).lower()
                color = BRAND_ERROR if risk in {"high", "critical"} else BRAND_WARNING
                with st.expander(f"#{i} {r.title} (ریسک: {r.risk_level})", expanded=(i == 1)):
                    st.write(r.description)
                    st.caption(f"نوع اقدام: `{r.action_type}` • پارامترها: `{r.parameters}`")

                    confirm = st.checkbox(
                        f"تأیید می‌کنم عملیات «{r.title}» را اجرا کن",
                        key=f"confirm_{i}",
                    )
                    if st.button(f"⚡ اجرا", key=f"exec_{i}", type="primary", disabled=not confirm):
                        with st.spinner("در حال اجرا..."):
                            try:
                                msg = _run(execute_fix(selected, r.action_type, r.parameters))
                                st.success(f"✅ {msg}")
                            except Exception as exc:
                                st.error(f"❌ خطا: {exc}")