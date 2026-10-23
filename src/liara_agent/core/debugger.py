"""Intelligent troubleshooting engine — RCA, context collection, and remediation."""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from liara_agent.api.client import LiaraClient
from liara_agent.utils.constants import ErrorCategory, RiskLevel

logger = logging.getLogger(__name__)


class DebugContext(BaseModel):
    """Context bundle collected for intelligent diagnosis."""
    project_name: str
    status: str = "unknown"
    platform: str = ""
    plan_id: str = ""
    recent_logs: list[str] = Field(default_factory=list)
    recent_events: list[str] = Field(default_factory=list)
    metrics_snapshot: dict[str, float] = Field(default_factory=dict)
    has_env_vars: bool = False


class Hypothesis(BaseModel):
    """Diagnosed possible root cause hypothesis."""
    title: str
    probability: float = Field(..., ge=0.0, le=1.0)
    category: str = ErrorCategory.UNKNOWN
    explanation: str
    impact: str


class Remediation(BaseModel):
    """Suggested actionable fix."""
    id: str
    title: str
    action_type: str  # restart, scale, resize
    description: str
    risk_level: RiskLevel = RiskLevel.MEDIUM
    auto_executable: bool = True
    parameters: dict[str, Any] = Field(default_factory=dict)

    def compute_hash(self) -> str:
        """Deterministic SHA-256 of this remediation's payload.

        Used by the HITL approval gate: the hash shown to the user must
        match the hash of the action that is actually executed, so a
        tampered or stale approval cannot be replayed.
        """
        payload = (
            f"{self.id}|{self.action_type}|"
            f"{sorted(self.parameters.items())}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class Diagnosis(BaseModel):
    """Complete diagnostic report."""
    root_cause_summary: str
    confidence: float
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    suggested_remediations: list[Remediation] = Field(default_factory=list)
    approval_hash: str = ""
    approval_expires_at: float = 0.0


class FixResult(BaseModel):
    """Result of executing a remediation action."""
    success: bool
    action: str
    message: str
    verification_needed: bool = True


def _normalize_ai_diagnosis(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize the LLM's JSON output to match the ``Diagnosis`` schema."""
    normalized: dict[str, Any] = {}

    # ── root cause summary ──
    normalized["root_cause_summary"] = str(
        raw.get("root_cause_summary")
        or raw.get("summary")
        or raw.get("root_cause")
        or raw.get("description")
        or "علت اصلی توسط تحلیل هوش مصنوعی مشخص نشد."
    )

    # ── confidence ──
    conf_raw = raw.get("confidence", raw.get("probability", 0.5))
    try:
        conf = float(conf_raw)
        if conf > 1.0:
            conf = conf / 100.0
    except (TypeError, ValueError):
        conf = 0.5
    normalized["confidence"] = max(0.0, min(1.0, conf))

    # ── hypotheses ──
    raw_hyps = raw.get("hypotheses") or raw.get("causes") or []
    hypotheses: list[dict[str, Any]] = []
    if isinstance(raw_hyps, list):
        for idx, h in enumerate(raw_hyps, start=1):
            if not isinstance(h, dict):
                continue
            prob_raw = h.get("probability", h.get("confidence", 0.5))
            try:
                prob = float(prob_raw)
                if prob > 1.0:
                    prob = prob / 100.0
            except (TypeError, ValueError):
                prob = 0.5
            hypotheses.append({
                "title": str(
                    h.get("title")
                    or h.get("name")
                    or h.get("root_cause_summary")
                    or h.get("summary")
                    or f"فرضیه {idx}"
                ),
                "probability": max(0.0, min(1.0, prob)),
                "category": str(h.get("category") or ErrorCategory.UNKNOWN),
                "explanation": str(
                    h.get("explanation")
                    or h.get("description")
                    or h.get("details")
                    or h.get("summary")
                    or "توضیحاتی ارائه نشده است."
                ),
                "impact": str(
                    h.get("impact")
                    or h.get("effect")
                    or h.get("consequence")
                    or "اثر نامشخص"
                ),
            })
    normalized["hypotheses"] = hypotheses

    # ── suggested remediations ──
    raw_rems = raw.get("suggested_remediations") or raw.get("remediations") or []
    remediations: list[dict[str, Any]] = []
    if isinstance(raw_rems, list):
        for idx, r in enumerate(raw_rems, start=1):
            if not isinstance(r, dict):
                continue
            remediations.append({
                "id": str(r.get("id") or f"fix_{idx}"),
                "title": str(r.get("title") or r.get("name") or f"راهکار {idx}"),
                "action_type": str(r.get("action_type") or r.get("action") or "restart"),
                "description": str(r.get("description") or r.get("details") or ""),
                "risk_level": str(r.get("risk_level") or RiskLevel.MEDIUM),
                "auto_executable": bool(r.get("auto_executable", True)),
                "parameters": r.get("parameters") or {},
            })
    normalized["suggested_remediations"] = remediations

    return normalized


def _attach_approval(diag: Diagnosis) -> Diagnosis:
    """Attach a hash + 15-minute expiry to the first remediation."""
    if diag.suggested_remediations:
        primary = diag.suggested_remediations[0]
        diag.approval_hash = primary.compute_hash()
        diag.approval_expires_at = time.time() + 15 * 60
    return diag


class Debugger:
    """Collects runtime state, runs rule-based and AI-assisted RCA, and provides fixes."""

    def __init__(self, api_client: LiaraClient, ai_engine: Any = None) -> None:
        self.api = api_client
        self.ai = ai_engine

    async def collect_context(self, project_name: str) -> DebugContext:
        """Collect logs, metrics, status, and events into a unified context."""
        status = "unknown"
        platform = ""
        plan_id = ""
        has_envs = False

        try:
            proj_data = await self.api.get_project(project_name)
            p = proj_data.project
            status = p.status or "unknown"
            platform = p.type or ""
            plan_id = p.planID or ""
            has_envs = bool(p.envs)
        except Exception as e:
            logger.warning("Could not fetch project info: %s", e)

        logs_list: list[str] = []
        try:
            since_ts = int(time.time()) - (30 * 60)
            logs_resp = await self.api.get_logs(project_name, since=since_ts)
            if hasattr(logs_resp, "logs") and logs_resp.logs:
                logs_list = [f"[{log.timestamp or ''}] {log.message}" for log in logs_resp.logs[-40:]]
            elif isinstance(logs_resp, list):
                logs_list = [str(x) for x in logs_resp[-40:]]
        except Exception as e:
            logger.debug("Could not fetch logs: %s", e)

        events_list: list[str] = []
        try:
            ev_resp = await self.api.get_events(project_name)
            if hasattr(ev_resp, "events") and ev_resp.events:
                events_list = [f"[{ev.status}] {ev.message}" for ev in ev_resp.events[-15:]]
        except Exception as e:
            logger.debug("Could not fetch events: %s", e)

        return DebugContext(
            project_name=project_name,
            status=status,
            platform=platform,
            plan_id=plan_id,
            recent_logs=logs_list,
            recent_events=events_list,
            metrics_snapshot={},
            has_env_vars=has_envs,
        )

    async def diagnose(self, context: DebugContext) -> Diagnosis:
        """Run diagnosis — uses AI Engine if available, with robust heuristic fallback."""
        if self.ai:
            try:
                ai_result = await self.ai.troubleshoot(context.model_dump())
                if ai_result and isinstance(ai_result, dict):
                    normalized = _normalize_ai_diagnosis(ai_result)
                    diag = Diagnosis(**normalized)
                    return _attach_approval(diag)
            except Exception as e:
                logger.warning("AI diagnosis fallback triggered: %s", e)

        # Heuristic / Rule-based RCA fallback
        logs_text = " \n ".join(context.recent_logs).lower()
        hypotheses: list[Hypothesis] = []
        remediations: list[Remediation] = []

        if "oom" in logs_text or "out of memory" in logs_text or "killed" in logs_text:
            hypotheses.append(
                Hypothesis(
                    title="خطای اتمام حافظه رم (OOM / Out of Memory)",
                    probability=0.92,
                    category=ErrorCategory.RESOURCE_EXHAUSTION,
                    explanation="کانتینر به دلیل عبور مصرف رم از سقف پلن فعلی توسط هسته لینوکس متوقف (Killed) شده است.",
                    impact="قطعی کامل اپلیکیشن و خطای 502/503 برای کاربران",
                )
            )
            remediations.append(
                Remediation(
                    id="fix_resize_ram",
                    title="ارتقای پلن به منابع رم بالاتر",
                    action_type="resize",
                    description="ارتقای پلن به پلن بالاتر جهت تامین حافظه مورد نیاز",
                    risk_level=RiskLevel.HIGH,
                    parameters={"planID": "small" if context.plan_id == "micro" else "medium"},
                )
            )
            remediations.append(
                Remediation(
                    id="fix_restart",
                    title="راه‌اندازی مجدد (Restart) موقت",
                    action_type="restart",
                    description="راه‌اندازی مجدد برنامه برای آزادسازی موقت رم",
                    risk_level=RiskLevel.MEDIUM,
                )
            )

        if "eaddrinuse" in logs_text or "address already in use" in logs_text:
            hypotheses.append(
                Hypothesis(
                    title="تداخل در پورت اتصال (Port Conflict)",
                    probability=0.88,
                    category=ErrorCategory.CONFIG_ERROR,
                    explanation="پورت مشخص شده توسط پروسس دیگری اشغال شده یا در کانتینر بسته نشده است.",
                    impact="عدم راه‌اندازی وب‌سرور",
                )
            )
            remediations.append(
                Remediation(
                    id="fix_restart",
                    title="ری‌استارت کانتینر برای بستن پورت‌های قبلی",
                    action_type="restart",
                    description="ری‌استارت کل پاد کانتینر در لیارا",
                    risk_level=RiskLevel.MEDIUM,
                )
            )

        if "connection refused" in logs_text or "etimedout" in logs_text or "database" in logs_text:
            hypotheses.append(
                Hypothesis(
                    title="عدم برقراری اتصال به دیتابیس یا سرویس جانبی",
                    probability=0.80,
                    category=ErrorCategory.NETWORK_ISSUE,
                    explanation="برنامه نمی‌تواند به دیتابیس یا سرویس وابسته وصل شود. متغیرهای محیطی اتصال یا فایروال را بررسی کنید.",
                    impact="بروز ارور 500 در کوئری‌ها",
                )
            )

        if not hypotheses:
            hypotheses.append(
                Hypothesis(
                    title="خطای احتمالی در زمان راه‌اندازی یا کد برنامه",
                    probability=0.65,
                    category=ErrorCategory.CODE_BUG,
                    explanation=f"وضعیت فعلی برنامه '{context.status}' است و لاگ‌های خطا نیاز به بررسی دستی دارند.",
                    impact="اختلال در عملکرد نرم‌افزار",
                )
            )
            remediations.append(
                Remediation(
                    id="fix_restart",
                    title="راه‌اندازی مجدد سرویس (Restart)",
                    action_type="restart",
                    description="یک بار ری‌استارت نرم‌افزاری کانتینر",
                    risk_level=RiskLevel.MEDIUM,
                )
            )

        diag = Diagnosis(
            root_cause_summary=hypotheses[0].title,
            confidence=hypotheses[0].probability,
            hypotheses=hypotheses,
            suggested_remediations=remediations,
        )
        return _attach_approval(diag)

    async def execute_fix(self, project_name: str, remediation: Remediation) -> FixResult:
        """Execute the chosen remediation action."""
        try:
            if remediation.action_type == "restart":
                await self.api.restart_project(project_name)
                return FixResult(
                    success=True,
                    action="restart",
                    message="سرویس با موفقیت ری‌استارت شد.",
                )
            elif remediation.action_type == "resize":
                plan_id = remediation.parameters.get("planID", "small")
                await self.api.change_plan(project_name, plan_id)
                return FixResult(
                    success=True,
                    action="resize",
                    message=f"پلن پروژه با موفقیت به '{plan_id}' تغییر یافت.",
                )
            elif remediation.action_type == "scale":
                scale = remediation.parameters.get("scale", 1)
                await self.api.scale_project(project_name, scale)
                return FixResult(
                    success=True,
                    action="scale",
                    message=f"مقیاس پروژه با موفقیت به {scale} تغییر یافت.",
                )
            else:
                return FixResult(
                    success=False,
                    action=remediation.action_type,
                    message=f"نوع اقدام '{remediation.action_type}' به صورت خودکار پشتیبانی نمی‌شود.",
                )
        except Exception as e:
            return FixResult(
                success=False,
                action=remediation.action_type,
                message=f"خطا در اجرای اصلاح: {e}",
            )