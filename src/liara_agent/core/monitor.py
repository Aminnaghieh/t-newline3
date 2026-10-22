"""Monitoring engine for service health, metrics reporting, and alerting."""

from __future__ import annotations

import logging
from typing import Any

from liara_agent.api.client import LiaraClient
from liara_agent.core.alerting import AlertEngine
from liara_agent.models.metrics import AlertEvent, HealthStatus, MetricsReport

logger = logging.getLogger(__name__)


class Monitor:
    """Monitoring engine for checking health and fetching metrics from Liara."""

    def __init__(self, api_client: LiaraClient) -> None:
        self.api = api_client
        self.alert_engine = AlertEngine()

    async def get_health_status(self, project_name: str) -> HealthStatus:
        """Fetch project details and reports to determine comprehensive health."""
        issues: list[str] = []
        recommendations: list[str] = []
        cpu_val = 0.0
        mem_val = 0.0
        status_str = "unknown"
        is_deployed = False

        try:
            proj_data = await self.api.get_project(project_name)
            project_obj = proj_data.project
            status_str = project_obj.status or "unknown"
            is_deployed = bool(project_obj.isDeployed)

            if status_str != "running" and is_deployed:
                issues.append(f"وضعیت برنامه '{status_str}' است")
                recommendations.append("بررسی لاگ‌های رانتایم و در صورت نیاز ری‌استارت سرویس")
        except Exception as e:
            logger.warning("Could not fetch project info for %s: %s", project_name, e)
            issues.append(f"عدم دریافت اطلاعات پروژه: {e}")

        # Try fetching reports
        try:
            reports_data = await self.api.get_reports(project_name, metric="cpu", period="1h")
            # If returns dict with metrics
            if isinstance(reports_data, dict):
                cpu_points = reports_data.get("cpu", [])
                if cpu_points and isinstance(cpu_points, list):
                    last_pt = cpu_points[-1]
                    cpu_val = float(last_pt.get("value", 0.0) if isinstance(last_pt, dict) else last_pt)

                mem_points = reports_data.get("memory", [])
                if mem_points and isinstance(mem_points, list):
                    last_pt = mem_points[-1]
                    mem_val = float(last_pt.get("value", 0.0) if isinstance(last_pt, dict) else last_pt)
        except Exception as e:
            logger.debug("Metrics fetch returned: %s", e)

        # Check metrics against alerts
        metrics_dict = {"cpu": cpu_val, "memory": mem_val}
        alerts = self.alert_engine.check(metrics_dict)
        for alert in alerts:
            issues.append(f"[{alert.severity.upper()}] {alert.message}")
            if alert.metric == "memory" and alert.current_value > 85:
                recommendations.append("ارتقای پلن به منابع رم بیشتر یا بررسی نشت حافظه (Memory Leak)")
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

    async def get_metrics_summary(self, project_name: str, period: str = "1h") -> dict[str, Any]:
        """Fetch and summarize CPU, Memory, Network metrics."""
        try:
            reports = await self.api.get_reports(project_name, metric="cpu", period=period)
            return reports if isinstance(reports, dict) else {"data": reports}
        except Exception as e:
            return {"error": str(e), "cpu": [], "memory": [], "network": []}

    async def check_alerts(self, project_name: str) -> list[AlertEvent]:
        """Run alert checks against current project metrics."""
        health = await self.get_health_status(project_name)
        return self.alert_engine.check({
            "cpu": health.cpu_percent,
            "memory": health.memory_percent,
        })
