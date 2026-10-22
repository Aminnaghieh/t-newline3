"""Liara Model Context Protocol (MCP) Server.

Enables any AI agent (Claude Desktop, Cursor, Antigravity, Windsurf, LangChain, etc.)
to manage, deploy, monitor, and troubleshoot Liara PaaS applications directly using
the user's own credentials and credits.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from liara_agent.api.client import LiaraClient
from liara_agent.core.analyzer import ProjectAnalyzer
from liara_agent.core.debugger import Debugger
from liara_agent.core.deployer import Deployer
from liara_agent.core.monitor import Monitor
from liara_agent.core.planner import PlanRecommender
from liara_agent.models.plans import get_plan_by_id
from liara_agent.storage.credentials import default_credential_store
from liara_agent.utils.config import get_settings

logger = logging.getLogger("liara-mcp")

# Initialize MCP Server
mcp_server = MCPServer("liara-sre-agent")


def _get_token() -> str:
    """Retrieve Liara API token from environment or credential store."""
    token = os.environ.get("LIARA_API_TOKEN")
    if not token:
        token = default_credential_store.get_token("LIARA_API_TOKEN")
    if not token:
        settings = get_settings()
        token = settings.liara_api_token
    if not token or token.endswith("xxxx"):
        raise ValueError(
            "Liara API token not found. Please set LIARA_API_TOKEN environment variable "
            "or run 'liara-agent config set-token' first."
        )
    return token


# ─── Tools ───────────────────────────────────────────────────


@mcp_server.tool(
    name="liara_get_account_info",
    description="Check user account info, email, and available credit on Liara.",
)
async def liara_get_account_info() -> str:
    """Check user account info and balance."""
    token = _get_token()
    async with LiaraClient(token=token) as client:
        user_data = await client.get_user()
        billing = await client.get_billing()
        return json.dumps({"user": user_data, "billing": billing}, ensure_ascii=False, indent=2)


@mcp_server.tool(
    name="liara_list_projects",
    description="List all projects and applications deployed on the user's Liara account.",
)
async def liara_list_projects() -> str:
    """List all projects."""
    token = _get_token()
    async with LiaraClient(token=token) as client:
        resp = await client.get_projects()
        projects = [
            {
                "name": p.name or p.project_id,
                "platform": p.type,
                "status": p.status,
                "plan": p.planID,
                "scale": p.scale,
                "is_deployed": p.isDeployed,
                "created_at": p.created_at,
            }
            for p in resp.projects
        ]
        return json.dumps(projects, ensure_ascii=False, indent=2)


@mcp_server.tool(
    name="liara_get_project_details",
    description="Get detailed specifications, status, port, and configuration of a Liara project.",
)
async def liara_get_project_details(project_name: str) -> str:
    """Get project details."""
    token = _get_token()
    async with LiaraClient(token=token) as client:
        resp = await client.get_project(project_name)
        return json.dumps(resp.project.model_dump(), ensure_ascii=False, indent=2)


@mcp_server.tool(
    name="liara_get_health",
    description="Get real-time health status, CPU/RAM usage, and active alerts for a Liara app.",
)
async def liara_get_health(project_name: str) -> str:
    """Get health status and metrics."""
    token = _get_token()
    async with LiaraClient(token=token) as client:
        monitor = Monitor(client)
        health = await monitor.get_health_status(project_name)
        return json.dumps(health.model_dump(), ensure_ascii=False, indent=2)


@mcp_server.tool(
    name="liara_get_logs",
    description="Retrieve recent application logs with optional time window and grep keyword filtering.",
)
async def liara_get_logs(project_name: str, since_minutes: int = 30, grep: str = "") -> str:
    """Get logs."""
    import time
    token = _get_token()
    since_ts = int(time.time()) - (since_minutes * 60)
    async with LiaraClient(token=token) as client:
        logs_resp = await client.get_logs(project_name, since=since_ts)
        items = getattr(logs_resp, "logs", logs_resp)
        results = []
        for it in items:
            msg = getattr(it, "message", str(it))
            ts = getattr(it, "timestamp", "")
            lvl = getattr(it, "level", "info")
            if grep and grep.lower() not in msg.lower():
                continue
            results.append({"timestamp": ts, "level": lvl, "message": msg})
        return json.dumps(results[-50:], ensure_ascii=False, indent=2)


@mcp_server.tool(
    name="liara_analyze_local_project",
    description="Analyze a local directory to detect language, framework, port, start command, and recommend a Liara plan.",
)
async def liara_analyze_local_project(project_path: str) -> str:
    """Analyze local codebase."""
    path = Path(project_path)
    if not path.is_dir():
        return json.dumps({"error": f"Path '{project_path}' is not a valid directory"})

    analyzer = ProjectAnalyzer(path)
    analysis = analyzer.analyze()
    planner = PlanRecommender()
    recommendation = planner.recommend(analysis)
    plan_info = get_plan_by_id(recommendation.recommended_plan)

    return json.dumps(
        {
            "analysis": analysis.model_dump(),
            "recommended_plan": plan_info.model_dump() if plan_info else {},
            "recommendation_reason": recommendation.reason,
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp_server.tool(
    name="liara_deploy_project",
    description="Package local source code as tar.gz and deploy/release to a Liara project.",
)
async def liara_deploy_project(
    project_name: str,
    source_path: str,
    port: int | None = None,
) -> str:
    """Deploy source code."""
    path = Path(source_path)
    if not path.is_dir():
        return json.dumps({"error": f"Path '{source_path}' is not a valid directory"})

    token = _get_token()
    async with LiaraClient(token=token) as client:
        analyzer = ProjectAnalyzer(path)
        analysis = analyzer.analyze()
        deployer = Deployer(client)
        result = await deployer.deploy(
            project_name=project_name,
            source_path=path,
            port=port or analysis.port,
            platform_type=analysis.platform,
        )
        return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)


@mcp_server.tool(
    name="liara_restart_app",
    description="Restart application pods/containers on Liara.",
)
async def liara_restart_app(project_name: str) -> str:
    """Restart app."""
    token = _get_token()
    async with LiaraClient(token=token) as client:
        await client.restart_project(project_name)
        return json.dumps(
            {"status": "success", "message": f"App '{project_name}' restarted successfully"},
            ensure_ascii=False,
        )


@mcp_server.tool(
    name="liara_scale_app",
    description="Turn an app on (scale=1) or off (scale=0) on Liara.",
)
async def liara_scale_app(project_name: str, scale: int) -> str:
    """Scale app on/off."""
    token = _get_token()
    async with LiaraClient(token=token) as client:
        await client.scale_project(project_name, scale)
        return json.dumps(
            {"status": "success", "message": f"App '{project_name}' scale set to {scale}"},
            ensure_ascii=False,
        )


@mcp_server.tool(
    name="liara_resize_plan",
    description="Upgrade or downgrade hardware plan (micro, small, medium, large, xlarge, xxlarge) of a Liara app.",
)
async def liara_resize_plan(project_name: str, plan_id: str) -> str:
    """Change hardware plan."""
    token = _get_token()
    async with LiaraClient(token=token) as client:
        await client.change_plan(project_name, plan_id)
        return json.dumps(
            {"status": "success", "message": f"App '{project_name}' plan changed to {plan_id}"},
            ensure_ascii=False,
        )


@mcp_server.tool(
    name="liara_diagnose_issue",
    description="Collect runtime context (logs, metrics, events) and diagnose root causes (RCA) with remediation steps.",
)
async def liara_diagnose_issue(project_name: str) -> str:
    """Troubleshoot an app."""
    token = _get_token()
    async with LiaraClient(token=token) as client:
        debugger = Debugger(client)
        context = await debugger.collect_context(project_name)
        diagnosis = await debugger.diagnose(context)
        return json.dumps(
            {
                "context_summary": {
                    "project_name": context.project_name,
                    "status": context.status,
                    "platform": context.platform,
                    "plan": context.plan_id,
                    "log_count": len(context.recent_logs),
                    "event_count": len(context.recent_events),
                },
                "diagnosis": diagnosis.model_dump(),
            },
            ensure_ascii=False,
            indent=2,
        )


# ─── Main Runner ─────────────────────────────────────────────


def run_mcp_server() -> None:
    """Run MCP server over stdio transport."""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    run_mcp_server()
