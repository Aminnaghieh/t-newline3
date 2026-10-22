"""Formatting utilities for Persian/English output."""

from __future__ import annotations

from datetime import datetime, timezone

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from liara_agent.utils.constants import RiskLevel


def format_timestamp(ts: str | int | float | None) -> str:
    """Format a timestamp for display."""
    if ts is None:
        return "—"
    if isinstance(ts, (int, float)):
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    else:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_bytes(size: int | float) -> str:
    """Format byte count to human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def format_percentage(value: float) -> str:
    """Format a float as percentage with color hint."""
    return f"{value:.1f}%"


def risk_badge(level: RiskLevel) -> Text:
    """Create a colored risk badge."""
    colors = {
        RiskLevel.LOW: "green",
        RiskLevel.MEDIUM: "yellow",
        RiskLevel.HIGH: "red",
        RiskLevel.CRITICAL: "bold red",
    }
    labels = {
        RiskLevel.LOW: "🟢 کم‌ریسک",
        RiskLevel.MEDIUM: "🟡 متوسط",
        RiskLevel.HIGH: "🔴 پرریسک",
        RiskLevel.CRITICAL: "⛔ بحرانی",
    }
    return Text(labels[level], style=colors[level])


def create_status_panel(
    title: str,
    content: str,
    status: str = "info",
) -> Panel:
    """Create a styled status panel."""
    border_styles = {
        "info": "blue",
        "success": "green",
        "warning": "yellow",
        "error": "red",
    }
    icons = {
        "info": "ℹ️",
        "success": "✅",
        "warning": "⚠️",
        "error": "❌",
    }
    return Panel(
        content,
        title=f"{icons.get(status, 'ℹ️')} {title}",
        border_style=border_styles.get(status, "blue"),
        padding=(1, 2),
    )


def create_plan_table(plans: dict) -> Table:
    """Create a comparison table for Liara plans."""
    table = Table(title="📋 پلن‌های لیارا", show_header=True, header_style="bold cyan")
    table.add_column("پلن", style="bold")
    table.add_column("CPU", justify="center")
    table.add_column("RAM", justify="center")
    table.add_column("Disk", justify="center")
    table.add_column("Bandwidth", justify="center")
    table.add_column("توضیحات")

    for plan_id, info in plans.items():
        table.add_row(
            info["label"],
            f"{info['cpu']} Core",
            f"{info['ram_gb']} GB",
            f"{info['disk_gb']} GB",
            f"{info['bandwidth_gb']} GB",
            info["description"],
        )
    return table
