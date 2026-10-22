"""Tests for Debugger RCA and diagnosis."""

import pytest
from liara_agent.core.debugger import DebugContext, Debugger
from liara_agent.utils.constants import ErrorCategory


@pytest.mark.asyncio
async def test_debugger_diagnoses_oom():
    debugger = Debugger(api_client=None, ai_engine=None)
    ctx = DebugContext(
        project_name="my-app",
        status="failed",
        platform="nodejs",
        plan_id="micro",
        recent_logs=[
            "Starting node application...",
            "FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory",
            "Process killed by OOM",
        ],
        recent_events=["Container terminated with exit code 137"],
    )

    diagnosis = await debugger.diagnose(ctx)
    assert diagnosis.confidence > 0.8
    assert diagnosis.hypotheses[0].category == ErrorCategory.RESOURCE_EXHAUSTION
    assert any(rem.action_type == "resize" for rem in diagnosis.suggested_remediations)


@pytest.mark.asyncio
async def test_debugger_diagnoses_port_conflict():
    debugger = Debugger(api_client=None, ai_engine=None)
    ctx = DebugContext(
        project_name="my-app",
        status="stopped",
        platform="nodejs",
        plan_id="micro",
        recent_logs=[
            "Error: listen EADDRINUSE: address already in use :::3000",
        ],
    )

    diagnosis = await debugger.diagnose(ctx)
    assert diagnosis.hypotheses[0].category == ErrorCategory.CONFIG_ERROR
