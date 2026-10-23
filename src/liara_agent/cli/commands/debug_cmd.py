"""CLI command: intelligent troubleshooting (RCA) and remediation."""

from __future__ import annotations

import asyncio
import time

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from liara_agent.ai.engine import AIEngine
from liara_agent.api.client import LiaraClient
from liara_agent.core.debugger import Debugger, Remediation
from liara_agent.utils.config import get_settings

console = Console()

debug_app = typer.Typer(
    name="debug",
    help="🔍 عیب‌یابی هوشمند، تحلیل ریشه‌ای خطاها (RCA) و رفع خودکار با تأیید",
    no_args_is_help=True,
)


@debug_app.command("run")
def run_debug(
    project: str = typer.Argument(..., help="نام اپلیکیشن دارای اختلال"),
    auto_fix: bool = typer.Option(
        False, "--auto-fix", "-f", help="تلاش برای اعمال خودکار راه‌حل پس از تأیید"
    ),
) -> None:
    """اجرای کامل چرخه عیب‌یابی: جمع‌آوری کانتکست، RCA، پیشنهاد راه‌حل و اجرای اصلاح."""
    settings = get_settings()
    token = settings.liara_api_token
    if not token:
        console.print("[red]❌ توکن API لیارا تنظیم نشده است.[/red]")
        raise typer.Exit(code=1)

    ai_engine = None
    if settings.openai_api_key:
        ai_engine = AIEngine(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

    async def _run() -> None:
        async with LiaraClient(token=token) as client:
            dbg = Debugger(api_client=client, ai_engine=ai_engine)

            console.print(
                Panel.fit(
                    f"[bold]پروژه هدف:[/bold] {project}\n"
                    f"[bold]موتور هوش مصنوعی:[/bold] "
                    f"{'فعال (' + settings.openai_model + ')' if ai_engine else 'غیرفعال (rule-based)'}",
                    title="🚨 شروع عملیات عیب‌یابی و ممیزی SRE",
                    border_style="red",
                )
            )

            with console.status("[cyan]در حال واکشی آخرین لاگ‌ها، رویدادها و وضعیت سیستم...[/cyan]"):
                context = await dbg.collect_context(project)

            # --- Offline indicator ---
            if client.is_offline:
                console.print(
                    Panel.fit(
                        "⚠️ [bold yellow]حالت آفلاین[/bold yellow]\n"
                        "ارتباط با Liara API برقرار نشد. داده‌ها از آخرین کش محلی نمایش داده می‌شوند "
                        "و ممکن است قدیمی باشند. برای بررسی مجدد، بعداً دوباره تلاش کنید.",
                        border_style="yellow",
                    )
                )

            console.print(
                f"• {len(context.recent_logs)} خط لاگ و "
                f"{len(context.recent_events)} رویداد جمع‌آوری شد."
            )

            with console.status("[cyan]در حال تحلیل ریشه‌ای دلایل بروز اختلال (RCA)...[/cyan]"):
                diagnosis = await dbg.diagnose(context)

            if diagnosis.hypotheses:
                table = Table(
                    title="📋 فرضیات و علل احتمالی اختلال (Prioritized Hypotheses)",
                    show_header=True,
                    header_style="bold magenta",
                )
                table.add_column("اولویت", justify="center")
                table.add_column("عنوان علت ریشه‌ای")
                table.add_column("احتمال وقوع", justify="center")
                table.add_column("دسته‌بندی", justify="center")
                table.add_column("اثر بر سیستم")
                for i, h in enumerate(diagnosis.hypotheses, start=1):
                    table.add_row(
                        f"#{i}",
                        h.title,
                        f"{h.probability * 100:.0f}%",
                        str(h.category),
                        h.impact,
                    )
                console.print(table)

            console.print(
                Panel.fit(
                    f"[bold]علت اصلی:[/bold] {diagnosis.root_cause_summary}\n"
                    f"[bold]درجه اطمینان تشخیصی:[/bold] {diagnosis.confidence * 100:.0f}%",
                    title="🧠 نتیجه‌گیری موتور عیب‌یابی (RCA Summary)",
                    border_style="blue",
                )
            )

            if not diagnosis.suggested_remediations:
                console.print("[green]هیچ اقدام اصلاحی فوری مورد نیاز نیست.[/green]")
                return

            if diagnosis.approval_hash:
                remaining = int(diagnosis.approval_expires_at - time.time())
                console.print(
                    f"\n🔐 [bold]کد تأیید عملیات:[/bold] [yellow]{diagnosis.approval_hash}[/yellow]"
                    f"  [dim](اعتبار: {max(remaining, 0)} ثانیه)[/dim]"
                )

            console.print("\n[bold]🛠️ راهکارهای پیشنهادی جهت رفع مشکل:[/bold]")
            for i, r in enumerate(diagnosis.suggested_remediations, start=1):
                console.print(
                    f"  {i}. [cyan]{r.title}[/cyan] — {r.description} "
                    f"[dim](ریسک: {r.risk_level})[/dim]"
                )

            if not auto_fix:
                console.print(
                    "\n[dim]برای اجرای راهکار، از فلگ --auto-fix استفاده کنید.[/dim]"
                )
                return

            first: Remediation = diagnosis.suggested_remediations[0]

            if (
                diagnosis.approval_expires_at
                and time.time() > diagnosis.approval_expires_at
            ):
                console.print(
                    "[red]❌ کد تأیید منقضی شده است. لطفاً دوباره debug را اجرا کنید.[/red]"
                )
                return

            answer = typer.prompt(
                f"\nآیا مایل به اجرای راهکار اول ({first.title}) هستید؟ [y/n]",
                default="y",
            )
            if answer.strip().lower() not in {"y", "yes"}:
                console.print("[yellow]عملیات لغو شد.[/yellow]")
                return

            current_hash = first.compute_hash()
            if diagnosis.approval_hash and current_hash != diagnosis.approval_hash:
                console.print(
                    "[red]❌ کد تأیید با عملیات مطابقت ندارد (احتمال دستکاری).[/red]"
                )
                return

            if str(first.risk_level).lower() in {"high", "critical"}:
                confirm = typer.prompt(
                    f"⚠️ عملیات پرریسک است. برای ادامه عبارت «{first.title}» را تایپ کنید",
                    default="",
                )
                if confirm.strip() != first.title:
                    console.print("[yellow]عملیات لغو شد.[/yellow]")
                    return

            console.print(
                Panel.fit(
                    f"پروژه: {project}\n"
                    f"نوع اقدام: {first.action_type}\n"
                    f"پارامترها: {first.parameters}",
                    title=f"⚡ اجرای راهکار اصلاحی: {first.title}",
                    border_style="yellow",
                )
            )

            with console.status("[cyan]در حال اجرای دستور اصلاحی در پلتفرم لیارا...[/cyan]"):
                result = await dbg.execute_fix(project, first)

            if result.success:
                console.print(f"[green]✅ {result.message}[/green]")
            else:
                console.print(f"[red]❌ {result.message}[/red]")
                return

            console.print("\n[cyan]🔄 در حال راستی‌آزمایی وضعیت پس از رفع مشکل...[/cyan]")
            await asyncio.sleep(5)
            post = await dbg.collect_context(project)
            console.print(
                Panel.fit(
                    f"وضعیت کنونی برنامه: [bold]{post.status}[/bold]\n"
                    f"{'پروژه با موفقیت به چرخه عملیاتی بازگشت.' if post.status == 'ACTIVE' else 'نیاز به بررسی دستی.'}",
                    title="🎉 پایان چرخه عیب‌یابی و تایید سلامت",
                    border_style="green",
                )
            )

    asyncio.run(_run())