"""CLI command: intelligent troubleshooting (RCA) and remediation."""

from __future__ import annotations

import asyncio
import time

import typer
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from liara_agent.ai.engine import AIEngine
from liara_agent.api.client import LiaraClient
from liara_agent.cli.commands.common import require_token
from liara_agent.cli.components.approval import request_approval
from liara_agent.cli.components.progress import operation_spinner
from liara_agent.cli.theme import BOX, console, print_next_steps, render_error
from liara_agent.core.debugger import Debugger
from liara_agent.storage.audit import audit
from liara_agent.utils.config import get_settings
from liara_agent.utils.errors import LiaraAgentError

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
    token = require_token()

    ai_engine = None
    if settings.openai_api_key:
        ai_engine = AIEngine(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
        )

    async def _run() -> None:
        async with LiaraClient(token=token) as client:
            dbg = Debugger(api_client=client, ai_engine=ai_engine)

            console.print(
                Panel(
                    f"[bold]پروژه هدف:[/bold] {escape(project)}\n"
                    f"[bold]موتور هوش مصنوعی:[/bold] "
                    f"{'فعال (' + escape(settings.openai_model) + ')' if ai_engine else 'غیرفعال (rule-based)'}",
                    title="🚨 شروع عملیات عیب‌یابی و ممیزی SRE",
                    border_style="red",
                    box=BOX,
                )
            )

            with operation_spinner("در حال واکشی آخرین لاگ‌ها، رویدادها و وضعیت سیستم..."):
                context = await dbg.collect_context(project)

            # --- Offline indicator ---
            if client.is_offline:
                console.print(
                    Panel(
                        "⚠️ [bold yellow]حالت آفلاین[/bold yellow]\n"
                        "ارتباط با Liara API برقرار نشد. داده‌ها از آخرین کش محلی نمایش داده می‌شوند "
                        "و ممکن است قدیمی باشند. برای بررسی مجدد، بعداً دوباره تلاش کنید.",
                        border_style="yellow",
                        box=BOX,
                    )
                )

            console.print(
                f"• {len(context.recent_logs)} خط لاگ و "
                f"{len(context.recent_events)} رویداد جمع‌آوری شد."
            )

            with operation_spinner("در حال تحلیل ریشه‌ای دلایل بروز اختلال (RCA)..."):
                diagnosis = await dbg.diagnose(context)

            if diagnosis.hypotheses:
                table = Table(
                    title="📋 فرضیات و علل احتمالی اختلال (Prioritized Hypotheses)",
                    show_header=True,
                    header_style="bold magenta",
                    box=BOX,
                )
                table.add_column("اولویت", justify="center")
                table.add_column("عنوان علت ریشه‌ای")
                table.add_column("احتمال وقوع", justify="center")
                table.add_column("دسته‌بندی", justify="center")
                table.add_column("اثر بر سیستم")
                for i, h in enumerate(diagnosis.hypotheses, start=1):
                    table.add_row(
                        f"#{i}",
                        escape(h.title),
                        f"{h.probability * 100:.0f}%",
                        escape(str(h.category)),
                        escape(h.impact),
                    )
                console.print(table)

            console.print(
                Panel(
                    f"[bold]علت اصلی:[/bold] {escape(diagnosis.root_cause_summary)}\n"
                    f"[bold]درجه اطمینان تشخیصی:[/bold] {diagnosis.confidence * 100:.0f}%",
                    title="🧠 نتیجه‌گیری موتور عیب‌یابی (RCA Summary)",
                    border_style="blue",
                    box=BOX,
                )
            )

            if not diagnosis.suggested_remediations:
                console.print("[green]هیچ اقدام اصلاحی فوری مورد نیاز نیست.[/green]")
                return

            console.print("\n[bold]🛠️ راهکارهای پیشنهادی جهت رفع مشکل:[/bold]")
            for i, r in enumerate(diagnosis.suggested_remediations, start=1):
                console.print(
                    f"  {i}. [cyan]{escape(r.title)}[/cyan] — {escape(r.description)} "
                    f"[dim](ریسک: {escape(str(r.risk_level))})[/dim]"
                )

            if not auto_fix:
                console.print(
                    "\n[dim]برای اجرای راهکار، از فلگ --auto-fix استفاده کنید.[/dim]"
                )
                return

            first = diagnosis.suggested_remediations[0]

            if (
                diagnosis.approval_expires_at
                and time.time() > diagnosis.approval_expires_at
            ):
                console.print(
                    "[red]❌ کد تأیید منقضی شده است. لطفاً دوباره debug را اجرا کنید.[/red]"
                )
                return

            # ── Unified Security Gateway ─────────────────────────
            approved = request_approval(
                operation=f"اجرای راهکار اصلاحی: {first.title}",
                details={
                    "پروژه": project,
                    "نوع اقدام": first.action_type,
                    "توضیح": first.description or "—",
                    "پارامترها": str(first.parameters),
                },
                risk_level=first.risk_level,
                approval_hash=diagnosis.approval_hash or None,
            )
            audit(
                action="debug.approval",
                target=project,
                risk_level=str(first.risk_level),
                status="approved" if approved else "denied",
                details={"action_type": first.action_type, "hash": diagnosis.approval_hash},
            )
            if not approved:
                console.print("[yellow]عملیات لغو شد — هیچ تغییری اعمال نشد.[/yellow]")
                return

            # Tamper-evidence: hash must still match the executed action.
            current_hash = first.compute_hash()
            if diagnosis.approval_hash and current_hash != diagnosis.approval_hash:
                audit(
                    action="debug.approval_mismatch",
                    target=project,
                    risk_level=str(first.risk_level),
                    status="refused",
                )
                console.print(
                    "[red]❌ کد تأیید با عملیات مطابقت ندارد (احتمال دستکاری). عملیات متوقف شد.[/red]"
                )
                return

            console.print(
                Panel(
                    f"پروژه: {escape(project)}\n"
                    f"نوع اقدام: {escape(first.action_type)}\n"
                    f"پارامترها: {escape(str(first.parameters))}",
                    title=f"⚡ اجرای راهکار اصلاحی: {escape(first.title)}",
                    border_style="yellow",
                    box=BOX,
                )
            )

            with operation_spinner("در حال اجرای دستور اصلاحی در پلتفرم لیارا..."):
                result = await dbg.execute_fix(project, first)

            audit(
                action=f"debug.fix.{first.action_type}",
                target=project,
                risk_level=str(first.risk_level),
                status="success" if result.success else "error",
                details={"message": result.message[:200]},
            )

            if result.success:
                console.print(f"[green]✅ {escape(result.message)}[/green]")
            else:
                console.print(f"[red]❌ {escape(result.message)}[/red]")
                return

            console.print("\n[cyan]🔄 در حال راستی‌آزمایی وضعیت پس از رفع مشکل...[/cyan]")
            await asyncio.sleep(5)
            post = await dbg.collect_context(project)
            console.print(
                Panel(
                    f"وضعیت کنونی برنامه: [bold]{escape(post.status)}[/bold]\n"
                    f"{'پروژه با موفقیت به چرخه عملیاتی بازگشت.' if post.status == 'ACTIVE' else 'نیاز به بررسی دستی.'}",
                    title="🎉 پایان چرخه عیب‌یابی و تایید سلامت",
                    border_style="green",
                    box=BOX,
                )
            )
            print_next_steps([
                (f"liara-agent monitor {project} --live", "پایش زنده پس از رفع مشکل"),
                (f"liara-agent logs {project} --level error", "بررسی لاگ‌های خطا"),
            ])

    try:
        asyncio.run(_run())
    except LiaraAgentError as exc:
        render_error(exc)
        raise typer.Exit(1) from exc
