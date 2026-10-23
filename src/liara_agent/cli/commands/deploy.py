"""Deploy command — publish new release of an application to Liara PaaS."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.markup import escape
from rich.panel import Panel

from liara_agent.api.client import LiaraClient
from liara_agent.cli.commands.common import cancelled, require_token
from liara_agent.cli.components.approval import request_approval
from liara_agent.cli.components.progress import deploy_progress
from liara_agent.cli.theme import BOX, console, print_next_steps
from liara_agent.core.analyzer import ProjectAnalyzer
from liara_agent.core.deployer import Deployer
from liara_agent.storage.audit import audit
from liara_agent.utils.constants import RiskLevel
from liara_agent.utils.errors import LiaraAgentError

deploy_app = typer.Typer(
    name="deploy",
    help="🚀 دیپلوی و انتشار نسخه جدید پروژه روی لیارا",
    no_args_is_help=False,
)


@deploy_app.callback(invoke_without_command=True)
def run_deploy(
    path: Path | None = typer.Argument(None, help="مسیر سورس‌کد (پیش‌فرض: پوشه جاری)"),
    project: str | None = typer.Option(None, "--project", "-p", help="نام اپلیکیشن در لیارا"),
    port: int | None = typer.Option(None, "--port", help="پورت وب‌سرور"),
) -> None:
    """بسته‌بندی و ارسال نسخه جدید پروژه به سرورهای لیارا."""
    source_path = path or Path.cwd()
    if not source_path.is_dir():
        console.print(f"[red]❌ مسیر '{escape(str(source_path))}' وجود ندارد.[/red]")
        raise typer.Exit(1)

    token = require_token()

    app_name = project
    if not app_name:
        from liara_agent.utils.config import get_settings

        settings = get_settings()
        app_name = settings.liara_default_project
    if not app_name:
        app_name = source_path.name.lower().replace("_", "-").replace(" ", "-")

    # Analyze briefly for platform/port if not supplied
    analyzer = ProjectAnalyzer(source_path)
    analysis = analyzer.analyze()
    effective_port = port or analysis.port

    # Approval check (unified security gateway)
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
        audit(action="deploy", target=app_name, risk_level="medium", status="denied")
        cancelled("عملیات دیپلوی لغو شد.")
        raise typer.Exit(0)

    async def _deploy() -> None:
        async with LiaraClient(token=token) as client:
            deployer = Deployer(client)

            with deploy_progress() as progress:
                task = progress.add_task("🚀 آغاز فرآیند دیپلوی…", total=1.0)

                def _on_progress(msg: str, p: float) -> None:
                    progress.update(task, description=f"[bold blue]{escape(msg)}", completed=p)

                result = await deployer.deploy(
                    project_name=app_name,
                    source_path=source_path,
                    port=effective_port,
                    platform_type=analysis.platform,
                    progress_cb=_on_progress,
                )

            audit(
                action="deploy",
                target=app_name,
                risk_level="medium",
                status="success",
                details={"release_id": result.release_id, "build_time": result.build_time_seconds},
            )
            console.print(Panel(
                f"[bold green]✅ دیپلوی با موفقیت انجام شد![/bold green]\n\n"
                f"🔗 آدرس اپلیکیشن: [bold underline cyan]{result.url}[/bold underline cyan]\n"
                f"⏱️ زمان ساخت و راه‌اندازی: {result.build_time_seconds} ثانیه\n"
                f"🆔 شناسه ریلیز: [dim]{escape(result.release_id)}[/dim]",
                title="🚀 انتشار موفقیت‌آمیز (Release Published)",
                border_style="green",
                box=BOX,
            ))
            print_next_steps([
                (f"liara-agent monitor {app_name} --live", "پایش زنده مصرف منابع"),
                (f"liara-agent logs {app_name} -f", "استریم زنده لاگ‌ها"),
            ])

    try:
        import asyncio

        asyncio.run(_deploy())
    except LiaraAgentError as exc:
        audit(action="deploy", target=app_name, risk_level="medium", status="error", details={"error": str(exc)[:200]})
        from liara_agent.cli.theme import render_error

        render_error(exc)
        raise typer.Exit(1) from exc
