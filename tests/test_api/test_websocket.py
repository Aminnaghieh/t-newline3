"""Tests for the LiaraWebSocket live-streaming client."""

import pytest

import liara_agent.api.websocket as ws_mod
from liara_agent.api.websocket import LiaraWebSocket
from liara_agent.utils.constants import LIARA_WS_BASE_URL


class FakeConnection:
    """Minimal stand-in for a websockets ClientConnection."""

    def __init__(self, messages):
        self._messages = messages
        self.open = True
        self.closed_called = False

    async def close(self) -> None:
        self.open = False
        self.closed_called = True

    def __aiter__(self):
        async def _gen():
            for message in self._messages:
                yield message

        return _gen()


def make_ws(**kwargs) -> LiaraWebSocket:
    defaults = {"token": "tok123", "project_id": "my-app"}
    defaults.update(kwargs)
    return LiaraWebSocket(**defaults)


def test_uri_composition():
    ws = make_ws()
    assert ws.uri.startswith(str(LIARA_WS_BASE_URL))
    assert "project_id=my-app" in ws.uri
    assert "cmd=/bin/bash" in ws.uri


def test_uri_never_contains_token():
    """Security: the bearer token must never leak into the WebSocket URL.

    URLs are logged by proxies, servers and crash reporters — the token is
    carried exclusively via the Authorization header.
    """
    ws = make_ws(token="super-secret-token-value")
    assert "super-secret-token-value" not in ws.uri
    assert "token=" not in ws.uri


def test_empty_token_or_project_rejected():
    with pytest.raises(ValueError):
        make_ws(token="")
    with pytest.raises(ValueError):
        make_ws(project_id="")


async def test_connect_and_stream_yields_messages(monkeypatch):
    fake = FakeConnection([b"boot: line one", "plain text line", "final line"])

    async def fake_connect(uri, additional_headers=None):
        assert "tok123" not in uri  # token stays out of the URL
        assert additional_headers is not None and "Bearer" in additional_headers["Authorization"]
        return fake

    monkeypatch.setattr(ws_mod.ws_client, "connect", fake_connect)

    ws = make_ws(max_reconnect_attempts=1)
    received = []
    async for message in ws.connect_and_stream():
        received.append(message)

    assert received == ["boot: line one", "plain text line", "final line"]
    assert ws._closed is True
    assert fake.closed_called is True


async def test_connect_and_stream_stops_after_max_reconnects(monkeypatch):
    """After the server closes, the loop must give up instead of retrying forever."""
    closed_once = FakeConnection([])  # empties immediately → graceful close path

    attempts = {"n": 0}

    async def fake_connect(uri, additional_headers=None):
        attempts["n"] += 1
        return closed_once

    monkeypatch.setattr(ws_mod.ws_client, "connect", fake_connect)

    ws = make_ws(max_reconnect_attempts=2)
    received = []
    async for message in ws.connect_and_stream():
        received.append(message)
    # The connection survives a graceful server close (still "open"), so the
    # loop reconnects by re-entering receive passes — one real handshake,
    # several passes capped by max_reconnect_attempts, then giving up.
    assert received == []
    assert attempts["n"] == 1
    assert ws._closed is True


async def test_aiter_is_idempotent():
    ws = make_ws()
    stream1 = ws.__aiter__()
    stream2 = ws.__aiter__()
    assert stream1 is stream2
