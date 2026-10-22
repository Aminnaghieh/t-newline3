"""Async HTTP client for the Liara PaaS REST API.

Provides :class:`LiaraClient`, the single entry-point for every Liara API
interaction used by the SRE Agent.  Supports automatic retries with
exponential back-off, rate-limit awareness, structured error mapping, and
full async-context-manager lifecycle.

Usage::

    async with LiaraClient(token="liara_xxx") as client:
        projects = await client.get_projects()
"""

from __future__ import annotations

import logging
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
from liara_agent.utils.constants import (
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_BACKOFF,
    LIARA_API_BASE_URL,
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


class LiaraClient:
    """Async HTTP client for the Liara PaaS API.

    Parameters
    ----------
    token:
        Bearer token obtained from the Liara console.
    base_url:
        API base URL.  Defaults to ``https://api.liara.ir``.
    timeout:
        Default request timeout in seconds.
    """

    def __init__(
        self,
        token: str,
        base_url: str = LIARA_API_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        if not token:
            raise AuthenticationError("API token must not be empty")

        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

        # Simple sliding-window rate-limit tracking.
        self._read_timestamps: list[float] = []
        self._write_timestamps: list[float] = []

    # ── Context Manager ──────────────────────────────────────

    async def __aenter__(self) -> LiaraClient:
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
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

    # ── Rate Limiter ─────────────────────────────────────────

    def _check_rate_limit(self, method: str) -> None:
        """Raise :class:`RateLimitError` if the local rate-limit window is full."""
        now = time.monotonic()
        window = 60.0  # seconds

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

    # ── Core Request ─────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, RateLimitError)),
        stop=stop_after_attempt(DEFAULT_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=DEFAULT_RETRY_BACKOFF, min=1, max=30),
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
        """Send an authenticated request and return the JSON response.

        Handles:
        - Authorization header injection
        - Client-side rate-limit enforcement
        - HTTP error → custom exception mapping
        - Retries with exponential back-off (via *tenacity*)

        Parameters
        ----------
        method:
            HTTP verb (``GET``, ``POST``, …).
        path:
            URL path **relative** to *base_url*.
        json:
            JSON-serialisable request body.
        params:
            Query-string parameters.
        files:
            Multipart file data (disables JSON content-type).
        headers:
            Extra headers merged on top of the default set.
        """
        if self._client is None:
            raise RuntimeError(
                "LiaraClient is not initialised — use 'async with LiaraClient(…) as c:'"
            )

        self._check_rate_limit(method)

        req_kwargs: dict[str, Any] = {"method": method, "url": path}
        if params:
            req_kwargs["params"] = params
        if files:
            # For multipart uploads, remove the JSON content-type.
            req_kwargs["files"] = files
            req_kwargs["headers"] = {
                **(headers or {}),
                "Content-Type": "",  # let httpx set multipart boundary
            }
            # httpx ignores Content-Type="" and auto-generates the header.
            req_kwargs["headers"].pop("Content-Type", None)
        else:
            if json is not None:
                req_kwargs["json"] = json
            if headers:
                req_kwargs["headers"] = headers

        logger.debug("API → %s %s", method, path)
        response = await self._client.request(**req_kwargs)
        return self._handle_response(response, path)

    # ── Response / Error Handling ─────────────────────────────

    @staticmethod
    def _handle_response(
        response: httpx.Response,
        endpoint: str,
    ) -> dict[str, Any]:
        """Map HTTP status codes to domain exceptions and parse JSON."""
        status = response.status_code

        if status == 204:
            return {}

        # --- error mapping ---
        if status == 401:
            raise AuthenticationError()
        if status == 404:
            raise ProjectNotFoundError(endpoint)
        if status == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            raise RateLimitError(retry_after=retry_after, endpoint=endpoint)
        if status >= 400:
            try:
                detail = response.json().get("message", response.text)
            except Exception:
                detail = response.text
            raise LiaraApiError(
                status_code=status,
                message=str(detail),
                endpoint=endpoint,
            )

        # --- success ---
        if not response.text:
            return {}
        return response.json()  # type: ignore[no-any-return]

    # ═══════════════════════════════════════════════════════════
    #  Apps / Projects
    # ═══════════════════════════════════════════════════════════

    async def get_projects(self) -> ProjectListResponse:
        """List all projects owned by the authenticated user.

        Returns
        -------
        ProjectListResponse
            Wrapper containing ``projects: list[ProjectInfo]``.
        """
        data = await self._request("GET", ep.PROJECTS)
        return ProjectListResponse.model_validate(data)

    async def get_project(self, name: str) -> ProjectDetailResponse:
        """Get detailed information for a single project.

        Parameters
        ----------
        name:
            Project name (slug).
        """
        data = await self._request("GET", ep.PROJECT.format(name=name))
        return ProjectDetailResponse.model_validate(data)

    async def create_project(self, data: ProjectCreate) -> dict[str, Any]:
        """Create a new Liara project.

        Parameters
        ----------
        data:
            Project creation payload.
        """
        return await self._request(
            "POST", ep.PROJECTS, json=data.model_dump()
        )

    async def delete_project(self, name: str) -> dict[str, Any]:
        """Permanently delete a project.

        Parameters
        ----------
        name:
            Project name.
        """
        return await self._request("DELETE", ep.PROJECT.format(name=name))

    async def restart_project(self, name: str) -> dict[str, Any]:
        """Restart a running project.

        Parameters
        ----------
        name:
            Project name.
        """
        return await self._request(
            "POST", ep.PROJECT_RESTART.format(name=name)
        )

    async def scale_project(self, name: str, scale: int) -> dict[str, Any]:
        """Scale a project on or off.

        Parameters
        ----------
        name:
            Project name.
        scale:
            ``1`` to turn on, ``0`` to turn off.
        """
        if scale not in (0, 1):
            raise ValueError("scale must be 0 or 1")
        return await self._request(
            "POST",
            ep.PROJECT_SCALE.format(name=name),
            json={"scale": scale},
        )

    async def change_plan(self, name: str, plan_id: str) -> dict[str, Any]:
        """Resize a project to a different plan.

        Parameters
        ----------
        name:
            Project name.
        plan_id:
            Target plan identifier (e.g. ``"medium"``).
        """
        return await self._request(
            "POST",
            ep.PROJECT_RESIZE.format(name=name),
            json={"planID": plan_id},
        )

    async def set_zero_downtime(
        self, name: str, enabled: bool
    ) -> dict[str, Any]:
        """Enable or disable zero-downtime deployments.

        Parameters
        ----------
        name:
            Project name.
        enabled:
            ``True`` to enable, ``False`` to disable.
        """
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
        """Upload a ``.tar.gz`` source archive for deployment.

        Parameters
        ----------
        name:
            Project name.
        file_path:
            Local path to the ``.tar.gz`` archive.

        Raises
        ------
        DeploymentError
            If the file does not exist or has the wrong extension.
        """
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
        """Create a new release (deploy) from a previously uploaded source.

        Parameters
        ----------
        name:
            Project name.
        data:
            Release configuration including ``sourceID``.
        """
        return await self._request(
            "POST",
            ep.RELEASES_CREATE.format(name=name),
            json=data.model_dump(exclude_none=True),
        )

    async def get_releases(
        self, name: str, page: int = 1, count: int = 10
    ) -> ReleasesResponse:
        """List releases (deployments) for a project, paginated.

        Parameters
        ----------
        name:
            Project name.
        page:
            Page number (1-based).
        count:
            Items per page.
        """
        data = await self._request(
            "GET",
            ep.RELEASES_LIST.format(name=name),
            params={"page": page, "count": count},
        )
        return ReleasesResponse.model_validate(data)

    async def get_events(
        self,
        name: str,
        search: str = "",
        start: int = 0,
        end: int = 0,
    ) -> EventsResponse:
        """Get deployment events for a project.

        Parameters
        ----------
        name:
            Project name.
        search:
            Optional event search filter.
        start:
            Unix timestamp – events **after** this time.
        end:
            Unix timestamp – events **before** this time.
        """
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
        return EventsResponse.model_validate(data)

    # ═══════════════════════════════════════════════════════════
    #  Monitoring
    # ═══════════════════════════════════════════════════════════

    async def get_reports(
        self,
        name: str,
        metric: str = "cpu",
        period: str = "1h",
    ) -> MetricsReport:
        """Fetch resource usage reports (CPU, memory, network).

        Parameters
        ----------
        name:
            Project name.
        metric:
            Metric type – ``cpu``, ``memory``, ``network``, ``disk``.
        period:
            Time window – ``1h``, ``6h``, ``24h``, ``7d``, ``30d``.
        """
        data = await self._request(
            "GET",
            ep.REPORTS.format(name=name),
            params={"metric": metric, "period": period},
        )
        return MetricsReport.model_validate(data)

    async def get_logs(self, name: str, since: int) -> LogsResponse:
        """Get historical application logs.

        Parameters
        ----------
        name:
            Project name.
        since:
            Unix timestamp – return logs created after this time.
        """
        data = await self._request(
            "GET",
            ep.LOGS.format(name=name),
            params={"since": since},
        )
        return LogsResponse.model_validate(data)

    # ═══════════════════════════════════════════════════════════
    #  Environment Variables
    # ═══════════════════════════════════════════════════════════

    async def update_envs(
        self, project: str, variables: list[dict[str, str]]
    ) -> dict[str, Any]:
        """Set or update environment variables for a project.

        Parameters
        ----------
        project:
            Project name.
        variables:
            List of ``{"key": "…", "value": "…"}`` dicts.
        """
        return await self._request(
            "POST",
            ep.UPDATE_ENVS,
            json={"project": project, "variables": variables},
        )

    # ═══════════════════════════════════════════════════════════
    #  Domains
    # ═══════════════════════════════════════════════════════════

    async def get_domains(self, project: str) -> dict[str, Any]:
        """List domains attached to a project.

        Parameters
        ----------
        project:
            Project name to filter by.
        """
        return await self._request(
            "GET", ep.DOMAINS, params={"project": project}
        )

    async def create_domain(self, name: str) -> dict[str, Any]:
        """Register a new custom domain.

        Parameters
        ----------
        name:
            Fully-qualified domain name (e.g. ``"example.com"``).
        """
        return await self._request(
            "POST", ep.DOMAINS, json={"name": name}
        )

    async def attach_domain(
        self, domain_id: str, project_id: str
    ) -> dict[str, Any]:
        """Attach an existing domain to a project.

        Parameters
        ----------
        domain_id:
            Domain identifier.
        project_id:
            Project identifier.
        """
        return await self._request(
            "POST",
            ep.DOMAINS_SET_PROJECT,
            json={"domainID": domain_id, "projectID": project_id},
        )

    # ═══════════════════════════════════════════════════════════
    #  Disks & Backups
    # ═══════════════════════════════════════════════════════════

    async def get_disks(self, name: str) -> dict[str, Any]:
        """List persistent disks for a project.

        Parameters
        ----------
        name:
            Project name.
        """
        return await self._request("GET", ep.DISKS.format(name=name))

    async def create_disk(
        self, name: str, disk_name: str, size: int
    ) -> dict[str, Any]:
        """Provision a new persistent disk.

        Parameters
        ----------
        name:
            Project name.
        disk_name:
            Name for the new disk.
        size:
            Disk size in GiB.
        """
        return await self._request(
            "POST",
            ep.DISKS.format(name=name),
            json={"name": disk_name, "size": size},
        )

    async def get_disk_backups(
        self, name: str, disk_id: str
    ) -> dict[str, Any]:
        """List backups for a specific disk.

        Parameters
        ----------
        name:
            Project name.
        disk_id:
            Disk identifier.
        """
        return await self._request(
            "GET", ep.DISK_BACKUPS.format(name=name, disk_id=disk_id)
        )

    async def create_disk_backup(
        self, name: str, disk_id: str
    ) -> dict[str, Any]:
        """Create a new backup for a disk.

        Parameters
        ----------
        name:
            Project name.
        disk_id:
            Disk identifier.
        """
        return await self._request(
            "POST", ep.DISK_BACKUPS.format(name=name, disk_id=disk_id)
        )

    # ═══════════════════════════════════════════════════════════
    #  User & Billing
    # ═══════════════════════════════════════════════════════════

    async def get_user(self) -> dict[str, Any]:
        """Get the authenticated user's profile."""
        return await self._request("GET", ep.USER_ME)

    async def get_billing(self) -> dict[str, Any]:
        """Get the current billing summary."""
        return await self._request("GET", ep.BILLING)
