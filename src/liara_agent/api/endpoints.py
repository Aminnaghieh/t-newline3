"""API endpoint path constants for the Liara PaaS REST API.

Centralises all URL paths so they can be changed in one place.
Parameterised paths are plain format-strings – call ``.format(name=…)``
or use an f-string with the constant.
"""

from __future__ import annotations

# ── Apps / Projects ──────────────────────────────────────────
PROJECTS = "/v1/projects"
PROJECT = "/v1/projects/{name}"
PROJECT_RESTART = "/v1/projects/{name}/actions/restart"
PROJECT_SCALE = "/v1/projects/{name}/actions/scale"
PROJECT_RESIZE = "/v1/projects/{name}/resize"
PROJECT_ZERO_DOWNTIME = "/v1/projects/{name}/zero-downtime/{status}"

# ── Deployments ──────────────────────────────────────────────
SOURCES_UPLOAD = "/v2/projects/{name}/sources"
RELEASES_CREATE = "/v2/projects/{name}/releases"
RELEASES_LIST = "/v1/projects/{name}/releases"
EVENTS = "/v1/projects/{name}/events"

# ── Monitoring & Logs ────────────────────────────────────────
REPORTS = "/v1/projects/{name}/reports"
LOGS = "/v1/projects/{name}/logs"

# ── Environment Variables ────────────────────────────────────
UPDATE_ENVS = "/v1/projects/update-envs"

# ── Domains ──────────────────────────────────────────────────
DOMAINS = "/v1/domains"
DOMAINS_SET_PROJECT = "/v1/domains/set-project"

# ── Disks & Backups ──────────────────────────────────────────
DISKS = "/v1/projects/{name}/disks"
DISK_BACKUPS = "/v1/projects/{name}/disks/{disk_id}/backups"

# ── User & Billing ───────────────────────────────────────────
USER_ME = "/v1/me"
BILLING = "/v1/billing"
