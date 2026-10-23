"""Async HTTP client for the Liara PaaS REST API.

Provides :class:`LiaraClient`, the single entry-point for every Liara API
interaction used by the SRE Agent.  Supports automatic retries with
exponential back-off, rate-limit awareness, structured error mapping,
offline cache fallback for read-only GET requests, and full
async-context-manager lifecycle.

Usage::

    async with LiaraClient(token="liara_xxx") as client:
        projects = await client.get_projects()
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from tenacity.wait import wait_base

from liara_agent.api import endpoints as ep
from liara_agent.models.deploy import (
    EventsResponse,
    ReleaseRequest,
    ReleasesResponse,
    SourceUploadResponse,
)
from liara_agent.models.metrics import LogsResponse, MetricsReport
from liara_agent.models.project import (
    ProjectCreate,
    ProjectDetailResponse,
    ProjectListResponse,
)
from liara_agent.utils import cache as offline_cache
from liara_agent.utils.constants import (
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_BACKOFF,
    LIARA_API_BASE_URL,
    PROJECT_NAME_PATTERN,
    RATE_LIMIT_READ_PER_MIN,
    RATE_LIMIT_WRITE_PER_MIN,
)
from liara_agent.utils.errors import (
    AuthenticationError,
    DeploymentError,
    LiaraApiError,
    ProjectNotFoundError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

# HTTP methods treated as *write* operations for rate-limit tracking.
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Marker injected into cached payloads so callers can surface "offline".
STALE_FLAG = "__stale__"
STALE_AGE = "__stale_age_sec__"

_PROJECT_NAME_RE = re.compile(PROJECT_NAME_PATTERN)


def validate_project_name(name: str) -> str:
    """Validate a project name before it is interpolated into endpoint paths.

    Blocks path-traversal and URL-injection payloads (``../x``, ``%2f``,
    spaces, ``@`` …) from ever reaching the HTTP layer.
    """
    if not name or not _PROJECT_NAME_RE.match(name):
        raise ValueError(
            f"نام پروژه '{name}' نامعتبر است. نام باید ۲ تا ۶۳ کاراکتر "
            "شامل حروف کوچک لاتین، عدد و خط تیره باشد."
        )
    return name


class _WaitRetryAfterOrBackoff(wait_base):
    """Honor the server's ``Retry-After`` hint, else exponential backoff."""

    def __init__(self, multiplier: float, min_v: float, max_v: float) -> None:
        self._exp = wait_exponential(multiplier=multiplier, min=min_v, max=max_v)

    def __call__(self, retry_state: Any) -> float:
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        retry_after = getattr(exc, "retry_after", None)
        if retry_after is not None:
            try:
                return min(float(retry_after) + 0.5, 60.0)
            except (TypeError, ValueError):  # pragma: no cover
                pass
        return self._exp(retry_state)


class LiaraClient:
    """Async HTTP client for the Liara PaaS API."""

    def __init__(
        self,
        token: str,
        base_url: str = LIARA_API_BASE_URL,
        timeout: float = 30.0,
        team_id: str | None = None,
    ) -> None:
        if not token:
            raise AuthenticationError("API token must not be empty")

        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._team_id = team_id or os.getenv("LIARA_TEAM_ID")
        self._client: httpx.AsyncClient | None = None
        self._offline: bool = False

        self._read_timestamps: list[float] = []
        self._write_timestamps: list[float] = []
        self._rate_lock = threading.Lock()

    # ── Context Manager ──────────────────────────────────────

    async def __aenter__(self) -> LiaraClient:
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            # Security posture: always verify TLS, never follow redirects
            # (a redirect must not silently re-send the Bearer token elsewhere).
            verify=True,
            follow_redirects=False,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def is_offline(self) -> bool:
        """True once the last read was served from the offline cache."""
        return self._offline

    # ── Rate Limiter ─────────────────────────────────────────

    def _check_rate_limit(self, method: str) -> None:
        now = time.monotonic()
        window = 60.0

        with self._rate_lock:
            if method.upper() in _WRITE_METHODS:
                self._write_timestamps = [
                    ts for ts in self._write_timestamps if now - ts < window
                ]
                if len(self._write_timestamps) >= RATE_LIMIT_WRITE_PER_MIN:
                    raise RateLimitError(
                        retry_after=int(window - (now - self._write_timestamps[0])) + 1,
                        endpoint=f"{method} (client-side limit)",
                    )
                self._write_timestamps.append(now)
            else:
                self._read_timestamps = [
                    ts for ts in self._read_timestamps if now - ts < window
                ]
                if len(self._read_timestamps) >= RATE_LIMIT_READ_PER_MIN:
                    raise RateLimitError(
                        retry_after=int(window - (now - self._read_timestamps[0])) + 1,
                        endpoint=f"{method} (client-side limit)",
                    )
                self._read_timestamps.append(now)

    # ── Cache key ────────────────────────────────────────────

    def _cache_key(self, method: str, path: str) -> str:
        team = self._team_id or "personal"
        return f"{method.upper()}:{team}:{path}"

    # ── Core Request ─────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, RateLimitError)),
        stop=stop_after_attempt(DEFAULT_RETRY_ATTEMPTS),
        wait=_WaitRetryAfterOrBackoff(DEFAULT_RETRY_BACKOFF, 1, 30),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError(
                "LiaraClient is not initialised — use 'async with LiaraClient(…) as c:'"
            )

        self._check_rate_limit(method)

        merged_params: dict[str, Any] = dict(params) if params else {}
        if self._team_id:
            merged_params["teamID"] = self._team_id

        req_kwargs: dict[str, Any] = {"method": method, "url": path}
        if merged_params:
            req_kwargs["params"] = merged_params

        if files:
            req_kwargs["files"] = files
            req_kwargs["headers"] = {
                **(headers or {}),
                "Content-Type": "",
            }
            req_kwargs["headers"].pop("Content-Type", None)
        else:
            if json is not None:
                req_kwargs["json"] = json
            if headers:
                req_kwargs["headers"] = headers

        logger.debug("API → %s %s", method, path)
        cache_key = self._cache_key(method, path)

        try:
            response = await self._client.request(**req_kwargs)
        except httpx.TransportError as exc:
            self._offline = True
            # Offline fallback: only for read-only requests.
            if method.upper() == "GET":
                cached = offline_cache.load(cache_key)
                if cached is not None:
                    payload, age = cached
                    self._offline = True
                    logger.warning(
                        "API offline (%s); serving cached %s (age=%.0fs)",
                        exc, path, age,
                    )
                    if isinstance(payload, dict):
                        out = dict(payload)
                    else:
                        out = {"data": payload}
                    out[STALE_FLAG] = True
                    out[STALE_AGE] = age
                    return out
            # No cache: propagate.
            raise

        data = self._handle_response(response, path)
        if method.upper() == "GET" and not self._offline:
            offline_cache.save(cache_key, data)
        return data

    # ── Response / Error Handling ─────────────────────────────

    @staticmethod
    def _handle_response(
        response: httpx.Response,
        endpoint: str,
    ) -> dict[str, Any]:
        status = response.status_code

        if status == 204:
            return {}

        if status == 401:
            raise AuthenticationError()
        if status == 404:
            raise ProjectNotFoundError(endpoint)
        if status == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            raise RateLimitError(retry_after=retry_after, endpoint=endpoint)
        if status >= 400:
            try:
                detail = str(response.json().get("message", ""))
            except Exception:
                # Never embed the raw server body (it may echo tokens or PII);
                # truncate to a safe snippet instead.
                detail = (response.text or "")[:200]
            raise LiaraApiError(
                status_code=status,
                message=detail or f"HTTP {status}",
                endpoint=endpoint,
            )

        if not response.text:
            return {}
        return response.json()  # type: ignore[no-any-return]

    # ═══════════════════════════════════════════════════════════
    #  Apps / Projects
    # ═══════════════════════════════════════════════════════════

    async def get_projects(self) -> ProjectListResponse:
        params = {"teamID": self._team_id} if self._team_id else None
        data = await self._request("GET", ep.PROJECTS, params=params)
        if data.get(STALE_FLAG):
            logger.warning("projects list served from offline cache")
        return ProjectListResponse.model_validate(
            {k: v for k, v in data.items() if k != STALE_FLAG and k != STALE_AGE}
        )

    async def get_project(self, name: str) -> ProjectDetailResponse:
        validate_project_name(name)
        data = await self._request("GET", ep.PROJECT.format(name=name))
        return ProjectDetailResponse.model_validate(
            {k: v for k, v in data.items() if k != STALE_FLAG and k != STALE_AGE}
        )

    async def create_project(self, data: ProjectCreate) -> dict[str, Any]:
        return await self._request(
            "POST", ep.PROJECTS, json=data.model_dump(exclude_none=True)
        )

    async def delete_project(self, name: str) -> dict[str, Any]:
        validate_project_name(name)
        return await self._request("DELETE", ep.PROJECT.format(name=name))

    async def restart_project(self, name: str) -> dict[str, Any]:
        validate_project_name(name)
        return await self._request(
            "POST", ep.PROJECT_RESTART.format(name=name)
        )

    async def scale_project(self, name: str, scale: int) -> dict[str, Any]:
        validate_project_name(name)
        if scale not in (0, 1):
            raise ValueError("scale must be 0 or 1")
        return await self._request(
            "POST",
            ep.PROJECT_SCALE.format(name=name),
            json={"scale": scale},
        )

    async def change_plan(self, name: str, plan_id: str) -> dict[str, Any]:
        validate_project_name(name)
        return await self._request(
            "POST",
            ep.PROJECT_RESIZE.format(name=name),
            json={"planID": plan_id},
        )

    async def set_zero_downtime(self, name: str, enabled: bool) -> dict[str, Any]:
        validate_project_name(name)
        status = "enable" if enabled else "disable"
        return await self._request(
            "POST",
            ep.PROJECT_ZERO_DOWNTIME.format(name=name, status=status),
        )

    # ═══════════════════════════════════════════════════════════
    #  Deployments
    # ═══════════════════════════════════════════════════════════

    async def upload_source(
        self, name: str, file_path: Path
    ) -> SourceUploadResponse:
        validate_project_name(name)
        file_path = Path(file_path)
        if not file_path.exists():
            raise DeploymentError(
                f"Source file not found: {file_path}", project_name=name
            )
        if not file_path.name.endswith(".tar.gz"):
            raise DeploymentError(
                "Source file must be a .tar.gz archive", project_name=name
            )

        with open(file_path, "rb") as fh:
            data = await self._request(
                "POST",
                ep.SOURCES_UPLOAD.format(name=name),
                files={"file": (file_path.name, fh, "application/gzip")},
            )
        return SourceUploadResponse.model_validate(data)

    async def deploy_release(
        self, name: str, data: ReleaseRequest
    ) -> dict[str, Any]:
        validate_project_name(name)
        return await self._request(
            "POST",
            ep.RELEASES_CREATE.format(name=name),
            json=data.model_dump(exclude_none=True),
        )

    async def get_releases(
        self, name: str, page: int = 1, count: int = 10
    ) -> ReleasesResponse:
        validate_project_name(name)
        data = await self._request(
            "GET",
            ep.RELEASES_LIST.format(name=name),
            params={"page": page, "count": count},
        )
        return ReleasesResponse.model_validate(
            {k: v for k, v in data.items() if k != STALE_FLAG and k != STALE_AGE}
        )

    async def get_events(
        self,
        name: str,
        search: str = "",
        start: int = 0,
        end: int = 0,
    ) -> EventsResponse:
        params: dict[str, Any] = {}
        if search:
            params["search"] = search
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        data = await self._request(
            "GET", ep.EVENTS.format(name=name), params=params or None
        )
        return EventsResponse.model_validate(
            {k: v for k, v in data.items() if k != STALE_FLAG and k != STALE_AGE}
        )

    # ═══════════════════════════════════════════════════════════
    #  Monitoring
    # ═══════════════════════════════════════════════════════════

    async def get_reports(
        self, name: str, metric: str = "cpu", period: str = "1h"
    ) -> MetricsReport:
        validate_project_name(name)
        data = await self._request(
            "GET",
            ep.REPORTS.format(name=name),
            params={"metric": metric, "period": period},
        )
        return MetricsReport.model_validate(
            {k: v for k, v in data.items() if k != STALE_FLAG and k != STALE_AGE}
        )

    async def get_logs(self, name: str, since: int) -> LogsResponse:
        validate_project_name(name)
        data = await self._request(
            "GET",
            ep.LOGS.format(name=name),
            params={"since": since},
        )
        return LogsResponse.model_validate(
            {k: v for k, v in data.items() if k != STALE_FLAG and k != STALE_AGE}
        )

    # ═══════════════════════════════════════════════════════════
    #  Environment Variables
    # ═══════════════════════════════════════════════════════════

    async def update_envs(
        self, project: str, variables: list[dict[str, str]]
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            ep.UPDATE_ENVS,
            json={"project": project, "variables": variables},
        )

    # ═══════════════════════════════════════════════════════════
    #  Domains
    # ═══════════════════════════════════════════════════════════

    async def get_domains(self, project: str) -> dict[str, Any]:
        return await self._request(
            "GET", ep.DOMAINS, params={"project": project}
        )

    async def create_domain(self, name: str) -> dict[str, Any]:
        return await self._request(
            "POST", ep.DOMAINS, json={"name": name}
        )

    async def attach_domain(self, domain_id: str, project_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            ep.DOMAINS_SET_PROJECT,
            json={"domainID": domain_id, "projectID": project_id},
        )

    # ═══════════════════════════════════════════════════════════
    #  Disks & Backups
    # ═══════════════════════════════════════════════════════════

    async def get_disks(self, name: str) -> dict[str, Any]:
        validate_project_name(name)
        return await self._request("GET", ep.DISKS.format(name=name))

    async def create_disk(self, name: str, disk_name: str, size: int) -> dict[str, Any]:
        validate_project_name(name)
        return await self._request(
            "POST",
            ep.DISKS.format(name=name),
            json={"name": disk_name, "size": size},
        )

    async def get_disk_backups(self, name: str, disk_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", ep.DISK_BACKUPS.format(name=name, disk_id=disk_id)
        )

    async def create_disk_backup(self, name: str, disk_id: str) -> dict[str, Any]:
        return await self._request(
            "POST", ep.DISK_BACKUPS.format(name=name, disk_id=disk_id)
        )

    # ═══════════════════════════════════════════════════════════
    #  User & Billing
    # ═══════════════════════════════════════════════════════════

    async def get_user(self) -> dict[str, Any]:
        return await self._request("GET", ep.USER_ME)

    async def get_billing(self) -> dict[str, Any]:
        return await self._request("GET", ep.BILLING)
