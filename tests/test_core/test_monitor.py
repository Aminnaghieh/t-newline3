"""Tests for core.monitor with mocked HTTP requests."""

import httpx
import pytest
import respx

from liara_agent.api.client import LiaraClient
from liara_agent.core.monitor import Monitor
from liara_agent.utils.errors import ProjectNotFoundError

BASE = "https://api.liara.ir"


def _points(values: list[float], start: int = 1000) -> list[dict]:
    return [{"timestamp": start + i, "value": v} for i, v in enumerate(values)]


def _project_response(status: str = "running", is_deployed: bool = True) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "project": {
                "_id": "p1",
                "project_id": "my-app",
                "type": "nodejs",
                "status": status,
                "scale": 1,
                "planID": "small",
                "isDeployed": is_deployed,
            }
        },
    )


def _mock_reports(
    cpu: list[float] | None = None,
    memory: list[float] | None = None,
    network: list[float] | None = None,
    project: str = "my-app",
) -> None:
    """Register respx routes for the three report endpoints."""
    url = f"{BASE}/v1/projects/{project}/reports"
    if cpu is not None:
        respx.get(url, params={"metric": "cpu", "period": "1h"}).mock(
            return_value=httpx.Response(200, json={"cpu": _points(cpu)})
        )
    if memory is not None:
        respx.get(url, params={"metric": "memory", "period": "1h"}).mock(
            return_value=httpx.Response(200, json={"memory": _points(memory)})
        )
    if network is not None:
        respx.get(url, params={"metric": "network", "period": "1h"}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "network_rx": _points(network),
                    "network_tx": _points(network),
                },
            )
        )


async def _snapshot(client: LiaraClient, project: str = "my-app"):
    monitor = Monitor(client)
    return await monitor.get_snapshot(project)


@pytest.mark.asyncio
@respx.mock
async def test_get_snapshot_full_metrics():
    respx.get(f"{BASE}/v1/projects/my-app").mock(
        return_value=_project_response(status="running", is_deployed=True)
    )
    _mock_reports(cpu=[10.0, 20.0, 30.0, 90.0], memory=[40.0, 45.0], network=[1000.0, 2000.0])

    async with LiaraClient(token="test_token") as client:
        snap = await _snapshot(client)

    assert snap.project_name == "my-app"
    assert snap.status == "running"
    assert snap.is_deployed is True
    assert snap.plan_id == "small"
    assert snap.cpu_percent == 90.0
    assert snap.memory_percent == 45.0
    assert snap.net_rx_series[-1].value == 2000.0
    assert snap.net_tx_series[-1].value == 2000.0
    assert snap.cpu_series[-1].value == 90.0

    # CPU 90% -> single high-CPU warning alert; warnings must not flip health.
    assert len(snap.alerts) == 1
    assert snap.alerts[0].rule_name == "High CPU Usage"
    assert snap.alerts[0].severity == "warning"
    assert snap.issues == []
    assert snap.is_healthy is True
    assert any("کلاستر/اسکیل" in r for r in snap.recommendations)


@pytest.mark.asyncio
@respx.mock
async def test_get_snapshot_critical_cpu_marks_unhealthy():
    respx.get(f"{BASE}/v1/projects/my-app").mock(return_value=_project_response())
    _mock_reports(cpu=[80.0, 96.0], memory=[10.0], network=[5.0])

    async with LiaraClient(token="test_token") as client:
        snap = await _snapshot(client)

    severities = {a.rule_name: a.severity for a in snap.alerts}
    assert severities == {
        "High CPU Usage": "warning",
        "Critical CPU Usage": "critical",
    }
    assert snap.is_healthy is False


@pytest.mark.asyncio
@respx.mock
async def test_get_snapshot_non_running_status_unhealthy():
    respx.get(f"{BASE}/v1/projects/my-app").mock(
        return_value=_project_response(status="starting")
    )
    _mock_reports(cpu=[10.0], memory=[10.0], network=[5.0])

    async with LiaraClient(token="test_token") as client:
        snap = await _snapshot(client)

    assert snap.is_healthy is False
    assert any("starting" in i for i in snap.issues)
    assert any("ری‌استارت" in r for r in snap.recommendations)


@pytest.mark.asyncio
@respx.mock
async def test_get_snapshot_report_failure_degrades_gracefully():
    respx.get(f"{BASE}/v1/projects/my-app").mock(return_value=_project_response())
    reports_url = f"{BASE}/v1/projects/my-app/reports"
    for metric in ("cpu", "memory", "network"):
        respx.get(reports_url, params={"metric": metric, "period": "1h"}).mock(
            return_value=httpx.Response(500, json={"message": "boom"})
        )

    async with LiaraClient(token="test_token") as client:
        snap = await _snapshot(client)

    assert snap.cpu_percent == 0.0
    assert snap.memory_percent == 0.0
    assert snap.cpu_series == []
    assert snap.alerts == []
    assert any("متریک" in i for i in snap.issues)
    assert snap.is_healthy is False


@pytest.mark.asyncio
@respx.mock
async def test_get_snapshot_unknown_project_propagates():
    respx.get(f"{BASE}/v1/projects/ghost").mock(
        return_value=httpx.Response(404, json={"message": "not found"})
    )

    async with LiaraClient(token="test_token") as client:
        with pytest.raises(ProjectNotFoundError):
            await _snapshot(client, project="ghost")


@pytest.mark.asyncio
@respx.mock
async def test_get_health_status_reads_model_data():
    """Regression: health values must come from the MetricsReport model."""
    respx.get(f"{BASE}/v1/projects/my-app").mock(return_value=_project_response())
    _mock_reports(cpu=[10.0, 90.0], memory=[30.0, 45.0])

    async with LiaraClient(token="test_token") as client:
        monitor = Monitor(client)
        health = await monitor.get_health_status("my-app")

    assert health.cpu_percent == 90.0  # was always 0.0 before the fix
    assert health.memory_percent == 45.0
    assert health.is_deployed is True
    assert health.is_healthy is False  # high-CPU warning alert added an issue
    assert any("[WARNING]" in i for i in health.issues)
