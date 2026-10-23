"""Shared helpers for CLI commands — token resolution and exit messaging."""

from __future__ import annotations

import typer

from liara_agent.cli.theme import console, onboarding_hint
from liara_agent.storage.credentials import resolve_liara_token


def require_token() -> str:
    """Resolve the Liara API token or exit with onboarding guidance.

    Single source of truth used by every command — previously each command
    had its own (sometimes divergent) resolution logic.
    """
    token = resolve_liara_token()
    if not token:
        onboarding_hint(console)
        raise typer.Exit(1)
    return token


def cancelled(message: str = "عملیات لغو شد.") -> None:
    """Print a uniform cancellation message."""
    console.print(f"[yellow]{message}[/yellow]")
