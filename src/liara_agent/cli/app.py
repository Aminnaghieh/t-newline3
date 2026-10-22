"""Main CLI entrypoint for Liara SRE Agent."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from liara_agent import __version__
from liara_agent.cli.commands.config import config_app
from liara_agent.cli.commands.debug_cmd import debug_app
from liara_agent.cli.commands.deploy import deploy_app
from liara_agent.cli.commands.init import init_app
from liara_agent.cli.commands.logs import logs_app
from liara_agent.cli.commands.mcp_cmd import mcp_app
from liara_agent.cli.commands.monitor import monitor_app
from liara_agent.cli.commands.service import service_app

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(legacy_windows=False)

app = typer.Typer(
    name="liara-agent",
    help="🛡️ Liara SRE Agent — ایجنت هوشمند DevOps و مهندسی قابلیت اطمینان برای پلتفرم لیارا",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Register Subcommands
app.add_typer(init_app, name="init")
app.add_typer(deploy_app, name="deploy")
app.add_typer(monitor_app, name="monitor")
app.add_typer(debug_app, name="debug")
app.add_typer(service_app, name="service")
app.add_typer(logs_app, name="logs")
app.add_typer(mcp_app, name="mcp")
app.add_typer(config_app, name="config")


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="نمایش نسخه برنامه"),
) -> None:
    """Liara SRE Agent — دستیار هوشمند استقرار، مانیتورینگ و عیب‌یابی خودکار."""
    if version:
        console.print(f"[bold cyan]Liara SRE Agent[/bold cyan] version [bold green]{__version__}[/bold green]")
        raise typer.Exit(0)

    if ctx.invoked_subcommand is None:
        banner = Text()
        banner.append("🛡️  Liara SRE Agent ", style="bold cyan")
        banner.append(f"v{__version__}\n", style="bold green")
        banner.append("دستیار هوشمند مهندسی پایداری و استقرار بر روی Liara PaaS\n", style="white")
        banner.append("دستورات اصلی: init | deploy | monitor | debug | service | logs | mcp | config", style="dim")

        console.print(Panel(banner, border_style="cyan", padding=(1, 2)))
