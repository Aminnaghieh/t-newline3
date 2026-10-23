"""Tamper-evident audit trail logger with a cryptographic hash chain.

Every record is chained to its predecessor: ``record.hash = HMAC-SHA256(key,
seq | prev_hash | canonical_payload)``.  The HMAC key is generated once and
stored with owner-only permissions next to the log file.  Any modification,
deletion or reordering of past records breaks the chain and is detected by
:func:`AuditLogger.verify` — satisfying the ``ARCHITECTURE.md §5`` contract
that all sensitive operations leave an immutable trail.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from liara_agent.utils.config import AUDIT_LOG_PATH, DATA_DIR

logger = logging.getLogger(__name__)

# The HMAC key lives next to the audit log and is created with 0600 perms.
AUDIT_KEY_PATH = DATA_DIR / "audit.key"

_GENESIS_HASH = "0" * 64


def _load_or_create_key(key_path: Path) -> bytes:
    """Load the HMAC key, creating a random one on first use."""
    try:
        if key_path.exists():
            key = key_path.read_bytes().strip()
            if key:
                return key
        key = secrets.token_bytes(32)
        # Create atomically with owner-only permissions *before* writing.
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(key.hex().encode())
        return key
    except OSError:
        logger.warning("Audit HMAC key unavailable; chain falls back to unkeyed digest")
        return b"liara-agent-audit-fallback-key"


class AuditLogger:
    """Append-only, hash-chained audit trail (JSONL)."""

    def __init__(
        self,
        log_path: Path = AUDIT_LOG_PATH,
        key_path: Path | None = None,
    ) -> None:
        self.log_path = log_path
        self.key_path = key_path or AUDIT_KEY_PATH
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._key = _load_or_create_key(self.key_path)

    # ── Core API ─────────────────────────────────────────────

    def log(
        self,
        action: str,
        target: str = "",
        risk_level: str = "low",
        status: str = "success",
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record an operation in the tamper-evident audit trail."""
        prev_hash, seq = self._tail()
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "seq": seq + 1,
            "prev_hash": prev_hash,
            "action": action,
            "target": target,
            "risk_level": risk_level,
            "status": status,
            "details": details or {},
        }
        record["hash"] = self._compute_hash(record)

        line = json.dumps(record, ensure_ascii=False, sort_keys=False)
        # Ensure the file is owner-readable-only before the first write.
        self._ensure_private_file()
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return record

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve the most recent audit records (newest first)."""
        return list(reversed(self.read_all()[-limit:]))

    def read_all(self) -> list[dict[str, Any]]:
        """Parse every record in the audit file (oldest first)."""
        if not self.log_path.exists():
            return []
        records: list[dict[str, Any]] = []
        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except Exception:
                    continue
                if isinstance(parsed, dict):
                    records.append(parsed)
        return records

    # ── Integrity verification ───────────────────────────────

    def verify(self) -> tuple[bool, str]:
        """Verify the whole hash chain.

        Returns ``(ok, message)`` — ``ok=False`` means the trail has been
        tampered with, truncated, or corrupted.
        """
        records = self.read_all()
        prev = _GENESIS_HASH
        for idx, rec in enumerate(records, start=1):
            stored_hash = rec.get("hash", "")
            expected = self._compute_hash({k: v for k, v in rec.items() if k != "hash"})
            if not hmac.compare_digest(stored_hash, expected):
                return False, f"رکورد #{idx} دستکاری شده است (hash mismatch)"
            if rec.get("prev_hash") != prev:
                return False, f"زنجیره در رکورد #{idx} گسسته است (prev_hash mismatch)"
            if rec.get("seq") != idx:
                return False, f"شماره توالی در رکورد #{idx} نامعتبر است"
            prev = stored_hash
        return True, f"زنجیره ممیزی سالم است ({len(records)} رکورد)"

    # ── Internals ────────────────────────────────────────────

    def _compute_hash(self, record: dict[str, Any]) -> str:
        payload = json.dumps(record, ensure_ascii=False, sort_keys=True)
        mac = hmac.new(self._key, payload.encode("utf-8"), hashlib.sha256)
        return mac.hexdigest()

    def _tail(self) -> tuple[str, int]:
        records = self.read_all()
        if not records:
            return _GENESIS_HASH, 0
        last = records[-1]
        return str(last.get("hash", _GENESIS_HASH)), int(last.get("seq", len(records)))

    def _ensure_private_file(self) -> None:
        if os.name != "posix":
            return
        try:
            if not self.log_path.exists():
                fd = os.open(self.log_path, os.O_WRONLY | os.O_CREAT, 0o600)
                os.close(fd)
            self.log_path.chmod(0o600)
        except OSError:  # pragma: no cover — best effort
            logger.debug("chmod on audit log failed", exc_info=True)


default_audit_logger = AuditLogger()


def audit(
    action: str,
    target: str = "",
    risk_level: str = "low",
    status: str = "success",
    details: dict[str, Any] | None = None,
) -> None:
    """Module-level convenience: log to the default audit trail, never raises."""
    try:
        default_audit_logger.log(
            action=action,
            target=target,
            risk_level=risk_level,
            status=status,
            details=details or {},
        )
    except Exception:  # pragma: no cover — audit must never break operations
        logger.debug("audit logging failed", exc_info=True)
