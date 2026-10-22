"""Tests for LiaraClient with mocked HTTP requests."""

import httpx
import pytest
import respx

from liara_agent.api.client import LiaraClient
from liara_agent.models.project import ProjectCreate
from liara_agent.utils.errors import LiaraApiError, RateLimitError


@pytest.mark.asyncio
@respx.mock
async def test_get_projects_success():
    respx.get("https://api.liara.ir/v1/projects").mock(
        return_value=httpx.Response(
            200,
            json={"projects": [{"_id": "p1", "project_id": "test-app", "type": "nodejs", "status": "running", "scale": 1, "planID": "small", "isDeployed": True}]},
        )
    )

    async with LiaraClient(token="test_token") as client:
        result = await client.get_projects()
        assert len(result.projects) == 1
        assert result.projects[0].name == "test-app"
        assert result.projects[0].status == "running"


@pytest.mark.asyncio
@respx.mock
async def test_restart_project():
    respx.post("https://api.liara.ir/v1/projects/my-app/actions/restart").mock(
        return_value=httpx.Response(204)
    )

    async with LiaraClient(token="test_token") as client:
        await client.restart_project("my-app")


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_handling():
    respx.get("https://api.liara.ir/v1/projects").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "30"})
    )

    async with LiaraClient(token="test_token") as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_projects()
        assert exc_info.value.retry_after == 30
