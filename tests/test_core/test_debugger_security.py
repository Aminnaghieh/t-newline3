"""Tests for approval-hash binding and LLM-context redaction in the Debugger."""

import pytest

from liara_agent.core.debugger import DebugContext, Debugger, Remediation
from liara_agent.utils.constants import RiskLevel


class _CapturingAI:
    """AI stub capturing the exact context dict it receives."""

    def __init__(self) -> None:
        self.captured: dict = {}

    async def troubleshoot(self, context: dict) -> dict:
        self.captured = context
        return {
            "root_cause_summary": "علت آزمایشی",
            "confidence": 0.9,
            "hypotheses": [
                {
                    "title": "هیپوتز",
                    "probability": 0.9,
                    "category": "unknown",
                    "explanation": "تست",
                    "impact": "تست",
                }
            ],
            "suggested_remediations": [
                {
                    "id": "fix_restart",
                    "title": "ری‌استارت",
                    "action_type": "restart",
                    "risk_level": "medium",
                }
            ],
        }


def test_remediation_hash_binds_to_project():
    rem = Remediation(
        id="fix_1", title="t", action_type="resize", description="d",
        risk_level=RiskLevel.HIGH, parameters={"planID": "small"},
    )
    rem.project_name = "app-a"
    hash_a = rem.compute_hash()
    rem.project_name = "app-b"
    assert rem.compute_hash() != hash_a


def test_remediation_hash_binds_to_parameters():
    rem = Remediation(id="fix_1", title="t", action_type="resize", description="d",
                      project_name="app")
    rem.parameters = {"planID": "small"}
    h1 = rem.compute_hash()
    rem.parameters = {"planID": "large"}
    assert rem.compute_hash() != h1


async def test_ai_context_is_redacted():
    """Secrets in runtime logs must never reach the AI engine."""
    ai = _CapturingAI()
    dbg = Debugger(api_client=None, ai_engine=ai)
    ctx = DebugContext(
        project_name="app",
        status="failed",
        recent_logs=[
            "connect postgres://admin:supersecretpw@db:5432/app",
            "Authorization: Bearer live_token_abcdef123456",
        ],
    )
    await dbg.diagnose(ctx)
    dumped = str(ai.captured)
    assert "supersecretpw" not in dumped
    assert "live_token_abcdef123456" not in dumped


async def test_approval_hash_attached_with_project():
    dbg = Debugger(api_client=None, ai_engine=None)
    ctx = DebugContext(project_name="my-app", status="failed", recent_logs=["oom killed"])
    diag = await dbg.diagnose(ctx)
    assert diag.approval_hash
    if diag.suggested_remediations:
        assert diag.suggested_remediations[0].project_name == "my-app"
