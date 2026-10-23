"""WebSocket client for live Liara log streaming.

Provides :class:`LiaraWebSocket` for real-time, bidirectional
communication with a project's container shell via the Liara
WebSocket gateway.

Usage::

    async for message in LiaraWebSocket(token, project_id):
        print(message)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from types import TracebackType
from typing import Self

import websockets
import websockets.asyncio.client as ws_client
from websockets.asyncio.client import ClientConnection

from liara_agent.utils.constants import LIARA_WS_BASE_URL

logger = logging.getLogger(__name__)

# Reconnection defaults
_INITIAL_BACKOFF = 1.0   # seconds
_MAX_BACKOFF = 60.0       # seconds
_BACKOFF_FACTOR = 2.0


class LiaraWebSocket:
    """Async WebSocket client for live log / shell streaming.

    Parameters
    ----------
    token:
        Liara API bearer token.
    project_id:
        Target project identifier (``_id`` field).
    base_url:
        WebSocket gateway base URL.
    max_reconnect_attempts:
        Maximum consecutive reconnection attempts before giving up.
        ``0`` means unlimited.
    """

    def __init__(
        self,
        token: str,
        project_id: str,
        base_url: str = LIARA_WS_BASE_URL,
        max_reconnect_attempts: int = 10,
    ) -> None:
        if not token:
            raise ValueError("WebSocket token must not be empty")
        if not project_id:
            raise ValueError("project_id must not be empty")

        self._token = token
        self._project_id = project_id
        self._base_url = base_url.rstrip("/")
        self._max_reconnect_attempts = max_reconnect_attempts

        self._connection: ClientConnection | None = None
        self._stream: AsyncIterator[str] | None = None
        self._closed = False

    # ── Properties ───────────────────────────────────────────

    @property
    def uri(self) -> str:
        """Fully-qualified WebSocket URI (token-free).

        Security: the bearer token is *never* placed in the URL — URLs are
        logged by proxies, servers and crash reporters. Authentication is
        carried exclusively by the ``Authorization`` header set in
        :meth:`connect`.
        """
        return f"{self._base_url}?cmd=/bin/bash&project_id={self._project_id}"

    @property
    def is_connected(self) -> bool:
        """``True`` when the underlying connection is open."""
        return self._connection is not None and self._connection.open

    # ── Connection Lifecycle ─────────────────────────────────

    async def connect(self) -> None:
        """Establish the WebSocket connection.

        Raises
        ------
        websockets.exceptions.WebSocketException
            If the initial handshake fails.
        """
        logger.info("WS connecting to project %s …", self._project_id)
        self._closed = False
        self._connection = await ws_client.connect(
            self.uri,
            additional_headers={
                "Authorization": f"Bearer {self._token}",
            },
        )
        logger.info("WS connected to project %s", self._project_id)

    async def disconnect(self) -> None:
        """Gracefully close the WebSocket connection."""
        self._closed = True
        if self._connection is not None:
            try:
                await self._connection.close()
            except Exception:
                logger.debug("WS close raised; ignoring", exc_info=True)
            finally:
                self._connection = None
        logger.info("WS disconnected from project %s", self._project_id)

    # ── Context Manager ──────────────────────────────────────

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.disconnect()

    # ── Async Iterator ───────────────────────────────────────

    def __aiter__(self) -> AsyncIterator[str]:
        """Return the idempotent receive loop for this instance.

        Iterating twice (or from two ``async for`` statements) yields the
        *same* stream instead of spawning competing receive loops.
        """
        if self._stream is None:
            self._stream = self._receive_loop()
        return self._stream

    async def connect_and_stream(self) -> AsyncIterator[str]:
        """Connect automatically and yield every incoming message.

        The ergonomic entry point for live log tailing::

            ws = LiaraWebSocket(token, project_id)
            async for message in ws.connect_and_stream():
                print(message)

        The underlying stream auto-reconnects with backoff and stops after
        ``max_reconnect_attempts`` consecutive failures. When iteration ends
        the connection is closed.
        """
        try:
            async for message in self:
                yield message
        finally:
            await self.disconnect()

    async def _receive_loop(self) -> AsyncIterator[str]:
        """Yield messages from the WebSocket with automatic reconnection."""
        attempts = 0
        backoff = _INITIAL_BACKOFF

        while not self._closed:
            try:
                if not self.is_connected:
                    await self.connect()
                    attempts = 0
                    backoff = _INITIAL_BACKOFF

                connection = self._connection
                if connection is None:  # pragma: no cover — connect() above guarantees
                    logger.error("WS connection missing after connect(); retrying…")
                    continue
                async for raw in connection:
                    if isinstance(raw, bytes):
                        yield raw.decode("utf-8", errors="replace")
                    else:
                        yield raw

                # Server closed gracefully — exit unless we should reconnect.
                if self._closed:
                    return
                logger.warning("WS connection closed by server; reconnecting…")

            except websockets.exceptions.ConnectionClosed as exc:
                if self._closed:
                    return
                logger.warning(
                    "WS connection lost (code=%s reason=%s); reconnecting…",
                    exc.code,
                    exc.reason,
                )
            except Exception:
                if self._closed:
                    return
                logger.exception("WS unexpected error; reconnecting…")

            # ── Reconnection back-off ────────────────────────
            attempts += 1
            if (
                self._max_reconnect_attempts > 0
                and attempts >= self._max_reconnect_attempts
            ):
                logger.error(
                    "WS max reconnect attempts (%d) reached; giving up.",
                    self._max_reconnect_attempts,
                )
                return

            logger.info("WS reconnect attempt %d (backoff %.1fs)", attempts, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * _BACKOFF_FACTOR, _MAX_BACKOFF)

    # ── Send ─────────────────────────────────────────────────

    async def send(self, message: str) -> None:
        """Send a text message through the WebSocket.

        Parameters
        ----------
        message:
            Text payload to send (e.g. a shell command).

        Raises
        ------
        RuntimeError
            If the connection is not open.
        """
        if not self.is_connected or self._connection is None:
            raise RuntimeError("WebSocket is not connected")
        await self._connection.send(message)
