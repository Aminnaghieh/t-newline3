"""Tiny JSON-file cache used to keep the CLI usable when Liara is offline.

The cache stores the last successful response for a handful of read-only
endpoints (project list, project detail, logs, events).  It is intentionally
minimal, but hardened:

- the cache directory is ``0700`` and files ``0600`` (API responses can
  contain project metadata and log fragments);
- entries expire after ``CACHE_TTL_SECONDS``;
- oversized payloads are never written and the directory has a total size
  cap with oldest-first eviction.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from liara_agent.utils.config import DATA_DIR
from liara_agent.utils.constants import (
    CACHE_MAX_DIR_BYTES,
    CACHE_MAX_ITEM_BYTES,
    CACHE_TTL_SECONDS,
)

logger = logging.getLogger(__name__)

# Central data dir alongside the SQLite DB and audit log.
_CACHE_DIR = DATA_DIR / "cache"


def _path_for(key: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
    return _CACHE_DIR / f"{safe}.json"


def _ensure_private_dir() -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        try:
            _CACHE_DIR.chmod(0o700)
        except OSError:  # pragma: no cover — best effort
            pass


def _evict_if_needed() -> None:
    """Keep the cache directory under its total size cap (oldest first)."""
    try:
        files = [p for p in _CACHE_DIR.glob("*.json") if p.is_file()]
        total = sum(p.stat().st_size for p in files)
        if total <= CACHE_MAX_DIR_BYTES:
            return
        files.sort(key=lambda p: p.stat().st_mtime)
        for p in files:
            if total <= CACHE_MAX_DIR_BYTES:
                break
            size = p.stat().st_size
            p.unlink(missing_ok=True)
            total -= size
    except OSError:  # pragma: no cover — best effort
        logger.debug("cache eviction failed", exc_info=True)


def save(key: str, payload: Any) -> None:
    """Persist ``payload`` under ``key``; never raises."""
    try:
        _ensure_private_dir()
        blob = json.dumps(
            {"ts": time.time(), "payload": payload}, ensure_ascii=False, default=str
        )
        if len(blob.encode("utf-8")) > CACHE_MAX_ITEM_BYTES:
            logger.debug("cache payload for %s exceeds cap; skipping", key)
            return
        path = _path_for(key)
        # Write with owner-only permissions from the very first byte.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(blob)
        _evict_if_needed()
    except Exception as exc:  # pragma: no cover - best effort
        logger.debug("cache save failed for %s: %s", key, exc)


def load(key: str, max_age: float | None = None) -> tuple[Any, float] | None:
    """Return ``(payload, age_seconds)`` or ``None`` if nothing usable is cached.

    Entries older than ``max_age`` (default ``CACHE_TTL_SECONDS``) are
    treated as expired and removed.
    """
    ttl = CACHE_TTL_SECONDS if max_age is None else max_age
    try:
        path = _path_for(key)
        if not path.exists():
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        age = max(0.0, time.time() - float(record.get("ts", 0)))
        if age > ttl:
            path.unlink(missing_ok=True)
            return None
        return record.get("payload"), age
    except Exception as exc:  # pragma: no cover
        logger.debug("cache load failed for %s: %s", key, exc)
        return None
