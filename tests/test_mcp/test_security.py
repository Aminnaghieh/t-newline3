"""Security tests for the MCP server: write gate + path containment."""

import json

import pytest

from liara_agent.mcp import server as mcp_server_mod
from liara_agent.mcp.server import (
    _validate_workspace_path,
    _writes_allowed,
    liara_restart_app,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv("LIARA_MCP_ALLOW_WRITES", raising=False)
    monkeypatch.delenv("LIARA_MCP_WORKSPACE_ROOT", raising=False)
    # Run inside a controlled workspace directory.
    monkeypatch.chdir(tmp_path)


def test_writes_disabled_by_default():
    assert _writes_allowed() is False


def test_writes_enabled_with_flag(monkeypatch):
    monkeypatch.setenv("LIARA_MCP_ALLOW_WRITES", "1")
    assert _writes_allowed() is True


async def test_restart_blocked_without_flag():
    out = await liara_restart_app("my-app")
    data = json.loads(out)
    assert "error" in data
    assert "LIARA_MCP_ALLOW_WRITES" in data["hint"]


def test_workspace_path_inside_cwd_allowed():
    import pathlib

    target = pathlib.Path.cwd() / "my-project"
    target.mkdir(exist_ok=True)
    resolved = _validate_workspace_path(str(target))
    assert resolved.is_absolute()


def test_workspace_path_outside_cwd_rejected():
    with pytest.raises(ValueError):
        _validate_workspace_path("/etc")


def test_sensitive_directory_rejected():
    import pathlib

    ssh_dir = pathlib.Path.home() / ".ssh"
    with pytest.raises(ValueError):
        _validate_workspace_path(str(ssh_dir))


def test_home_itself_rejected():
    import pathlib

    with pytest.raises(ValueError):
        _validate_workspace_path(str(pathlib.Path.home()))


def test_workspace_root_env_expands_allowlist(monkeypatch, tmp_path):
    monkeypatch.setenv("LIARA_MCP_WORKSPACE_ROOT", str(tmp_path / "ws"))
    (tmp_path / "ws" / "proj").mkdir(parents=True)
    resolved = _validate_workspace_path(str(tmp_path / "ws" / "proj"))
    assert "proj" in str(resolved)
