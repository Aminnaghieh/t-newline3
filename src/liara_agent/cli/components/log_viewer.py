"""Log viewer component with syntax highlighting and filtering."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# Log level color mapping
LEVEL_STYLES: dict[str, str] = {
    "debug": "dim white",
    "info": "green",
    "warn": "yellow",
    "warning": "yellow",
    "error": "bold red",
    "fatal": "bold white on red",
    "critical": "bold white on red",
}

LEVEL_ICONS: dict[str, str] = {
    "debug": "🔍",
    "info": "ℹ️ ",
    "warn": "⚠️ ",
    "warning": "⚠️ ",
    "error": "❌",
    "fatal": "💀",
    "critical": "💀",
}


def _format_log_timestamp(ts: str | None) -> Text:
    """Format a log timestamp with dim styling."""
    if not ts:
        return Text("—", style="dim")
    try:
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        formatted = dt.strftime("%H:%M:%S.%f")[:-3]
    except (ValueError, TypeError):
        formatted = str(ts)
    return Text(formatted, style="dim cyan")


def _format_log_level(level: str) -> Text:
    """Format a log level with appropriate color."""
    normalized = level.lower().strip()
    style = LEVEL_STYLES.get(normalized, "white")
    icon = LEVEL_ICONS.get(normalized, "📝")
    label = normalized.upper().ljust(7)
    return Text(f"{icon} {label}", style=style)


def _highlight_message(message: str, grep: str | None = None) -> Text:
    """Highlight log message text, optionally highlighting grep matches."""
    text = Text(message)

    # Highlight common log patterns
    # IP addresses
    for match in re.finditer(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", message):
        text.stylize("cyan", match.start(), match.end())

    # HTTP status codes
    for match in re.finditer(r"\b[1-5]\d{2}\b", message):
        code = int(match.group())
        if 200 <= code < 300:
            text.stylize("green", match.start(), match.end())
        elif 300 <= code < 400:
            text.stylize("yellow", match.start(), match.end())
        elif code >= 400:
            text.stylize("red", match.start(), match.end())

    # URLs / paths
    for match in re.finditer(r'(?:https?://|/)\S+', message):
        text.stylize("underline blue", match.start(), match.end())

    # Highlight grep matches
    if grep:
        for match in re.finditer(re.escape(grep), message, re.IGNORECASE):
            text.stylize("bold white on magenta", match.start(), match.end())

    return text


def render_logs(
    logs: list[dict],
    grep: str | None = None,
    project_name: str = "",
) -> None:
    """Render a list of log entries with syntax highlighting.

    Args:
        logs: List of log entry dicts with keys: timestamp, message, level, source.
        grep: Optional pattern to filter and highlight in log messages.
        project_name: Optional project name for the panel title.
    """
    # Filter by grep pattern if provided
    if grep:
        filtered = [
            log for log in logs
            if re.search(re.escape(grep), log.get("message", ""), re.IGNORECASE)
        ]
    else:
        filtered = logs

    if not filtered:
        if grep:
            console.print(
                f"[yellow]هیچ لاگی با الگوی '{grep}' یافت نشد.[/yellow]"
            )
        else:
            console.print("[yellow]هیچ لاگی موجود نیست.[/yellow]")
        return

    # Build log table
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
        expand=True,
    )
    table.add_column("زمان", width=14, no_wrap=True)
    table.add_column("سطح", width=12, no_wrap=True)
    table.add_column("پیام", ratio=1)

    for entry in filtered:
        ts = _format_log_timestamp(entry.get("timestamp"))
        level = _format_log_level(entry.get("level", "info"))
        msg = _highlight_message(entry.get("message", ""), grep=grep)
        table.add_row(ts, level, msg)

    title = f"📋 لاگ‌ها — {project_name}" if project_name else "📋 لاگ‌ها"
    if grep:
        title += f" (فیلتر: {grep})"

    panel = Panel(
        table,
        title=title,
        border_style="blue",
        padding=(0, 0),
    )
    console.print(panel)
    console.print(f"[dim]تعداد: {len(filtered)} / {len(logs)} لاگ[/dim]\n")


def render_single_log(entry: dict, grep: str | None = None) -> None:
    """Render a single log entry (for live streaming).

    Args:
        entry: Log entry dict with keys: timestamp, message, level, source.
        grep: Optional pattern to highlight in the message.
    """
    ts = _format_log_timestamp(entry.get("timestamp"))
    level = _format_log_level(entry.get("level", "info"))
    msg = _highlight_message(entry.get("message", ""), grep=grep)

    output = Text()
    output.append_text(ts)
    output.append(" │ ")
    output.append_text(level)
    output.append(" │ ")
    output.append_text(msg)

    console.print(output)


def render_log_line(
    console_inst: Console,
    message: str,
    timestamp: str | None = None,
    level: str = "info",
    grep: str | None = None,
) -> None:
    """Render a single formatted log line to console."""
    entry = {"message": message, "timestamp": timestamp, "level": level}
    render_single_log(entry, grep=grep)

