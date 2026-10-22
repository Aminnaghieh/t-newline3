"""Immutable audit trail logger for operations and modifications."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from liara_agent.utils.config import AUDIT_LOG_PATH


class AuditLogger:
    """Logs every critical operation to an append-only JSONL file."""

    def __init__(self, log_path: Path = AUDIT_LOG_PATH) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        action: str,
        target: str = "",
        risk_level: str = "low",
        status: str = "success",
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record an operation in the audit trail."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "target": target,
            "risk_level": risk_level,
            "status": status,
            "details": details or {},
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve most recent audit records."""
        if not self.log_path.exists():
            return []
        records: list[dict[str, Any]] = []
        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        continue
        return records[-limit:][::-1]


default_audit_logger = AuditLogger()
