"""Tests for the tamper-evident, hash-chained audit trail."""

import json
import os

import pytest

from liara_agent.storage.audit import AuditLogger


@pytest.fixture
def audit_logger(tmp_path):
    return AuditLogger(log_path=tmp_path / "audit.log", key_path=tmp_path / "audit.key")


def test_log_creates_chained_records(audit_logger):
    for i in range(3):
        audit_logger.log(action=f"op_{i}", target="app", risk_level="medium")

    records = audit_logger.read_all()
    assert len(records) == 3

    # Chain: each record points at its predecessor's hash.
    assert records[0]["prev_hash"] == "0" * 64
    assert records[1]["prev_hash"] == records[0]["hash"]
    assert records[2]["prev_hash"] == records[1]["hash"]
    # Sequential numbering
    assert [r["seq"] for r in records] == [1, 2, 3]


def test_verify_accepts_intact_chain(audit_logger):
    audit_logger.log(action="deploy", target="app")
    audit_logger.log(action="restart", target="app", risk_level="medium")
    ok, message = audit_logger.verify()
    assert ok is True
    assert "سالم" in message


def test_verify_detects_tampered_record(audit_logger):
    audit_logger.log(action="deploy", target="app")
    audit_logger.log(action="scale", target="app", risk_level="high")

    # Tamper: rewrite the first record's action silently.
    lines = audit_logger.log_path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record["action"] = "innocent_read"
    lines[0] = json.dumps(record, ensure_ascii=False)
    audit_logger.log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, message = audit_logger.verify()
    assert ok is False
    assert "دستکاری" in message or "گسسته" in message


def test_verify_detects_deleted_record(audit_logger):
    audit_logger.log(action="op1", target="app")
    audit_logger.log(action="op2", target="app")
    audit_logger.log(action="op3", target="app")

    lines = audit_logger.log_path.read_text(encoding="utf-8").splitlines()
    del lines[1]  # remove the middle record
    audit_logger.log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, message = audit_logger.verify()
    assert ok is False


def test_verify_detects_appended_foreign_record(audit_logger):
    audit_logger.log(action="op1", target="app")
    # Attacker appends a fake record without knowing the HMAC key.
    fake = {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "seq": 2,
        "prev_hash": audit_logger.read_all()[0]["hash"],
        "action": "fake",
        "target": "x",
        "risk_level": "low",
        "status": "success",
        "details": {},
        "hash": "a" * 64,
    }
    with open(audit_logger.log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(fake, ensure_ascii=False) + "\n")

    ok, _ = audit_logger.verify()
    assert ok is False


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_audit_log_is_owner_only(audit_logger):
    audit_logger.log(action="op1", target="app")
    mode = oct(audit_logger.log_path.stat().st_mode & 0o777)
    assert mode == "0o600"


def test_get_recent_returns_newest_first(audit_logger):
    for i in range(5):
        audit_logger.log(action=f"op_{i}", target="app")
    recent = audit_logger.get_recent(limit=2)
    assert len(recent) == 2
    assert recent[0]["action"] == "op_4"
    assert recent[1]["action"] == "op_3"


def test_different_keys_produce_different_hashes(tmp_path):
    logger_a = AuditLogger(log_path=tmp_path / "a.log", key_path=tmp_path / "key_a")
    logger_b = AuditLogger(log_path=tmp_path / "b.log", key_path=tmp_path / "key_b")
    rec_a = logger_a.log(action="same", target="same")
    rec_b = logger_b.log(action="same", target="same")
    assert rec_a["hash"] != rec_b["hash"]
