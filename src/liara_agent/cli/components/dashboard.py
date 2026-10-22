"""Live metrics dashboard component using Rich Live display."""

from __future__ import annotations

from datetime import datetime, timezone

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def _color_for_value(value: float) -> str:
    """Return a Rich color name based on percentage thresholds.

    - Green  : < 50%
    - Yellow : 50–80%
    - Red    : > 80%
    """
    if value < 50.0:
        return "green"
    if value <= 80.0:
        return "yellow"
    return "red"


def _health_icon(value: float) -> str:
    """Return a health indicator icon based on value."""
    if value < 50.0:
        return "🟢"
    if value <= 80.0:
        return "🟡"
    return "🔴"


def _build_metrics_table(project_name: str, metrics: dict) -> Table:
    """Build a Rich table from metrics data.

    Expected metrics dict keys:
        cpu_percent, memory_percent, memory_used_mb, memory_total_mb,
        network_rx_bytes, network_tx_bytes, disk_used_mb, disk_total_mb
    """
    table = Table(
        title=f"📊 داشبورد متریک‌ها — {project_name}",
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
        padding=(0, 1),
    )
    table.add_column("متریک", style="bold", no_wrap=True, width=18)
    table.add_column("مقدار", justify="center", width=15)
    table.add_column("وضعیت", justify="center", width=8)
    table.add_column("نوار", width=25)

    # CPU
    cpu = metrics.get("cpu_percent", 0.0)
    cpu_color = _color_for_value(cpu)
    cpu_bar = _progress_bar(cpu)
    table.add_row(
        "🖥️  CPU",
        f"[{cpu_color}]{cpu:.1f}%[/{cpu_color}]",
        _health_icon(cpu),
        cpu_bar,
    )

    # Memory
    mem = metrics.get("memory_percent", 0.0)
    mem_used = metrics.get("memory_used_mb", 0)
    mem_total = metrics.get("memory_total_mb", 0)
    mem_color = _color_for_value(mem)
    mem_bar = _progress_bar(mem)
    table.add_row(
        "💾 حافظه",
        f"[{mem_color}]{mem:.1f}%[/{mem_color}] ({mem_used}/{mem_total} MB)",
        _health_icon(mem),
        mem_bar,
    )

    # Network
    net_rx = metrics.get("network_rx_bytes", 0)
    net_tx = metrics.get("network_tx_bytes", 0)
    table.add_row(
        "🌐 شبکه (دریافت)",
        _format_bytes(net_rx),
        "📥",
        "",
    )
    table.add_row(
        "🌐 شبکه (ارسال)",
        _format_bytes(net_tx),
        "📤",
        "",
    )

    # Disk
    disk_used = metrics.get("disk_used_mb", 0)
    disk_total = metrics.get("disk_total_mb", 1)
    disk_pct = (disk_used / disk_total * 100) if disk_total else 0.0
    disk_color = _color_for_value(disk_pct)
    disk_bar = _progress_bar(disk_pct)
    table.add_row(
        "💿 دیسک",
        f"[{disk_color}]{disk_pct:.1f}%[/{disk_color}] ({disk_used}/{disk_total} MB)",
        _health_icon(disk_pct),
        disk_bar,
    )

    return table


def _progress_bar(percent: float, width: int = 20) -> str:
    """Create a text-based progress bar."""
    filled = int(width * min(percent, 100) / 100)
    empty = width - filled
    color = _color_for_value(percent)
    return f"[{color}]{'█' * filled}{'░' * empty}[/{color}]"


def _format_bytes(size: int | float) -> str:
    """Format byte count to human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def _build_alerts_panel(metrics: dict) -> Panel:
    """Build an alerts panel highlighting problematic metrics."""
    alerts: list[str] = []

    cpu = metrics.get("cpu_percent", 0.0)
    mem = metrics.get("memory_percent", 0.0)
    disk_used = metrics.get("disk_used_mb", 0)
    disk_total = metrics.get("disk_total_mb", 1)
    disk_pct = (disk_used / disk_total * 100) if disk_total else 0.0

    if cpu > 80:
        alerts.append(f"[red]⚠️  CPU بالا: {cpu:.1f}% — بررسی مصرف پردازنده[/red]")
    elif cpu > 50:
        alerts.append(f"[yellow]📌 CPU متوسط: {cpu:.1f}%[/yellow]")

    if mem > 80:
        alerts.append(f"[red]⚠️  حافظه بالا: {mem:.1f}% — خطر OOM[/red]")
    elif mem > 50:
        alerts.append(f"[yellow]📌 حافظه متوسط: {mem:.1f}%[/yellow]")

    if disk_pct > 80:
        alerts.append(f"[red]⚠️  دیسک پر: {disk_pct:.1f}% — فضای دیسک رو به اتمام[/red]")

    if not alerts:
        alerts.append("[green]✅ همه متریک‌ها در محدوده نرمال[/green]")

    return Panel(
        "\n".join(alerts),
        title="🔔 هشدارها",
        border_style="yellow" if any("⚠️" in a for a in alerts) else "green",
        padding=(1, 2),
    )


def show_dashboard(project_name: str, metrics: dict) -> None:
    """Display a static metrics dashboard for a project.

    Args:
        project_name: The Liara project name.
        metrics: Dict with metric values (cpu_percent, memory_percent, etc.).
    """
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    metrics_table = _build_metrics_table(project_name, metrics)
    alerts_panel = _build_alerts_panel(metrics)

    console.print()
    console.print(metrics_table)
    console.print(alerts_panel)
    console.print(f"[dim]آخرین بروزرسانی: {now}[/dim]\n")


def show_live_dashboard(
    project_name: str,
    fetch_metrics_fn,
    refresh_interval: int = 10,
) -> None:
    """Display a live auto-refreshing metrics dashboard.

    Args:
        project_name: The Liara project name.
        fetch_metrics_fn: Callable that returns a metrics dict.
        refresh_interval: Seconds between refreshes.
    """
    import time

    def _generate_display() -> Table:
        metrics = fetch_metrics_fn()
        return _build_metrics_table(project_name, metrics)

    console.print(
        f"[bold cyan]📊 داشبورد زنده — {project_name}[/bold cyan]"
    )
    console.print(
        f"[dim]بروزرسانی هر {refresh_interval} ثانیه | Ctrl+C برای خروج[/dim]\n"
    )

    try:
        with Live(_generate_display(), console=console, refresh_per_second=1) as live:
            while True:
                time.sleep(refresh_interval)
                metrics = fetch_metrics_fn()
                table = _build_metrics_table(project_name, metrics)
                alerts = _build_alerts_panel(metrics)
                live.update(table)
    except KeyboardInterrupt:
        console.print("\n[yellow]داشبورد متوقف شد.[/yellow]")
