"""Monitoring engine for service health, metrics reporting, and alerting."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from liara_agent.api.client import LiaraClient
from liara_agent.core.alerting import AlertEngine
from liara_agent.models.metrics import (
    AlertEvent,
    HealthStatus,
    MetricDataPoint,
    MetricsReport,
    MonitorSnapshot,
)
from liara_agent.utils.errors import LiaraAgentError, ProjectNotFoundError

logger = logging.getLogger(__name__)

REPORT_METRICS = ("cpu", "memory", "network")


def _last_value(series: list[MetricDataPoint]) -> float:
    """Return the value of the last data point in a series, or ``0.0``."""
    if not series:
        return 0.0
    return float(series[-1].value)


class Monitor:
    """Monitoring engine for checking health and fetching metrics from Liara."""

    def __init__(self, api_client: LiaraClient) -> None:
        self.api = api_client
        self.alert_engine = AlertEngine()

    # ──────────────────────────────────────────────────────────────
    #  Snapshot (rich data for the dashboard)
    # ──────────────────────────────────────────────────────────────

    async def get_snapshot(
        self, project_name: str, period: str = "1h"
    ) -> MonitorSnapshot:
        """Build a complete, normalized monitoring snapshot for the dashboard.

        Failure handling:

        * ``ProjectNotFoundError`` propagates so the CLI can print a friendly
          message (an unknown project is a hard failure).
        * Report-fetch failures degrade gracefully — the affected series stay
          empty and an issue is recorded; the dashboard still renders.

        A critical alert marks the snapshot unhealthy; warning alerts are
        surfaced but do not flip the health flag.
        """
        issues: list[str] = []
        recommendations: list[str] = []
        status_str = "unknown"
        is_deployed = False
        plan_id = ""
        scale = 0

        # 1) Project info — an unknown project is a hard failure.
        try:
            project_obj = (await self.api.get_project(project_name)).project
            status_str = project_obj.status or "unknown"
            is_deployed = bool(project_obj.isDeployed)
            plan_id = project_obj.planID or ""
            scale = project_obj.scale or 0

            if status_str != "running":
                issues.append(f"وضعیت برنامه '{status_str}' است (به‌جای running)")
                recommendations.append(
                    "بررسی لاگ‌های رانتایم و در صورت نیاز ری‌استارت سرویس"
                )
        except ProjectNotFoundError:
            raise
        except LiaraAgentError as exc:
            issues.append(f"عدم دریافت اطلاعات پروژه: {exc.message}")
        except Exception as e:  # pragma: no cover - unexpected transport errors
            logger.warning("Could not fetch project info for %s: %s", project_name, e)
            issues.append(f"عدم دریافت اطلاعات پروژه: {e}")

        # 2) Reports in parallel — Liara API accepts one metric per call.
        cpu_r, mem_r, net_r = await asyncio.gather(
            _fetch_report(self.api, project_name, "cpu", period),
            _fetch_report(self.api, project_name, "memory", period),
            _fetch_report(self.api, project_name, "network", period),
        )

        cpu_series = cpu_r.cpu if cpu_r else []
        mem_series = mem_r.memory if mem_r else []
        net_rx_series = (net_r.network_rx if net_r else []) or []
        net_tx_series = (net_r.network_tx if net_r else []) or []

        if cpu_r is None or mem_r is None or net_r is None:
            issues.append("دریافت برخی متریک‌ها ناموفق بود — مقادیر ممکن است غیرواقعی باشند")

        cpu_val = _last_value(cpu_series)
        mem_val = _last_value(mem_series)

        # 3) Alerts
        alerts = self.alert_engine.check({"cpu": cpu_val, "memory": mem_val})
        for alert in alerts:
            if alert.metric == "memory" and alert.current_value > 85:
                recommendations.append("ارتقای پلن یا بررسی نشت حافظه (Memory Leak)")
            if alert.metric == "cpu" and alert.current_value > 80:
                recommendations.append("ارتقای پلن به CPU بیشتر یا فعال‌سازی کلاستر/اسکیل")

        has_critical = any(a.severity == "critical" for a in alerts)
        is_healthy = status_str == "running" and not issues and not has_critical

        return MonitorSnapshot(
            project_name=project_name,
            status=status_str,
            is_deployed=is_deployed,
            is_healthy=is_healthy,
            plan_id=plan_id,
            scale=scale,
            cpu_percent=cpu_val,
            memory_percent=mem_val,
            cpu_series=cpu_series,
            memory_series=mem_series,
            net_rx_series=net_rx_series,
            net_tx_series=net_tx_series,
            alerts=alerts,
            issues=issues,
            recommendations=recommendations,
            fetched_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        )

    # ──────────────────────────────────────────────────────────────
    #  Health status (compat API)
    # ──────────────────────────────────────────────────────────────

    async def get_health_status(self, project_name: str) -> HealthStatus:
        """Fetch project details and reports to determine comprehensive health."""
        issues: list[str] = []
        recommendations: list[str] = []
        status_str = "unknown"
        is_deployed = False

        try:
            project_obj = (await self.api.get_project(project_name)).project
            status_str = project_obj.status or "unknown"
            is_deployed = bool(project_obj.isDeployed)

            if status_str != "running":
                issues.append(f"وضعیت برنامه '{status_str}' است")
                recommendations.append("بررسی لاگ‌های رانتایم و در صورت نیاز ری‌استارت سرویس")
        except Exception as e:
            logger.warning("Could not fetch project info for %s: %s", project_name, e)
            issues.append(f"عدم دریافت اطلاعات پروژه: {e}")

        cpu_r, mem_r = await asyncio.gather(
            _fetch_report(self.api, project_name, "cpu", "1h"),
            _fetch_report(self.api, project_name, "memory", "1h"),
        )
        cpu_val = _last_value(cpu_r.cpu) if cpu_r else 0.0
        mem_val = _last_value(mem_r.memory) if mem_r else 0.0

        # Check metrics against alerts
        metrics_dict = {"cpu": cpu_val, "memory": mem_val}
        alerts = self.alert_engine.check(metrics_dict)
        for alert in alerts:
            issues.append(f"[{alert.severity.upper()}] {alert.message}")
            if alert.metric == "memory" and alert.current_value > 85:
                recommendations.append(
                    "ارتقای پلن به منابع رم بیشتر یا بررسی نشت حافظه (Memory Leak)"
                )
            if alert.metric == "cpu" and alert.current_value > 80:
                recommendations.append("ارتقای پلن به CPU بیشتر یا فعال‌سازی کلاستر/اسکیل")

        is_healthy = len(issues) == 0 and status_str == "running"

        return HealthStatus(
            is_healthy=is_healthy,
            cpu_percent=cpu_val,
            memory_percent=mem_val,
            is_deployed=is_deployed,
            status=status_str,
            issues=issues,
            recommendations=recommendations,
        )

    # ──────────────────────────────────────────────────────────────
    #  Misc
    # ──────────────────────────────────────────────────────────────

    async def get_metrics_summary(
        self, project_name: str, period: str = "1h"
    ) -> dict[str, list[dict]]:
        """Fetch and summarize CPU/Memory/Network time-series as plain dicts."""
        try:
            cpu_r, mem_r, net_r = await asyncio.gather(
                _fetch_report(self.api, project_name, "cpu", period),
                _fetch_report(self.api, project_name, "memory", period),
                _fetch_report(self.api, project_name, "network", period),
            )
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("Metrics summary fetch failed: %s", e)
            return {"cpu": [], "memory": [], "network_rx": [], "network_tx": []}

        return {
            "cpu": _series_dicts(cpu_r, key="cpu"),
            "memory": _series_dicts(mem_r, key="memory"),
            "network_rx": _series_dicts(net_r, key="network_rx"),
            "network_tx": _series_dicts(net_r, key="network_tx"),
        }

    async def check_alerts(self, project_name: str) -> list[AlertEvent]:
        """Run alert checks against current project metrics."""
        health = await self.get_health_status(project_name)
        return self.alert_engine.check({
            "cpu": health.cpu_percent,
            "memory": health.memory_percent,
        })


async def _fetch_report(
    api: LiaraClient, project_name: str, metric: str, period: str
) -> MetricsReport | None:
    """Fetch a single metrics report, returning ``None`` on any failure."""
    try:
        return await api.get_reports(project_name, metric=metric, period=period)
    except Exception as e:
        logger.debug("Report fetch failed (%s/%s): %s", project_name, metric, e)
        return None


def _series_dicts(report: MetricsReport | None, key: str) -> list[dict]:
    """Convert one report's series to plain dicts (empty list on failure)."""
    if report is None:
        return []
    points = getattr(report, key, []) or []
    return [p.model_dump() for p in points]
