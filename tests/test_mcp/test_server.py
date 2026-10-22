"""Tests for Liara MCP Server tool registrations."""

import asyncio
import pytest

from liara_agent.mcp.server import mcp_server


@pytest.mark.asyncio
async def test_mcp_tools_registration():
    """Verify that all Liara MCP tools are properly registered."""
    tools = await mcp_server.list_tools()
    tool_names = [t.name for t in tools]

    expected = [
        "liara_get_account_info",
        "liara_list_projects",
        "liara_get_project_details",
        "liara_get_health",
        "liara_get_logs",
        "liara_analyze_local_project",
        "liara_deploy_project",
        "liara_restart_app",
        "liara_scale_app",
        "liara_resize_plan",
        "liara_diagnose_issue",
    ]

    for exp in expected:
        assert exp in tool_names, f"Tool '{exp}' missing from MCP server"
