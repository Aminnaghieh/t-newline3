"""Tiny JSON-file cache used to keep the CLI usable when Liara is offline.

The cache stores the last successful response for a handful of read-only
endpoints (project list, project detail, logs, events).  It is intentionally
minimal: one file per key, no eviction, no TTL beyond a "stale" flag that the
caller decides how to surface.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default location: alongside the SQLite DB used by the rest of the agent.
_CACHE_DIR = Path.home() / ".liara-agent" / "cache"


def _path_for(key: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
    return _CACHE_DIR / f"{safe}.json"


def save(key: str, payload: Any) -> None:
    """Persist ``payload`` under ``key``; never raises."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        record = {"ts": time.time(), "payload": payload}
        _path_for(key).write_text(
            json.dumps(record, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except Exception as exc:  # pragma: no cover - best effort
        logger.debug("cache save failed for %s: %s", key, exc)


def load(key: str) -> tuple[Any, float] | None:
    """Return ``(payload, age_seconds)`` or ``None`` if nothing is cached."""
    try:
        path = _path_for(key)
        if not path.exists():
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        age = max(0.0, time.time() - float(record.get("ts", 0)))
        return record.get("payload"), age
    except Exception as exc:  # pragma: no cover
        logger.debug("cache load failed for %s: %s", key, exc)
        return None