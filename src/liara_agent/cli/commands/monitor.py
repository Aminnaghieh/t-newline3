"""Monitor command — live metrics, health dashboard, and proactive alerts."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from liara_agent.api.client import LiaraClient
from liara_agent.cli.components.dashboard import show_dashboard, show_live_dashboard
from liara_agent.core.monitor import Monitor
from liara_agent.storage.credentials import default_credential_store
from liara_agent.utils.config import get_settings
from liara_agent.utils.errors import LiaraAgentError

monitor_app = typer.Typer(
    name="monitor",
    help="📊 پایش زنده متریک‌های سرویس (CPU/RAM/Network) و وضعیت سلامت",
    no_args_is_help=False,
)
console = Console()

REFRESH_INTERVAL = 10


def _resolve_token() -> str:
    settings = get_settings()
    token = default_credential_store.get_token("LIARA_API_TOKEN") or settings.liara_api_token
    if not token or token.endswith("xxxx"):
        console.print("[yellow]⚠️ ابتدا توکن API لیارا را تنظیم کنید:[/yellow]")
        console.print("  [cyan]liara-agent config set-token[/cyan]\n")
        raise typer.Exit(1)
    return token


@monitor_app.callback(invoke_without_command=True)
def run_monitor(
    project: str = typer.Argument(..., help="نام اپلیکیشن در لیارا"),
    live: bool = typer.Option(False, "--live", "-l", help="بروزرسانی مداوم هر ۱۰ ثانیه"),
) -> None:
    """بررسی شاخص‌های حیاتی اپلیکیشن و مانیتورینگ زنده."""
    token = _resolve_token()

    async def _fetch_snapshot():
        async with LiaraClient(token=token) as client:
            monitor_engine = Monitor(client)
            return await monitor_engine.get_snapshot(project)

    def _fetch() -> object:
        return asyncio.run(_fetch_snapshot())

    if not live:
        try:
            snapshot = asyncio.run(_fetch_snapshot())
        except LiaraAgentError as exc:
            console.print(f"[bold red]✗ {exc}[/bold red]")
            if exc.hint:
                console.print(f"  [dim]💡 {exc.hint}[/dim]")
            raise typer.Exit(1) from exc
        show_dashboard(snapshot, console=console)
        return

    # Live mode — fetch failures are rendered inline by the dashboard loop.
    try:
        asyncio.run(_fetch_snapshot())
    except LiaraAgentError as exc:
        console.print(f"[bold red]✗ {exc}[/bold red]")
        if exc.hint:
            console.print(f"  [dim]💡 {exc.hint}[/dim]")
        raise typer.Exit(1) from exc

    show_live_dashboard(project, _fetch, refresh_interval=REFRESH_INTERVAL, console=console)
