"""Log viewer component with syntax highlighting, level filtering, and legend."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from liara_agent.cli.theme import BOX, console, escape_markup

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

# Numeric severity used for --level filtering (>= shown).
LEVEL_ORDER: dict[str, int] = {
    "debug": 10,
    "info": 20,
    "warn": 30,
    "warning": 30,
    "error": 40,
    "fatal": 50,
    "critical": 50,
}


def _format_log_timestamp(ts: str | None) -> Text:
    """Format a log timestamp with dim styling."""
    if not ts:
        return Text("—", style="dim")
    try:
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            dt = datetime.fromtimestamp(float(ts), tz=UTC)
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
    min_level: str | None = None,
) -> None:
    """Render a list of log entries with syntax highlighting.

    Args:
        logs: List of log entry dicts with keys: timestamp, message, level, source.
        grep: Optional pattern to filter and highlight in log messages.
        project_name: Optional project name for the panel title.
        min_level: Optional minimum severity (debug < info < warn < error < fatal).
    """
    filtered = logs

    # Severity filter
    if min_level:
        floor = LEVEL_ORDER.get(min_level.lower())
        if floor is None:
            console.print(
                f"[yellow]سطح لاگ نامعتبر: '{min_level}' — معتبرها: debug/info/warn/error/fatal[/yellow]"
            )
            return
        filtered = [
            log for log in filtered
            if LEVEL_ORDER.get(str(log.get("level", "info")).lower(), 20) >= floor
        ]

    # Grep filter
    if grep:
        filtered = [
            log for log in filtered
            if re.search(re.escape(grep), log.get("message", ""), re.IGNORECASE)
        ]

    if not filtered:
        if grep:
            console.print(
                f"[yellow]هیچ لاگی با الگوی '{escape_markup(grep)}' یافت نشد.[/yellow]"
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

    proj_escaped = escape_markup(project_name) if project_name else ""
    title = f"📋 لاگ‌ها — {proj_escaped}" if project_name else "📋 لاگ‌ها"
    if grep:
        title += f" (فیلتر: {escape_markup(grep)})"
    if min_level:
        title += f" (سطح ≥ {min_level.upper()})"

    panel = Panel(
        table,
        title=title,
        border_style="blue",
        box=BOX,
        padding=(0, 0),
    )
    console.print(panel)

    # Summary + severity legend
    counts: dict[str, int] = {}
    for entry in filtered:
        lvl = str(entry.get("level", "info")).lower()
        counts[lvl] = counts.get(lvl, 0) + 1
    legend = Text("تعداد: ", style="dim")
    legend.append(f"{len(filtered)}", style="bold white")
    legend.append(f" / {len(logs)} لاگ", style="dim")
    if counts:
        legend.append("   •   ", style="dim")
        parts = []
        for lvl in ("error", "warn", "info", "debug"):
            if counts.get(lvl):
                parts.append(f"{LEVEL_ICONS.get(lvl, '')} {lvl}: {counts[lvl]}")
        legend.append("  ".join(parts), style="dim")
    console.print(legend)
    console.print()


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

