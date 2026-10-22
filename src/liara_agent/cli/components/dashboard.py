"""Beautiful live metrics dashboard for Liara projects, built on Rich.

The dashboard consumes a :class:`~liara_agent.models.metrics.MonitorSnapshot`
produced by :class:`~liara_agent.core.monitor.Monitor` and renders it as a
composite of panels:

1. Header — project identity + status chips (status/deployed/plan/scale).
2. Metrics table — current value, progress bar, sparkline and trend arrow
   for CPU, memory and network RX/TX.
3. Alerts + Recommendations panels side by side.
4. Footer with last-update timestamp.

Both a static renderer (``show_dashboard``) and a live, auto-refreshing
renderer (``show_live_dashboard``) are provided.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from liara_agent.models.metrics import MetricDataPoint, MonitorSnapshot

# ─── Display thresholds ──────────────────────────────────────
CPU_WARN = 70.0
CPU_CRIT = 85.0
MEM_WARN = 75.0
MEM_CRIT = 90.0

# ─── Visual constants ────────────────────────────────────────
BAR_WIDTH = 24
SPARK_POINTS = 24
SPARK_BLOCKS = "▁▂▃▄▅▆▇█"

STATUS_COLORS = {
    "running": "green",
    "starting": "yellow",
    "deploying": "yellow",
    "stopped": "red",
    "failed": "red",
    "unknown": "dim",
}


def severity_for(value: float, warn: float, crit: float) -> str:
    """Classify a percentage into ``"ok"`` / ``"warn"`` / ``"crit"``."""
    if value >= crit:
        return "crit"
    if value >= warn:
        return "warn"
    return "ok"


def color_for(value: float, warn: float, crit: float) -> str:
    """Rich color name for a percentage value."""
    return {"ok": "green", "warn": "yellow", "crit": "bold red"}[
        severity_for(value, warn, crit)
    ]


def progress_bar(
    percent: float,
    width: int = BAR_WIDTH,
    warn: float = 60.0,
    crit: float = 85.0,
) -> str:
    """Colored text progress bar, clamped to ``0..100``."""
    clamped = max(0.0, min(percent, 100.0))
    filled = int(width * clamped / 100)
    color = color_for(percent, warn, crit)
    return (
        f"[{color}]{'█' * filled}{'░' * (width - filled)}[/{color}]"
        f" [bold]{clamped:.1f}%[/]"
    )


def sparkline(
    series: list[MetricDataPoint],
    width: int = SPARK_POINTS,
    fixed_scale: float | None = None,
) -> Text:
    """Render the last ``width`` points of a series as a colored sparkline.

    ``fixed_scale`` pins the vertical scale (e.g. ``100`` for percentages);
    otherwise the series maximum is used.
    """
    values = [p.value for p in series[-width:]]
    if not values:
        return Text("—", style="dim")

    top = fixed_scale if fixed_scale is not None else max(values)
    top = top if top > 0 else 1.0

    chars = []
    for v in values:
        idx = int(len(SPARK_BLOCKS) * max(0.0, min(v, top)) / top)
        chars.append(SPARK_BLOCKS[min(idx, len(SPARK_BLOCKS) - 1)])

    last = values[-1]
    style = color_for(100 * last / top if top else 0, 60.0, 85.0)
    return Text("".join(chars), style=style)


def trend_arrow(series: list[MetricDataPoint], width: int = SPARK_POINTS) -> Text:
    """Arrow + Persian label showing whether the recent trend goes up or down."""
    values = [p.value for p in series[-width:]]
    if len(values) < 2:
        return Text("→", style="dim")
    half = len(values) // 2
    old = sum(values[:half]) / half
    new = sum(values[half:]) / (len(values) - half)

    if new > old * 1.1:
        return Text("↑ در حال رشد", style="bold red")
    if new < old * 0.9:
        return Text("↓ در حال کاهش", style="green")
    return Text("→ پایدار", style="dim")


def format_bytes(size: float) -> str:
    """Format a byte count as a human-readable string."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def _chip(label: str, color: str) -> Text:
    """A pill-like chip with inverted colors."""
    return Text(f" {label} ", style=f"bold black on {color}")


def _status_color(status: str) -> str:
    return STATUS_COLORS.get(status.lower(), "magenta")


def build_dashboard(snapshot: MonitorSnapshot) -> Group:
    """Assemble the full dashboard renderable from a snapshot."""
    header = _build_header(snapshot)
    metrics = _build_metrics_table(snapshot)
    footer = _build_footer(snapshot)

    side = Table.grid(padding=(0, 1))
    side.add_column(ratio=1)
    side.add_column(ratio=1)
    side.add_row(_build_alerts_panel(snapshot), _build_recommendations_panel(snapshot))

    return Group(header, metrics, side, footer)


def _build_header(snapshot: MonitorSnapshot) -> Panel:
    """Header: identity line + status chips."""
    status = (snapshot.status or "unknown").lower()
    sc = _status_color(status)

    identity = Text()
    identity.append("🛡️ ", style="bold cyan")
    identity.append("داشبورد پایش ", style="bold cyan")
    identity.append(snapshot.project_name, style=f"bold {sc} underline")
    identity.append("   ", style="dim")
    identity.append(
        "سلامت کلی: " + ("سالم" if snapshot.is_healthy else "ناسالم"),
        style="green" if snapshot.is_healthy else "bold red",
    )

    chips = Table.grid(padding=(0, 1))
    for _ in range(4):
        chips.add_column()
    chips.add_row(
        _chip(f"STATUS: {status.upper()}", sc),
        _chip(
            "DEPLOYED ✓" if snapshot.is_deployed else "NOT DEPLOYED ✗",
            "green" if snapshot.is_deployed else "red",
        ),
        _chip(f"PLAN: {snapshot.plan_id or '—'}", "blue"),
        _chip(f"SCALE: {snapshot.scale or 0}", "blue"),
    )

    body = Group(identity, Text(), chips)
    return Panel(
        body,
        border_style=sc,
        padding=(0, 1),
        title="🛡️ LIARA SRE AGENT",
        title_align="right",
        subtitle=snapshot.fetched_at or None,
    )


def _build_metrics_table(snapshot: MonitorSnapshot) -> Table:
    """Metrics table: current value, progress bar, sparkline and trend."""
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        expand=True,
        padding=(0, 1),
        caption="📊 آخرین نمونه‌های گزارش‌شده",
        caption_style="dim",
    )
    table.add_column("شاخص", style="bold", no_wrap=True)
    table.add_column("مقدار فعلی", justify="center", width=14)
    table.add_column("مقدار مصرف", width=BAR_WIDTH + 10)
    table.add_column(f"نمودار خام ({SPARK_POINTS} نمونه اخیر)", justify="center")
    table.add_column("روند", justify="center", no_wrap=True)

    cpu = snapshot.cpu_percent
    table.add_row(
        "🖥️  CPU",
        Text(f"{cpu:.1f}%", style=color_for(cpu, CPU_WARN, CPU_CRIT)),
        progress_bar(cpu, warn=CPU_WARN, crit=CPU_CRIT),
        sparkline(snapshot.cpu_series, fixed_scale=100.0),
        trend_arrow(snapshot.cpu_series),
    )

    mem = snapshot.memory_percent
    table.add_row(
        "💾 RAM",
        Text(f"{mem:.1f}%", style=color_for(mem, MEM_WARN, MEM_CRIT)),
        progress_bar(mem, warn=MEM_WARN, crit=MEM_CRIT),
        sparkline(snapshot.memory_series, fixed_scale=100.0),
        trend_arrow(snapshot.memory_series),
    )

    net_rx = snapshot.net_rx_series
    rx_last = net_rx[-1].value if net_rx else 0.0
    table.add_row(
        "📥 NET ↓",
        Text(format_bytes(rx_last), style="cyan"),
        Text(format_bytes(rx_last), style="dim"),
        sparkline(net_rx),
        trend_arrow(net_rx),
    )

    net_tx = snapshot.net_tx_series
    tx_last = net_tx[-1].value if net_tx else 0.0
    table.add_row(
        "📤 NET ↑",
        Text(format_bytes(tx_last), style="cyan"),
        Text(format_bytes(tx_last), style="dim"),
        sparkline(net_tx),
        trend_arrow(net_tx),
    )

    return table


def _build_alerts_panel(snapshot: MonitorSnapshot) -> Panel:
    """Alerts panel: triggered alerts + collected issues."""
    lines: list[Text] = []

    for alert in snapshot.alerts:
        style = "bold red" if alert.severity == "critical" else "yellow"
        icon = "🚨" if alert.severity == "critical" else "⚠️"
        lines.append(Text(f"{icon} [{alert.severity}] {alert.message}", style=style))

    for issue in snapshot.issues:
        lines.append(Text(f"❗ {issue}", style="yellow"))

    has_critical = any(a.severity == "critical" for a in snapshot.alerts)
    has_warn = bool(snapshot.alerts) or bool(snapshot.issues)

    if not lines:
        lines.append(Text("✅ همه شاخص‌ها در محدوده نرمال هستند", style="green"))

    return Panel(
        Group(*lines),
        title=f"🔔 هشدارها ({len(snapshot.alerts) + len(snapshot.issues)})",
        border_style="bold red" if has_critical else ("yellow" if has_warn else "green"),
        padding=(1, 1),
    )


def _build_recommendations_panel(snapshot: MonitorSnapshot) -> Panel:
    """Recommendations panel with actionable hints."""
    if snapshot.recommendations:
        content: Text | Group = Group(
            *(Text(f"💡 {r}", style="cyan") for r in snapshot.recommendations)
        )
        title = f"💡 پیشنهادات ({len(snapshot.recommendations)})"
        border = "cyan"
    elif snapshot.is_healthy:
        content = Text("نیازی به اقدام فوری نیست.", style="dim")
        title, border = "💡 پیشنهادات", "green"
    else:
        content = Text("داده کافی برای پیشنهاد موجود نیست.", style="dim")
        title, border = "💡 پیشنهادات", "dim"

    return Panel(content, title=title, border_style=border, padding=(1, 1))


def _build_footer(snapshot: MonitorSnapshot) -> Text:
    """Footer hint line."""
    footer = Text()
    footer.append("آخرین بروزرسانی: ", style="dim")
    footer.append(snapshot.fetched_at or "—", style="dim")
    footer.append("  •  ", style="dim")
    footer.append("برای خروج Ctrl+C", style="dim italic")
    return footer


# ══════════════════════════════════════════════════════════════
#  Public render API
# ══════════════════════════════════════════════════════════════

def show_dashboard(snapshot: MonitorSnapshot, console: Console | None = None) -> None:
    """Print a static snapshot of the dashboard."""
    out = console or Console()
    out.print()
    out.print(build_dashboard(snapshot))


def show_live_dashboard(
    project_name: str,
    fetch_snapshot_fn: Callable[[], MonitorSnapshot],
    refresh_interval: int = 10,
    console: Console | None = None,
) -> None:
    """Auto-refreshing live dashboard.

    Args:
        project_name: Display name of the project.
        fetch_snapshot_fn: Synchronous callable returning a fresh
            :class:`MonitorSnapshot`. Failures are rendered as an error
            panel and the loop keeps running.
        refresh_interval: Seconds between refreshes.
        console: Optional console (useful for tests/capture).
    """
    out = console or Console()
    out.print()
    out.print(
        f"[bold cyan]📊 پایش زنده [bold yellow]{project_name}[/] "
        f"• بروزرسانی هر {refresh_interval} ثانیه • برای خروج Ctrl+C[/]\n"
    )

    def _error_panel(exc: Exception) -> Panel:
        return Panel(
            Text(f"خطا در دریافت متریک‌ها: {exc}", style="bold red"),
            title="⚠️ ارتباط با لیارا",
            border_style="red",
        )

    try:
        with Live(console=out, refresh_per_second=1) as live:
            while True:
                try:
                    snapshot = fetch_snapshot_fn()
                    live.update(build_dashboard(snapshot))
                except Exception as exc:  # noqa: BLE001 — never kill the live loop
                    live.update(_error_panel(exc))
                time.sleep(refresh_interval)
    except KeyboardInterrupt:
        out.print("\n[yellow]داشبورد زنده متوقف شد. موفق باشید! 👋[/yellow]")
