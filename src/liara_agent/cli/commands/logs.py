"""Logs command — fetch, search, filter, and stream application logs."""

from __future__ import annotations

import asyncio
import time

import typer
from rich.markup import escape

from liara_agent.api.client import LiaraClient
from liara_agent.api.websocket import LiaraWebSocket
from liara_agent.cli.commands.common import require_token
from liara_agent.cli.components.log_viewer import render_log_line, render_logs
from liara_agent.cli.theme import console, render_error
from liara_agent.utils.errors import LiaraAgentError

logs_app = typer.Typer(
    name="logs",
    help="📜 دریافت، جستجو و استریم زنده لاگ‌های اپلیکیشن",
    no_args_is_help=False,
)


def _entry_dict(item: object) -> dict:
    return {
        "message": getattr(item, "message", str(item)),
        "timestamp": getattr(item, "timestamp", ""),
        "level": getattr(item, "level", "info"),
    }


@logs_app.callback(invoke_without_command=True)
def run_logs(
    project: str = typer.Argument(..., help="نام اپلیکیشن"),
    follow: bool = typer.Option(False, "--follow", "-f", help="استریم مداوم لاگ‌ها به صورت زنده"),
    since: int = typer.Option(30, "--since", "-s", help="تعداد دقایق گذشته برای بازیابی لاگ‌ها"),
    grep: str | None = typer.Option(None, "--grep", "-g", help="فیلتر خطوط لاگ بر اساس عبارت خاص"),
    level: str | None = typer.Option(None, "--level", "-l", help="حداقل سطح لاگ: debug/info/warn/error/fatal"),
) -> None:
    """مشاهده لاگ‌های خروجی استاندارد (stdout/stderr) برنامه."""
    token = require_token()

    since_ts = int(time.time()) - (since * 60)

    async def _fetch_historical() -> None:
        async with LiaraClient(token=token) as client:
            resp = await client.get_logs(project, since=since_ts)
            logs_list = getattr(resp, "logs", resp)

            if not logs_list:
                console.print(
                    f"[dim]هیچ لاگی در {since} دقیقه گذشته برای پروژه '{escape(project)}' ثبت نشده است.[/dim]"
                )
                return

            entries = [_entry_dict(item) for item in logs_list]
            render_logs(entries, grep=grep, project_name=project, min_level=level)

    if not follow:
        try:
            asyncio.run(_fetch_historical())
        except LiaraAgentError as exc:
            render_error(exc)
            raise typer.Exit(1) from exc
        return

    # Live streaming via WebSocket / continuous polling
    async def _stream() -> None:
        await _fetch_historical()
        console.print("\n[dim]⚡ در حال برقراری اتصال زنده... (برای خروج Ctrl+C بزنید)[/dim]\n")

        # Follow-mode header bar: project + active filters.
        filters = " | ".join(filter(None, [
            f"grep: {grep}" if grep else "",
            f"level ≥ {level}" if level else "",
        ]))
        header = (
            f"[bold cyan]📡 استریم زنده[/bold cyan] [yellow]{escape(project)}[/yellow]"
            + (f"  [dim]({escape(filters)})[/dim]" if filters else "")
        )
        console.print(header)
        console.print("[dim]" + "─" * 40 + "[/dim]")

        try:
            ws = LiaraWebSocket(token=token, project_id=project)
            async for raw_msg in ws.connect_and_stream():
                if grep and grep.lower() not in raw_msg.lower():
                    continue
                render_log_line(console, raw_msg, level="info", grep=grep)
        except Exception as e:
            console.print(f"[yellow]استریم وب‌سوکت قطع شد ({escape(str(e))})، سوئیچ به پولینگ دوره‌ای...[/yellow]")
            last_ts = int(time.time())
            while True:
                await asyncio.sleep(5)
                async with LiaraClient(token=token) as client:
                    resp = await client.get_logs(project, since=last_ts)
                    logs_list = getattr(resp, "logs", resp)
                    last_ts = int(time.time())
                    for item in logs_list:
                        d = _entry_dict(item)
                        if grep and grep.lower() not in d["message"].lower():
                            continue
                        if level:
                            from liara_agent.cli.components.log_viewer import LEVEL_ORDER

                            if LEVEL_ORDER.get(d["level"].lower(), 20) < LEVEL_ORDER.get(level.lower(), 20):
                                continue
                        render_log_line(console, d["message"], timestamp=d["timestamp"], level=d["level"], grep=grep)

    try:
        asyncio.run(_stream())
    except KeyboardInterrupt:
        console.print("\n[yellow]استریم لاگ‌ها متوقف شد.[/yellow]")
    except LiaraAgentError as exc:
        render_error(exc)
        raise typer.Exit(1) from exc
