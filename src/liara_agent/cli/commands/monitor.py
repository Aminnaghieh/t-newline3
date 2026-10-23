"""Monitor command — live metrics, health dashboard, and proactive alerts."""

from __future__ import annotations

import asyncio

import typer

from liara_agent.api.client import LiaraClient
from liara_agent.cli.commands.common import require_token
from liara_agent.cli.components.dashboard import show_dashboard, show_live_dashboard
from liara_agent.cli.theme import console, render_error
from liara_agent.core.monitor import Monitor
from liara_agent.utils.errors import LiaraAgentError

monitor_app = typer.Typer(
    name="monitor",
    help="📊 پایش زنده متریک‌های سرویس (CPU/RAM/Network) و وضعیت سلامت",
    no_args_is_help=False,
)


@monitor_app.callback(invoke_without_command=True)
def run_monitor(
    project: str = typer.Argument(..., help="نام اپلیکیشن در لیارا"),
    live: bool = typer.Option(False, "--live", "-l", help="بروزرسانی مداوم و زنده"),
    interval: int = typer.Option(10, "--interval", "-i", min=2, help="فاصله بروزرسانی زنده (ثانیه، حداقل ۲)"),
    json_output: bool = typer.Option(False, "--json", help="خروجی JSON اسنپ‌شات برای اسکریپت‌نویسی"),
) -> None:
    """بررسی شاخص‌های حیاتی اپلیکیشن و مانیتورینگ زنده."""
    token = require_token()

    state = {"offline": False}

    async def _fetch_snapshot():
        async with LiaraClient(token=token) as client:
            monitor_engine = Monitor(client)
            snapshot = await monitor_engine.get_snapshot(project)
            state["offline"] = client.is_offline
            return snapshot

    def _fetch() -> object:
        return asyncio.run(_fetch_snapshot())

    if json_output and not live:
        import json

        try:
            snapshot = asyncio.run(_fetch_snapshot())
        except LiaraAgentError as exc:
            render_error(exc)
            raise typer.Exit(1) from exc
        console.print_json(json.dumps(snapshot.model_dump(), ensure_ascii=False, default=str))
        return

    if not live:
        try:
            snapshot = asyncio.run(_fetch_snapshot())
        except LiaraAgentError as exc:
            render_error(exc)
            raise typer.Exit(1) from exc
        show_dashboard(snapshot, console=console)
        return

    # Live mode — fetch failures are rendered inline by the dashboard loop.
    try:
        asyncio.run(_fetch_snapshot())
    except LiaraAgentError as exc:
        render_error(exc)
        raise typer.Exit(1) from exc

    show_live_dashboard(
        project,
        _fetch,
        refresh_interval=interval,
        console=console,
        offline_fn=lambda: state["offline"],
    )
