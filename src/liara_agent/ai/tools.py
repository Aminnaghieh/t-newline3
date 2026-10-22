"""OpenAI function calling schemas and tool execution engine with risk awareness."""

from __future__ import annotations

import json
from typing import Any, Callable

from liara_agent.api.client import LiaraClient
from liara_agent.models.deploy import ReleaseRequest
from liara_agent.models.project import ProjectCreate, ProjectUpdateEnvs, ProjectEnv
from liara_agent.utils.constants import RiskLevel
from liara_agent.utils.errors import ApprovalDeniedError


# ─── OpenAI Tool Definitions ─────────────────────────────────

LIARA_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "liara_list_projects",
            "description": "لیست تمام پروژه‌ها و اپلیکیشن‌های فعال کاربر در پلتفرم لیارا",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        "risk_level": RiskLevel.LOW,
    },
    {
        "type": "function",
        "function": {
            "name": "liara_get_project",
            "description": "دریافت جزئیات کامل و وضعیت یک پروژه در لیارا",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "نام انگلیسی پروژه"},
                },
                "required": ["name"],
            },
        },
        "risk_level": RiskLevel.LOW,
    },
    {
        "type": "function",
        "function": {
            "name": "liara_restart_project",
            "description": "راه‌اندازی مجدد (Restart) پادها و کانتینر پروژه در لیارا",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "نام پروژه"},
                },
                "required": ["name"],
            },
        },
        "risk_level": RiskLevel.MEDIUM,
    },
    {
        "type": "function",
        "function": {
            "name": "liara_scale_project",
            "description": "روشن یا خاموش کردن اپلیکیشن در لیارا (Scale on/off)",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "نام پروژه"},
                    "scale": {"type": "integer", "enum": [0, 1], "description": "1 برای روشن و 0 برای خاموش کردن"},
                },
                "required": ["name", "scale"],
            },
        },
        "risk_level": RiskLevel.HIGH,
    },
    {
        "type": "function",
        "function": {
            "name": "liara_change_plan",
            "description": "تغییر پلن و اندازه منابع سخت‌افزاری (CPU/RAM) پروژه",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "نام پروژه"},
                    "planID": {
                        "type": "string",
                        "enum": ["micro", "small", "medium", "large", "xlarge", "xxlarge"],
                        "description": "شناسه پلن جدید",
                    },
                },
                "required": ["name", "planID"],
            },
        },
        "risk_level": RiskLevel.HIGH,
    },
    {
        "type": "function",
        "function": {
            "name": "liara_get_logs",
            "description": "دریافت آخرین لاگ‌های رانتایم برنامه برای خطایابی",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "نام پروژه"},
                    "since_minutes": {"type": "integer", "description": "تعداد دقایق گذشته (پیش‌فرض ۳۰ دقیقه)"},
                },
                "required": ["name"],
            },
        },
        "risk_level": RiskLevel.LOW,
    },
    {
        "type": "function",
        "function": {
            "name": "liara_get_metrics",
            "description": "دریافت متریک‌های مانیتورینگ CPU، RAM، شبکه و دیسک",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "نام پروژه"},
                    "metric": {"type": "string", "enum": ["cpu", "memory", "network", "disk"]},
                    "period": {"type": "string", "enum": ["1h", "6h", "24h", "7d", "30d"]},
                },
                "required": ["name"],
            },
        },
        "risk_level": RiskLevel.LOW,
    },
    {
        "type": "function",
        "function": {
            "name": "liara_delete_project",
            "description": "حذف دائم یک پروژه و کل اطلاعات آن در لیارا",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "نام پروژه"},
                },
                "required": ["name"],
            },
        },
        "risk_level": RiskLevel.CRITICAL,
    },
]


class ToolExecutor:
    """Executes OpenAI tool calls safely against the Liara Client."""

    def __init__(
        self,
        api_client: LiaraClient,
        approval_callback: Callable[[str, dict[str, Any], RiskLevel], bool] | None = None,
    ) -> None:
        self.api = api_client
        self.approval_callback = approval_callback

    def get_tool_risk(self, tool_name: str) -> RiskLevel:
        for tool in LIARA_TOOLS:
            if tool["function"]["name"] == tool_name:
                return tool.get("risk_level", RiskLevel.LOW)
        return RiskLevel.LOW

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool with risk evaluation and human approval check."""
        risk = self.get_tool_risk(tool_name)

        # Human approval check for medium, high, and critical actions
        if risk != RiskLevel.LOW and self.approval_callback:
            approved = self.approval_callback(tool_name, arguments, risk)
            if not approved:
                raise ApprovalDeniedError(tool_name)

        if tool_name == "liara_list_projects":
            res = await self.api.get_projects()
            return {"projects": [p.model_dump() for p in res.projects]}

        elif tool_name == "liara_get_project":
            name = arguments["name"]
            res = await self.api.get_project(name)
            return {"project": res.project.model_dump()}

        elif tool_name == "liara_restart_project":
            name = arguments["name"]
            await self.api.restart_project(name)
            return {"status": "success", "message": f"پروژه {name} با موفقیت ری‌استارت شد"}

        elif tool_name == "liara_scale_project":
            name = arguments["name"]
            scale = int(arguments["scale"])
            await self.api.scale_project(name, scale)
            return {"status": "success", "message": f"وضعیت اسکیل پروژه {name} به {scale} تغییر یافت"}

        elif tool_name == "liara_change_plan":
            name = arguments["name"]
            plan_id = arguments["planID"]
            await self.api.change_plan(name, plan_id)
            return {"status": "success", "message": f"پلن پروژه {name} به {plan_id} تغییر کرد"}

        elif tool_name == "liara_get_logs":
            import time
            name = arguments["name"]
            since_mins = arguments.get("since_minutes", 30)
            since_ts = int(time.time()) - (since_mins * 60)
            logs = await self.api.get_logs(name, since=since_ts)
            return {"logs": getattr(logs, "logs", logs)}

        elif tool_name == "liara_get_metrics":
            name = arguments["name"]
            metric = arguments.get("metric", "cpu")
            period = arguments.get("period", "1h")
            metrics = await self.api.get_reports(name, metric=metric, period=period)
            return {"metrics": metrics}

        elif tool_name == "liara_delete_project":
            name = arguments["name"]
            await self.api.delete_project(name)
            return {"status": "success", "message": f"پروژه {name} با موفقیت حذف شد"}

        return {"error": f"Tool '{tool_name}' not implemented"}
