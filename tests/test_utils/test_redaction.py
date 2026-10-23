"""Tests for the secret-redaction layer used before LLM calls."""

from liara_agent.utils.redaction import redact_mapping, redact_secrets


def test_redacts_bearer_token():
    text = "Authorization: Bearer liara_sk_abcdef1234567890"
    out = redact_secrets(text)
    assert "liara_sk_abcdef1234567890" not in out
    assert "Authorization: Bearer" in out
    assert "REDACTED" in out


def test_redacts_openai_style_key():
    out = redact_secrets("using key sk-abcdefghij1234567890abcd")
    assert "sk-abcdefghij1234567890abcd" not in out
    assert "REDACTED" in out


def test_redacts_url_credentials():
    out = redact_secrets("connect to postgres://admin:s3cr3tpw@db.internal:5432/app")
    assert "s3cr3tpw" not in out
    assert "postgres://admin:" in out  # structure preserved
    assert "db.internal:5432/app" in out


def test_redacts_kv_password():
    out = redact_secrets("failed login password=hunter2secret retried")
    assert "hunter2secret" not in out
    assert "password=" in out


def test_redacts_jwt():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    out = redact_secrets(f"token {jwt} expired")
    assert jwt not in out


def test_redacts_aws_key():
    out = redact_secrets("key AKIAIOSFODNN7EXAMPLE invalid")
    assert "AKIAIOSFODNN7EXAMPLE" not in out


def test_redaction_is_idempotent():
    once = redact_secrets("Authorization: Bearer supersecrettoken123")
    twice = redact_secrets(once)
    assert once == twice


def test_plain_text_untouched():
    text = "GET /api/health 200 OK in 32ms"
    assert redact_secrets(text) == text


def test_redact_mapping_nested():
    data = {
        "logs": ["Authorization: Bearer abcdefsecret123", "ok line"],
        "meta": {"db": "mysql://root:topw@host/db"},
        "count": 3,
    }
    out = redact_mapping(data)
    dumped = str(out)
    assert "abcdefsecret123" not in dumped
    assert "topw" not in dumped
    assert out["count"] == 3
    assert "ok line" in out["logs"]
