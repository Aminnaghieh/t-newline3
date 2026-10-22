"""Logs command — fetch, search, filter, and stream application logs."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import typer
from rich.console import Console

from liara_agent.api.client import LiaraClient
from liara_agent.api.websocket import LiaraWebSocket
from liara_agent.cli.components.log_viewer import render_log_line
from liara_agent.storage.credentials import default_credential_store
from liara_agent.utils.config import get_settings

logs_app = typer.Typer(
    name="logs",
    help="📜 دریافت، جستجو و استریم زنده لاگ‌های اپلیکیشن",
    no_args_is_help=False,
)
console = Console()


@logs_app.callback(invoke_without_command=True)
def run_logs(
    project: str = typer.Argument(..., help="نام اپلیکیشن"),
    follow: bool = typer.Option(False, "--follow", "-f", help="استریم مداوم لاگ‌ها به صورت زنده"),
    since: int = typer.Option(30, "--since", "-s", help="تعداد دقایق گذشته برای بازیابی لاگ‌ها"),
    grep: Optional[str] = typer.Option(None, "--grep", "-g", help="فیلتر خطوط لاگ بر اساس عبارت خاص"),
) -> None:
    """مشاهده لاگ‌های خروجی استاندارد (stdout/stderr) برنامه."""
    settings = get_settings()
    token = default_credential_store.get_token("LIARA_API_TOKEN") or settings.liara_api_token
    if not token or token.endswith("xxxx"):
        console.print("[yellow]⚠️ ابتدا توکن API لیارا را تنظیم کنید:[/yellow]")
        console.print("  [cyan]liara-agent config set-token[/cyan]\n")
        raise typer.Exit(1)

    since_ts = int(time.time()) - (since * 60)

    async def _fetch_historical() -> None:
        async with LiaraClient(token=token) as client:
            resp = await client.get_logs(project, since=since_ts)
            logs_list = getattr(resp, "logs", resp)

            if not logs_list:
                console.print(f"[dim]هیچ لاگی در {since} دقیقه گذشته برای پروژه '{project}' ثبت نشده است.[/dim]")
                return

            console.print(f"[bold cyan]📜 لاگ‌های پروژه '{project}' (از {since} دقیقه پیش):[/bold cyan]\n")
            for item in logs_list:
                msg = getattr(item, "message", str(item))
                ts = getattr(item, "timestamp", "")
                lvl = getattr(item, "level", "info")
                if grep and grep.lower() not in msg.lower():
                    continue
                render_log_line(console, msg, timestamp=ts, level=lvl)

    if not follow:
        asyncio.run(_fetch_historical())
        return

    # Live streaming via WebSocket / continuous polling
    async def _stream() -> None:
        await _fetch_historical()
        console.print("\n[dim]⚡ در حال برقراری اتصال زنده... (برای خروج Ctrl+C بزنید)[/dim]\n")
        try:
            ws = LiaraWebSocket(token=token, project_id=project)
            async for raw_msg in ws.connect_and_stream():
                if grep and grep.lower() not in raw_msg.lower():
                    continue
                render_log_line(console, raw_msg)
        except Exception as e:
            console.print(f"[yellow]استریم وب‌سوکت قطع شد ({e})، سوئیچ به پولینگ دوره‌ای...[/yellow]")
            last_ts = int(time.time())
            while True:
                await asyncio.sleep(5)
                async with LiaraClient(token=token) as client:
                    resp = await client.get_logs(project, since=last_ts)
                    logs_list = getattr(resp, "logs", resp)
                    last_ts = int(time.time())
                    for item in logs_list:
                        msg = getattr(item, "message", str(item))
                        if grep and grep.lower() not in msg.lower():
                            continue
                        render_log_line(console, msg)

    try:
        asyncio.run(_stream())
    except KeyboardInterrupt:
        console.print("\n[yellow]استریم لاگ‌ها متوقف شد.[/yellow]")
