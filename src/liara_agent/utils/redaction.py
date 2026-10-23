"""Secret redaction layer — strips credentials before data leaves the machine.

Runtime logs and events frequently embed database URLs, bearer tokens,
API keys and raw ``Authorization`` headers.  Before any of that context is
handed to a remote LLM (or printed to a shared terminal) it must pass
through :func:`redact_secrets` so secrets never leave the user's machine.

The redactor is intentionally conservative: it over-matches rather than
under-matches, replacing the *value* while keeping enough of the shape for
the LLM to reason about the log line.
"""

from __future__ import annotations

import re

# Pre-compiled patterns.  Each pattern replaces the *sensitive capture group*
# with a fixed placeholder, preserving the surrounding structure.
_PATTERNS: list[re.Pattern[str]] = [
    # Bearer / token authorization headers (Authorization: Bearer xxx)
    re.compile(r"(?i)(authorization\s*[:=]\s*)(bearer\s+)?(?P<secret>[A-Za-z0-9\-._~+/=]{8,})"),
    # OpenAI-style API keys
    re.compile(r"(?P<secret>sk-[A-Za-z0-9\-_]{16,})"),
    # Generic API keys / tokens passed as query params or key=value pairs
    re.compile(
        r"(?i)\b((?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|"
        r"secret|password|passwd|pwd|token|client[_-]?secret)\s*[=:]\s*)"
        r"(?P<secret>[^\s&\"';,]{6,})"
    ),
    # URL-embedded credentials: scheme://user:password@host
    re.compile(
        r"(?P<prefix>\b[a-z][a-z0-9+.\-]*://[^\s/:@\"']+:)(?P<secret>[^\s@\"'/]+)(?=@)"
    ),
    # JWT-like tokens (three base64url segments)
    re.compile(r"(?P<secret>eyJ[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,})"),
    # AWS access keys
    re.compile(r"(?P<secret>AKIA[0-9A-Z]{16})"),
    # Liara API tokens
    re.compile(r"(?P<secret>liara_[A-Za-z0-9\-_]{10,})"),
]

_REDACTED = "«REDACTED»"


def redact_secrets(text: str) -> str:
    """Return ``text`` with every detected secret replaced by a placeholder.

    Idempotent: already-redacted text passes through unchanged.
    """
    if not text:
        return text
    result = text
    for pattern in _PATTERNS:
        result = pattern.sub(_replace, result)
    return result


def _replace(match: re.Match[str]) -> str:
    # Keep everything before the secret (e.g. "Authorization: Bearer ",
    # "postgres://user:") visible and replace only the secret value.
    head = match.group(0)[: match.start("secret") - match.start(0)]
    return f"{head}{_REDACTED}"


def redact_text_lines(lines: list[str]) -> list[str]:
    """Redact a list of log/event lines in place (returns a new list)."""
    return [redact_secrets(line) for line in lines]


def redact_mapping(data: dict) -> dict:
    """Recursively redact all string values inside a mapping."""
    out: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            out[key] = redact_secrets(value)
        elif isinstance(value, dict):
            out[key] = redact_mapping(value)
        elif isinstance(value, list):
            out[key] = [
                redact_secrets(v) if isinstance(v, str)
                else redact_mapping(v) if isinstance(v, dict)
                else v
                for v in value
            ]
        else:
            out[key] = value
    return out
