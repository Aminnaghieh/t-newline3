"""Init command — project analysis, optimal plan wizard, and initial deployment."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from liara_agent.api.client import LiaraClient
from liara_agent.cli.commands.common import cancelled, require_token
from liara_agent.cli.components.approval import request_approval
from liara_agent.cli.components.progress import deploy_progress, operation_spinner
from liara_agent.cli.theme import BOX, console, print_next_steps, render_error
from liara_agent.core.analyzer import ProjectAnalyzer
from liara_agent.core.deployer import Deployer
from liara_agent.core.planner import PlanRecommender
from liara_agent.models.plans import get_plan_by_id
from liara_agent.models.project import ProjectCreate
from liara_agent.storage.audit import audit
from liara_agent.utils.constants import RiskLevel
from liara_agent.utils.errors import LiaraAgentError

init_app = typer.Typer(
    name="init",
    help="🚀 راه‌اندازی گام‌به‌گام پروژه و اولین دیپلوی با هوش مصنوعی",
    no_args_is_help=False,
)


@init_app.callback(invoke_without_command=True)
def run_init(
    path: Path | None = typer.Argument(
        None,
        help="مسیر پوشه پروژه (پیش‌فرض: پوشه جاری)",
    ),
) -> None:
    """تحلیل هوشمند سورس‌کد، پیشنهاد بهترین پلن و استقرار خودکار."""
    project_path = path or Path.cwd()
    if not project_path.is_dir():
        console.print(f"[red]❌ مسیر '{escape(str(project_path))}' وجود ندارد یا پوشه نیست.[/red]")
        raise typer.Exit(1)

    token = require_token()

    console.print(Panel(
        f"[bold cyan]🔍 تحلیل هوشمند و آماده‌سازی پروژه[/bold cyan]\n"
        f"مسیر: [yellow]{escape(str(project_path.resolve()))}[/yellow]",
        border_style="cyan",
        box=BOX,
    ))

    # 1. Analyze Project
    with operation_spinner("در حال کاوش فایل‌ها و تحلیل ساختار پروژه..."):
        analyzer = ProjectAnalyzer(project_path)
        analysis = analyzer.analyze()

    # 2. Display Analysis Results
    info_table = Table(title="📊 نتایج تحلیل سورس‌کد", show_header=True, header_style="bold magenta", box=BOX)
    info_table.add_column("مشخصه", style="bold")
    info_table.add_column("مقدار شناسایی شده")

    info_table.add_row("زبان / پلتفرم", f"[green]{escape(analysis.platform)}[/green]")
    info_table.add_row("فریم‌ورک", escape(analysis.framework) if analysis.framework else "[dim]عمومی[/dim]")
    info_table.add_row("پورت پیش‌فرض", str(analysis.port))
    info_table.add_row("دستور اجرا (Start)", escape(analysis.start_cmd or "—"))
    if analysis.build_cmd:
        info_table.add_row("دستور بیلد", escape(analysis.build_cmd))
    info_table.add_row("تعداد پکیج‌ها", str(len(analysis.dependencies)))
    info_table.add_row("حجم تخمینی سورس", f"{analysis.project_size_mb:.2f} MB")

    console.print(info_table)

    # 3. Plan Recommendation
    planner = PlanRecommender()
    recommendation = planner.recommend(analysis)
    plan_info = get_plan_by_id(recommendation.recommended_plan)

    plan_panel = Panel(
        f"[bold green]پلن پیشنهادی: {escape(plan_info.label)} ({escape(plan_info.id)})[/bold green]\n"
        f"مشخصات: [cyan]{plan_info.cpu} هسته CPU | {plan_info.ram_gb} گیگابایت RAM | {plan_info.disk_gb} گیگابایت دیسک[/cyan]\n"
        f"[dim]دلیل انتخاب: {escape(recommendation.reason)}[/dim]",
        title="💡 پیشنهاد هوشمند پلن زیرساخت",
        border_style="green",
        box=BOX,
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
        console.print(f"\n[cyan]متغیرهای محیطی احتمالی شناسایی شده: {', '.join(escape(v) for v in analysis.env_vars_needed)}[/cyan]")
        if Confirm.ask("آیا مایل به مقداردهی متغیرهای محیطی هستید؟", default=False):
            for env_name in analysis.env_vars_needed:
                val = Prompt.ask(f"مقدار برای {env_name}", password=True, default="")
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
        audit(action="init.deploy", target=app_name, risk_level="high", status="denied")
        cancelled("عملیات توسط کاربر لغو گردید.")
        raise typer.Exit(0)

    # 6. Execute Creation & Deployment
    async def _execute() -> None:
        async with LiaraClient(token=token) as client:
            # Check if project exists, else create
            try:
                console.print(f"[blue]🔨 در حال ساخت پروژه '{escape(app_name)}' در لیارا...[/blue]")
                create_req = ProjectCreate(
                    name=app_name,
                    planID=selected_plan,
                    platform=analysis.platform,
                )
                await client.create_project(create_req)
                audit(action="project.create", target=app_name, risk_level="high", status="success", details={"plan": selected_plan})
                console.print(f"[green]✅ پروژه '{escape(app_name)}' با موفقیت ساخته شد.[/green]")
            except LiaraAgentError as e:
                if "409" in str(e) or "already exists" in str(e).lower():
                    console.print(f"[dim]ℹ️ پروژه '{escape(app_name)}' از قبل وجود دارد، ادامه با همین پروژه...[/dim]")
                else:
                    raise

            # Update Envs if any
            if env_vars:
                console.print("[blue]📝 در حال ثبت متغیرهای محیطی...[/blue]")
                await client.update_envs(app_name, env_vars)
                audit(action="env.update", target=app_name, risk_level="medium", status="success", details={"count": len(env_vars)})

            # Deploy source with staged progress
            console.print("\n[bold cyan]🚀 شروع استقرار کدهای پروژه...[/bold cyan]")
            deployer = Deployer(client)
            with deploy_progress() as progress:
                task = progress.add_task("🚀 آغاز استقرار…", total=1.0)

                def _on_progress(msg: str, p: float) -> None:
                    progress.update(task, description=f"[bold blue]{escape(msg)}", completed=p)

                result = await deployer.deploy(
                    project_name=app_name,
                    source_path=project_path,
                    port=selected_port,
                    platform_type=analysis.platform,
                    progress_cb=_on_progress,
                )

            audit(
                action="init.deploy",
                target=app_name,
                risk_level="high",
                status="success",
                details={"release_id": result.release_id, "url": result.url},
            )
            console.print(Panel(
                f"[bold green]🎉 پروژه با موفقیت در لیارا مستقر شد![/bold green]\n\n"
                f"🌐 آدرس اینترنتی (URL): [bold underline cyan]{result.url}[/bold underline cyan]\n"
                f"⏱️ زمان ساخت و دیپلوی: {result.build_time_seconds} ثانیه\n"
                f"📦 شناسه ریلیز: [dim]{escape(result.release_id)}[/dim]",
                title="✨ استقرار موفقیت‌آمیز (Deployment Complete)",
                border_style="green",
                box=BOX,
            ))
            print_next_steps([
                (f"liara-agent monitor {app_name} --live", "داشبورد زنده مصرف CPU/RAM"),
                (f"liara-agent logs {app_name} -f", "استریم زنده لاگ‌ها"),
                (f"liara-agent debug {app_name}", "عیب‌یابی هوشمند در صورت بروز خطا"),
            ])

    try:
        asyncio.run(_execute())
    except LiaraAgentError as exc:
        audit(action="init.deploy", target=app_name, risk_level="high", status="error", details={"error": str(exc)[:200]})
        render_error(exc)
        raise typer.Exit(1) from exc
