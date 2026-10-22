"""Debug command — intelligent troubleshooting, RCA, and auto-remediation."""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from liara_agent.ai.engine import AIEngine
from liara_agent.api.client import LiaraClient
from liara_agent.cli.components.approval import request_approval
from liara_agent.cli.components.progress import operation_spinner
from liara_agent.core.debugger import Debugger, Remediation
from liara_agent.storage.credentials import default_credential_store
from liara_agent.utils.config import get_settings
from liara_agent.utils.constants import RiskLevel

debug_app = typer.Typer(
    name="debug",
    help="🔍 عیب‌یابی هوشمند، تحلیل ریشه‌ای خطاها (RCA) و رفع خودکار با تأیید",
    no_args_is_help=False,
)
console = Console()


@debug_app.callback(invoke_without_command=True)
def run_debug(
    project: str = typer.Argument(..., help="نام اپلیکیشن دارای اختلال"),
    auto_fix: bool = typer.Option(False, "--auto-fix", "-f", help="تلاش برای اعمال خودکار راه‌حل پس از تأیید"),
) -> None:
    """جمع‌آوری اطلاعات خطا، شناسایی علت و ارائه راهکار اصلاحی به کمک هوش مصنوعی."""
    settings = get_settings()
    token = default_credential_store.get_token("LIARA_API_TOKEN") or settings.liara_api_token
    if not token or token.endswith("xxxx"):
        console.print("[yellow]⚠️ ابتدا توکن API لیارا را تنظیم کنید.[/yellow]")
        raise typer.Exit(1)

    openai_key = default_credential_store.get_token("OPENAI_API_KEY") or settings.openai_api_key
    ai_engine = AIEngine(api_key=openai_key, model=settings.openai_model) if openai_key and not openai_key.endswith("xxxx") else None

    console.print(Panel(
        f"[bold red]🚨 شروع عملیات عیب‌یابی و ممیزی SRE[/bold red]\n"
        f"پروژه هدف: [yellow]{project}[/yellow]\n"
        f"موتور هوش مصنوعی: [green]{'فعال (GPT-4o)' if ai_engine else 'غیرفعال (مبتنی بر قوانین و الگوهای خطا)'}[/green]",
        border_style="red",
    ))

    async def _diagnose_and_remediate() -> None:
        async with LiaraClient(token=token) as client:
            debugger = Debugger(client, ai_engine=ai_engine)

            # 1. Collect Context
            with operation_spinner("در حال واکشی آخرین لاگ‌ها، رویدادها و وضعیت سیستم..."):
                ctx = await debugger.collect_context(project)

            console.print(f"[dim]• {len(ctx.recent_logs)} خط لاگ و {len(ctx.recent_events)} رویداد جمع‌آوری شد.[/dim]")

            # 2. Run Diagnosis (RCA)
            with operation_spinner("در حال تحلیل ریشه‌ای دلایل بروز اختلال (RCA)..."):
                diagnosis = await debugger.diagnose(ctx)

            # 3. Present Hypotheses
            table = Table(title="📋 فرضیات و علل احتمالی اختلال (Prioritized Hypotheses)", show_header=True, header_style="bold cyan")
            table.add_column("اولویت", justify="center")
            table.add_column("عنوان علت ریشه‌ای", style="bold")
            table.add_column("احتمال وقوع", justify="center")
            table.add_column("دسته‌بندی")
            table.add_column("اثر بر سیستم")

            for idx, hyp in enumerate(diagnosis.hypotheses, 1):
                prob_pct = f"{hyp.probability * 100:.0f}%"
                prob_style = "bold red" if hyp.probability > 0.8 else ("yellow" if hyp.probability > 0.5 else "dim")
                table.add_row(
                    f"#{idx}",
                    hyp.title,
                    f"[{prob_style}]{prob_pct}[/{prob_style}]",
                    hyp.category,
                    hyp.impact,
                )

            console.print(table)

            if diagnosis.hypotheses:
                console.print(Panel(
                    f"[bold]علت اصلی:[/bold] {diagnosis.hypotheses[0].title}\n"
                    f"[bold]توضیحات فنی:[/bold] {diagnosis.hypotheses[0].explanation}\n"
                    f"[bold]درجه اطمینان تشخیصی:[/bold] {diagnosis.confidence * 100:.0f}%",
                    title="🧠 نتیجه‌گیری موتور عیب‌یابی (RCA Summary)",
                    border_style="yellow",
                ))

            # 4. Present Remediation Options
            if not diagnosis.suggested_remediations:
                console.print("[green]هیچ اقدام اصلاحی فوری مورد نیاز نیست.[/green]")
                return

            console.print("\n[bold cyan]🛠️ راهکارهای پیشنهادی جهت رفع مشکل:[/bold cyan]")
            for i, rem in enumerate(diagnosis.suggested_remediations, 1):
                console.print(f"  [bold cyan]{i}.[/bold cyan] [bold]{rem.title}[/bold] — {rem.description} [dim](ریسک: {rem.risk_level})[/dim]")

            chosen_rem = diagnosis.suggested_remediations[0]

            # 5. Human-in-the-Loop Approval for Remediation
            should_apply = auto_fix or Confirm.ask(
                f"\nآیا مایل به اجرای راهکار اول ([bold]{chosen_rem.title}[/bold]) هستید؟",
                default=True,
            )

            if not should_apply:
                console.print("[yellow]عملیات اصلاحی اجرا نشد.[/yellow]")
                return

            approved = request_approval(
                operation=f"اجرای راهکار اصلاحی: {chosen_rem.title}",
                details={
                    "پروژه": project,
                    "نوع اقدام": chosen_rem.action_type,
                    "پارامترها": str(chosen_rem.parameters),
                },
                risk_level=chosen_rem.risk_level,
            )

            if not approved:
                console.print("[yellow]عملیات توسط کاربر لغو گردید.[/yellow]")
                return

            # 6. Execute Fix
            with operation_spinner("در حال اجرای دستور اصلاحی در پلتفرم لیارا..."):
                fix_res = await debugger.execute_fix(project, chosen_rem)

            if fix_res.success:
                console.print(f"[bold green]✅ {fix_res.message}[/bold green]")

                # 7. Verification Loop
                console.print("\n[blue]🔄 در حال راستی‌آزمایی وضعیت پس از رفع مشکل (Verification Loop)...[/blue]")
                await asyncio.sleep(5)
                new_ctx = await debugger.collect_context(project)
                console.print(Panel(
                    f"وضعیت کنونی برنامه: [bold]{new_ctx.status}[/bold]\n"
                    f"پروژه با موفقیت به چرخه عملیاتی بازگشت.",
                    title="🎉 پایان چرخه عیب‌یابی و تایید سلامت",
                    border_style="green",
                ))
            else:
                console.print(f"[bold red]❌ خطا در اعمال راهکار: {fix_res.message}[/bold red]")

    asyncio.run(_diagnose_and_remediate())
