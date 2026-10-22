"""Init command — project analysis, optimal plan wizard, and initial deployment."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from liara_agent.api.client import LiaraClient
from liara_agent.cli.components.approval import request_approval
from liara_agent.cli.components.progress import operation_spinner
from liara_agent.core.analyzer import ProjectAnalyzer
from liara_agent.core.deployer import Deployer
from liara_agent.core.planner import PlanRecommender
from liara_agent.models.plans import get_plan_by_id
from liara_agent.models.project import ProjectCreate
from liara_agent.storage.credentials import default_credential_store
from liara_agent.utils.config import get_settings
from liara_agent.utils.constants import RiskLevel

init_app = typer.Typer(
    name="init",
    help="🚀 راه‌اندازی گام‌به‌گام پروژه و اولین دیپلوی با هوش مصنوعی",
    no_args_is_help=False,
)
console = Console()


@init_app.callback(invoke_without_command=True)
def run_init(
    path: Optional[Path] = typer.Argument(
        None,
        help="مسیر پوشه پروژه (پیش‌فرض: پوشه جاری)",
    ),
) -> None:
    """تحلیل هوشمند سورس‌کد، پیشنهاد بهترین پلن و استقرار خودکار."""
    project_path = path or Path.cwd()
    if not project_path.is_dir():
        console.print(f"[red]❌ مسیر '{project_path}' وجود ندارد یا پوشه نیست.[/red]")
        raise typer.Exit(1)

    settings = get_settings()
    token = default_credential_store.get_token("LIARA_API_TOKEN") or settings.liara_api_token
    if not token or token.endswith("xxxx"):
        console.print("[yellow]⚠️ ابتدا توکن API لیارا را تنظیم کنید:[/yellow]")
        console.print("  [cyan]liara-agent config set-token[/cyan]\n")
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold cyan]🔍 تحلیل هوشمند و آماده‌سازی پروژه[/bold cyan]\n"
        f"مسیر: [yellow]{project_path.resolve()}[/yellow]",
        border_style="cyan",
    ))

    # 1. Analyze Project
    with operation_spinner("در حال کاوش فایل‌ها و تحلیل ساختار پروژه..."):
        analyzer = ProjectAnalyzer(project_path)
        analysis = analyzer.analyze()

    # 2. Display Analysis Results
    info_table = Table(title="📊 نتایج تحلیل سورس‌کد", show_header=True, header_style="bold magenta")
    info_table.add_column("مشخصه", style="bold")
    info_table.add_column("مقدار شناسایی شده")

    info_table.add_row("زبان / پلتفرم", f"[green]{analysis.platform}[/green]")
    info_table.add_row("فریم‌ورک", analysis.framework or "[dim]عمومی[/dim]")
    info_table.add_row("پورت پیش‌فرض", str(analysis.port))
    info_table.add_row("دستور اجرا (Start)", analysis.start_cmd)
    if analysis.build_cmd:
        info_table.add_row("دستور بیلد", analysis.build_cmd)
    info_table.add_row("تعداد پکیج‌ها", str(len(analysis.dependencies)))
    info_table.add_row("حجم تخمینی سورس", f"{analysis.project_size_mb:.2f} MB")

    console.print(info_table)

    # 3. Plan Recommendation
    planner = PlanRecommender()
    recommendation = planner.recommend(analysis)
    plan_info = get_plan_by_id(recommendation.recommended_plan)

    plan_panel = Panel(
        f"[bold green]پلن پیشنهادی: {plan_info.label} ({plan_info.id})[/bold green]\n"
        f"مشخصات: [cyan]{plan_info.cpu} هسته CPU | {plan_info.ram_gb} گیگابایت RAM | {plan_info.disk_gb} گیگابایت دیسک[/cyan]\n"
        f"[dim]دلیل انتخاب: {recommendation.reason}[/dim]",
        title="💡 پیشنهاد هوشمند پلن زیرساخت",
        border_style="green",
    )
    console.print(plan_panel)

    # 4. Interactive Configuration Wizard
    default_name = project_path.name.lower().replace("_", "-").replace(" ", "-")
    app_name = Prompt.ask("\n[bold]نام اپلیکیشن در لیارا[/bold]", default=default_name)
    selected_plan = Prompt.ask("[bold]پلن انتخابی[/bold]", default=recommendation.recommended_plan)
    selected_port = int(Prompt.ask("[bold]پورت اپلیکیشن[/bold]", default=str(analysis.port)))

    # Env vars
    env_vars: list[dict[str, str]] = []
    if analysis.env_vars_needed:
        console.print(f"\n[cyan]متغیرهای محیطی احتمالی شناسایی شده: {', '.join(analysis.env_vars_needed)}[/cyan]")
        if Confirm.ask("آیا مایل به مقداردهی متغیرهای محیطی هستید؟", default=False):
            for env_name in analysis.env_vars_needed:
                val = Prompt.ask(f"مقدار برای {env_name}", default="")
                if val:
                    env_vars.append({"key": env_name, "value": val})

    # 5. Human-in-the-Loop Approval Before Project Creation & Deploy
    deploy_summary = {
        "نام اپلیکیشن": app_name,
        "پلتفرم": analysis.platform,
        "پلن زیرساخت": selected_plan,
        "پورت شبکه": str(selected_port),
        "متغیرهای محیطی": f"{len(env_vars)} متغیر",
    }

    approved = request_approval(
        operation="ایجاد پروژه و اولین استقرار (Deploy) روی ابر لیارا",
        details=deploy_summary,
        risk_level=RiskLevel.HIGH,
    )

    if not approved:
        console.print("[yellow]عملیات توسط کاربر لغو گردید.[/yellow]")
        raise typer.Exit(0)

    # 6. Execute Creation & Deployment
    async def _execute() -> None:
        async with LiaraClient(token=token) as client:
            # Check if project exists, else create
            try:
                console.print(f"[blue]🔨 در حال ساخت پروژه '{app_name}' در لیارا...[/blue]")
                create_req = ProjectCreate(
                    name=app_name,
                    planID=selected_plan,
                    platform=analysis.platform,
                )
                await client.create_project(create_req)
                console.print(f"[green]✅ پروژه '{app_name}' با موفقیت ساخته شد.[/green]")
            except Exception as e:
                if "409" in str(e) or "already exists" in str(e).lower():
                    console.print(f"[dim]ℹ️ پروژه '{app_name}' از قبل وجود دارد، ادامه با همین پروژه...[/dim]")
                else:
                    console.print(f"[red]❌ خطا در ایجاد پروژه: {e}[/red]")
                    raise

            # Update Envs if any
            if env_vars:
                console.print("[blue]📝 در حال ثبت متغیرهای محیطی...[/blue]")
                await client.update_envs(app_name, env_vars)

            # Deploy source
            console.print("\n[bold cyan]🚀 شروع استقرار کدهای پروژه...[/bold cyan]")
            deployer = Deployer(client)
            result = await deployer.deploy(
                project_name=app_name,
                source_path=project_path,
                port=selected_port,
                platform_type=analysis.platform,
                progress_cb=lambda msg, p: console.print(f"  [dim]•[/dim] {msg}"),
            )

            console.print(Panel(
                f"[bold green]🎉 پروژه با موفقیت در لیارا مستقر شد![/bold green]\n\n"
                f"🌐 آدرس اینترنتی (URL): [bold underline cyan]{result.url}[/bold underline cyan]\n"
                f"⏱️ زمان ساخت و دیپلوی: {result.build_time_seconds} ثانیه\n"
                f"📦 شناسه ریلیز: [dim]{result.release_id}[/dim]",
                title="✨ استقرار موفقیت‌آمیز (Deployment Complete)",
                border_style="green",
            ))

    asyncio.run(_execute())
