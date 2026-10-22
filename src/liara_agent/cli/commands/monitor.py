"""Monitor command — live metrics, health dashboard, and proactive alerts."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from liara_agent.api.client import LiaraClient
from liara_agent.core.monitor import Monitor
from liara_agent.storage.credentials import default_credential_store
from liara_agent.utils.config import get_settings

monitor_app = typer.Typer(
    name="monitor",
    help="📊 پایش زنده متریک‌های سرویس (CPU/RAM/Network) و وضعیت سلامت",
    no_args_is_help=False,
)
console = Console()


def _render_dashboard_table(project_name: str, health: Any, reports: dict) -> Panel:
    """Build a rich visual dashboard table."""
    status_color = "green" if health.is_healthy else "red"
    status_icon = "🟢" if health.is_healthy else "🔴"

    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("متریک", style="bold")
    table.add_column("مقدار کنونی", justify="center")
    table.add_column("وضعیت / ارزیابی")

    # CPU
    cpu_style = "green" if health.cpu_percent < 70 else ("yellow" if health.cpu_percent < 85 else "bold red")
    table.add_row(
        "پردازنده (CPU)",
        f"[{cpu_style}]{health.cpu_percent:.1f}%[/{cpu_style}]",
        "طبیعی" if health.cpu_percent < 70 else "بالا",
    )

    # Memory
    mem_style = "green" if health.memory_percent < 75 else ("yellow" if health.memory_percent < 90 else "bold red")
    table.add_row(
        "حافظه رم (RAM)",
        f"[{mem_style}]{health.memory_percent:.1f}%[/{mem_style}]",
        "طبیعی" if health.memory_percent < 75 else "هشدار کمبود حافظه",
    )

    # Status
    table.add_row("وضعیت سرویس", f"[{status_color}]{health.status}[/{status_color}]", "فعال و پاسخگو" if health.is_healthy else "دارای اختلال")
    table.add_row("استقرار یافته (Deployed)", "بله" if health.is_deployed else "خیر", "—")

    # Issues
    issues_text = "\n".join(f"[yellow]⚠️ {iss}[/yellow]" for iss in health.issues) if health.issues else "[green]هیچ هشداری ثبت نشده است.[/green]"
    recs_text = "\n".join(f"[cyan]💡 {r}[/cyan]" for r in health.recommendations) if health.recommendations else "[dim]نیازی به اقدام فوری نیست.[/dim]"

    content = f"[bold]وضعیت اپلیکیشن: {status_icon} [{status_color}]{health.status.upper()}[/{status_color}][/bold]\n\n"
    content += f"[bold]هشدارهای فعال:[/bold]\n{issues_text}\n\n"
    content += f"[bold]پیشنهادات هوشمند:[/bold]\n{recs_text}"

    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_row(table)
    grid.add_row(Panel(content, border_style=status_color))

    return Panel(
        grid,
        title=f"📊 مانیتورینگ زنده پروژه: [bold yellow]{project_name}[/bold yellow]",
        border_style="cyan",
        subtitle=f"بروزرسانی: {time.strftime('%H:%M:%S')}",
    )


@monitor_app.callback(invoke_without_command=True)
def run_monitor(
    project: str = typer.Argument(..., help="نام اپلیکیشن در لیارا"),
    live: bool = typer.Option(False, "--live", "-l", help="بروزرسانی مداوم هر ۱۰ ثانیه"),
) -> None:
    """بررسی شاخص‌های حیاتی اپلیکیشن و مانیتورینگ زنده."""
    settings = get_settings()
    token = default_credential_store.get_token("LIARA_API_TOKEN") or settings.liara_api_token
    if not token or token.endswith("xxxx"):
        console.print("[yellow]⚠️ ابتدا توکن API لیارا را تنظیم کنید:[/yellow]")
        console.print("  [cyan]liara-agent config set-token[/cyan]\n")
        raise typer.Exit(1)

    async def _fetch_and_render() -> Panel:
        async with LiaraClient(token=token) as client:
            monitor_engine = Monitor(client)
            health = await monitor_engine.get_health_status(project)
            reports = await monitor_engine.get_metrics_summary(project)
            return _render_dashboard_table(project, health, reports)

    if not live:
        panel = asyncio.run(_fetch_and_render())
        console.print(panel)
        return

    # Continuous live dashboard
    console.print("[dim]برای خروج از حالت زنده، Ctrl+C را فشار دهید...[/dim]\n")
    try:
        with Live(console=console, screen=False, refresh_per_second=1) as live_display:
            while True:
                panel = asyncio.run(_fetch_and_render())
                live_display.update(panel)
                time.sleep(10)
    except KeyboardInterrupt:
        console.print("\n[yellow]مانیتورینگ زنده متوقف شد.[/yellow]")
