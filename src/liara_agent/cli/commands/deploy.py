"""Deploy command — publish new release of an application to Liara PaaS."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from liara_agent.api.client import LiaraClient
from liara_agent.cli.components.approval import request_approval
from liara_agent.cli.components.progress import operation_spinner
from liara_agent.core.analyzer import ProjectAnalyzer
from liara_agent.core.deployer import Deployer
from liara_agent.storage.credentials import default_credential_store
from liara_agent.utils.config import get_settings
from liara_agent.utils.constants import RiskLevel

deploy_app = typer.Typer(
    name="deploy",
    help="🚀 دیپلوی و انتشار نسخه جدید پروژه روی لیارا",
    no_args_is_help=False,
)
console = Console()


@deploy_app.callback(invoke_without_command=True)
def run_deploy(
    path: Optional[Path] = typer.Argument(None, help="مسیر سورس‌کد (پیش‌فرض: پوشه جاری)"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="نام اپلیکیشن در لیارا"),
    port: Optional[int] = typer.Option(None, "--port", help="پورت وب‌سرور"),
) -> None:
    """بسته‌بندی و ارسال نسخه جدید پروژه به سرورهای لیارا."""
    source_path = path or Path.cwd()
    if not source_path.is_dir():
        console.print(f"[red]❌ مسیر '{source_path}' وجود ندارد.[/red]")
        raise typer.Exit(1)

    settings = get_settings()
    token = default_credential_store.get_token("LIARA_API_TOKEN") or settings.liara_api_token
    if not token or token.endswith("xxxx"):
        console.print("[yellow]⚠️ ابتدا توکن API لیارا را تنظیم کنید:[/yellow]")
        console.print("  [cyan]liara-agent config set-token[/cyan]\n")
        raise typer.Exit(1)

    app_name = project or settings.liara_default_project
    if not app_name:
        app_name = source_path.name.lower().replace("_", "-").replace(" ", "-")

    # Analyze briefly for platform/port if not supplied
    analyzer = ProjectAnalyzer(source_path)
    analysis = analyzer.analyze()
    effective_port = port or analysis.port

    # Approval check
    approved = request_approval(
        operation=f"دیپلوی نسخه جدید اپلیکیشن '{app_name}'",
        details={
            "پروژه": app_name,
            "مسیر": str(source_path.resolve()),
            "پلتفرم": analysis.platform,
            "پورت": str(effective_port),
        },
        risk_level=RiskLevel.MEDIUM,
    )

    if not approved:
        console.print("[yellow]عملیات دیپلوی لغو شد.[/yellow]")
        raise typer.Exit(0)

    async def _deploy() -> None:
        async with LiaraClient(token=token) as client:
            deployer = Deployer(client)
            console.print(f"\n[bold cyan]📦 آغاز فرآیند دیپلوی برای پروژه '{app_name}'...[/bold cyan]")

            result = await deployer.deploy(
                project_name=app_name,
                source_path=source_path,
                port=effective_port,
                platform_type=analysis.platform,
                progress_cb=lambda msg, p: console.print(f"  [cyan]•[/cyan] {msg}"),
            )

            console.print(Panel(
                f"[bold green]✅ دیپلوی با موفقیت انجام شد![/bold green]\n\n"
                f"🔗 آدرس اپلیکیشن: [bold underline cyan]{result.url}[/bold underline cyan]\n"
                f"⏱️ زمان ساخت و راه‌اندازی: {result.build_time_seconds} ثانیه\n"
                f"🆔 شناسه ریلیز: [dim]{result.release_id}[/dim]",
                title="🚀 انتشار موفقیت‌آمیز (Release Published)",
                border_style="green",
            ))

    asyncio.run(_deploy())
