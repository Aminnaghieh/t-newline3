"""Tests for the fail-closed ToolExecutor and audit integration."""

import asyncio

import pytest

from liara_agent.ai.tools import ToolExecutor
from liara_agent.utils.constants import RiskLevel
from liara_agent.utils.errors import ApprovalDeniedError


class StubApi:
    """Records calls; never touches the network."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def get_projects(self):
        self.calls.append(("get_projects",))
        return type("R", (), {"projects": []})()

    async def restart_project(self, name):
        self.calls.append(("restart", name))


def test_medium_operation_without_callback_is_refused():
    """Fail-closed: no approver ⇒ non-LOW operations must never run."""
    executor = ToolExecutor(api_client=StubApi(), approval_callback=None)
    with pytest.raises(ApprovalDeniedError):
        asyncio.run(executor.execute("liara_restart_project", {"name": "app"}))


def test_critical_operation_without_callback_is_refused():
    executor = ToolExecutor(api_client=StubApi(), approval_callback=None)
    with pytest.raises(ApprovalDeniedError):
        asyncio.run(executor.execute("liara_delete_project", {"name": "app"}))


def test_denied_approval_raises():
    executor = ToolExecutor(api_client=StubApi(), approval_callback=lambda *a: False)
    with pytest.raises(ApprovalDeniedError):
        asyncio.run(executor.execute("liara_restart_project", {"name": "app"}))
    assert executor.api.calls == []  # nothing executed


def test_approved_medium_operation_executes():
    api = StubApi()
    executor = ToolExecutor(api_client=api, approval_callback=lambda *a: True)
    result = asyncio.run(executor.execute("liara_restart_project", {"name": "app"}))
    assert result["status"] == "success"
    assert ("restart", "app") in api.calls


def test_low_risk_runs_without_callback():
    api = StubApi()
    executor = ToolExecutor(api_client=api, approval_callback=None)
    asyncio.run(executor.execute("liara_list_projects", {}))
    assert ("get_projects",) in api.calls


def test_audit_trail_records_denial():
    from liara_agent.storage.audit import default_audit_logger

    executor = ToolExecutor(api_client=StubApi(), approval_callback=lambda *a: False)
    with pytest.raises(ApprovalDeniedError):
        asyncio.run(executor.execute("liara_scale_project", {"name": "app", "scale": 0}))

    records = default_audit_logger.get_recent(limit=5)
    denial = next(r for r in records if r["action"] == "tool.approval")
    assert denial["status"] == "denied"
    assert denial["risk_level"] == "high"


def test_get_tool_risk_mapping():
    executor = ToolExecutor(api_client=StubApi())
    assert executor.get_tool_risk("liara_list_projects") == RiskLevel.LOW
    assert executor.get_tool_risk("liara_restart_project") == RiskLevel.MEDIUM
    assert executor.get_tool_risk("liara_delete_project") == RiskLevel.CRITICAL
