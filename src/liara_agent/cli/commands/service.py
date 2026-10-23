"""Service management command — status, restart, scale, resize, and info."""

from __future__ import annotations

import asyncio
import json

import typer
from rich.markup import escape
from rich.table import Table

from liara_agent.api.client import LiaraClient
from liara_agent.cli.commands.common import cancelled, require_token
from liara_agent.cli.components.approval import request_approval
from liara_agent.cli.theme import BOX, console
from liara_agent.storage.audit import audit
from liara_agent.utils.constants import RiskLevel

service_app = typer.Typer(
    name="service",
    help="⚡ مدیریت عملیات زیرساخت، وضعیت، مقیاس‌پذیری و تنظیمات سرویس‌ها",
    no_args_is_help=True,
)


@service_app.command("list")
def list_projects(
    json_output: bool = typer.Option(False, "--json", help="خروجی JSON برای اسکریپت‌نویسی"),
) -> None:
    """مشاهده لیست تمام اپلیکیشن‌های موجود در حساب لیارا."""
    token = require_token()

    async def _list() -> None:
        async with LiaraClient(token=token) as client:
            resp = await client.get_projects()

            if json_output:
                console.print_json(json.dumps(
                    [
                        {
                            "name": p.name or p.project_id,
                            "platform": p.type,
                            "plan": p.planID,
                            "status": p.status,
                            "scale": p.scale,
                            "deployed": p.isDeployed,
                        }
                        for p in resp.projects
                    ],
                    ensure_ascii=False,
                ))
                return

            table = Table(
                title="📋 لیست اپلیکیشن‌های شما در لیارا",
                show_header=True,
                header_style="bold cyan",
                box=BOX,
            )
            table.add_column("نام پروژه", style="bold")
            table.add_column("پلتفرم")
            table.add_column("پلن فعلی")
            table.add_column("وضعیت", justify="center")
            table.add_column("اسکیل")
            table.add_column("دیپلوی شده؟")

            for p in resp.projects:
                status_color = "green" if p.status == "running" else ("yellow" if p.status == "deploying" else "red")
                table.add_row(
                    p.name or p.project_id,
                    p.type or "—",
                    p.planID or "—",
                    f"[{status_color}]{escape(p.status or '—')}[/{status_color}]",
                    str(p.scale),
                    "بله" if p.isDeployed else "خیر",
                )
            console.print(table)

    try:
        asyncio.run(_list())
    except Exception as exc:
        audit(action="service.list", status="error", details={"error": str(exc)[:200]})
        raise


@service_app.command("info")
def project_info(project: str = typer.Argument(..., help="نام پروژه")) -> None:
    """مشاهده جزئیات کامل و وضعیت یک پروژه."""
    token = require_token()

    async def _info() -> None:
        async with LiaraClient(token=token) as client:
            resp = await client.get_project(project)
            p = resp.project

            table = Table(title=f"ℹ️ جزئیات پروژه: {escape(project)}", show_header=False, box=BOX)
            table.add_column("مشخصه", style="bold cyan")
            table.add_column("مقدار")

            table.add_row("نام پروژه", p.name or p.project_id)
            table.add_row("پلتفرم", p.type)
            table.add_row("وضعیت", p.status)
            table.add_row("پلن", p.planID)
            table.add_row("مقیاس (Scale)", str(p.scale))
            table.add_row("پورت", str(p.port or "پیش‌فرض"))
            table.add_row("تاریخ ساخت", str(p.created_at))

            console.print(table)

    asyncio.run(_info())


@service_app.command("restart")
def restart(project: str = typer.Argument(..., help="نام پروژه")) -> None:
    """راه‌اندازی مجدد (Restart) یک سرویس."""
    token = require_token()

    approved = request_approval(
        operation=f"راه‌اندازی مجدد (Restart) پروژه '{project}'",
        details={"پروژه": project, "اثر": "توقف موقت چند ثانیه‌ای و راه‌اندازی کانتینرها"},
        risk_level=RiskLevel.MEDIUM,
    )
    if not approved:
        audit(action="service.restart", target=project, risk_level="medium", status="denied")
        cancelled()
        return

    async def _restart() -> None:
        async with LiaraClient(token=token) as client:
            await client.restart_project(project)
            audit(action="service.restart", target=project, risk_level="medium", status="success")
            console.print(f"[bold green]✅ پروژه '{escape(project)}' با موفقیت ری‌استارت شد.[/bold green]")

    try:
        asyncio.run(_restart())
    except Exception as exc:
        audit(action="service.restart", target=project, risk_level="medium", status="error", details={"error": str(exc)[:200]})
        raise


@service_app.command("scale")
def scale(
    project: str = typer.Argument(..., help="نام پروژه"),
    scale_val: int = typer.Argument(..., help="1 برای روشن و 0 برای خاموش کردن"),
) -> None:
    """تغییر وضعیت اسکیل (روشن یا خاموش کردن اپلیکیشن)."""
    token = require_token()

    approved = request_approval(
        operation=f"تغییر مقیاس (Scale) پروژه '{project}' به {scale_val}",
        details={
            "پروژه": project,
            "وضعیت هدف": "روشن (Scale 1)" if scale_val == 1 else "خاموش (Scale 0)",
        },
        risk_level=RiskLevel.HIGH,
    )
    if not approved:
        audit(action="service.scale", target=project, risk_level="high", status="denied", details={"scale": scale_val})
        cancelled()
        return

    async def _scale() -> None:
        async with LiaraClient(token=token) as client:
            await client.scale_project(project, scale_val)
            audit(action="service.scale", target=project, risk_level="high", status="success", details={"scale": scale_val})
            console.print(f"[bold green]✅ وضعیت اسکیل پروژه '{escape(project)}' به {scale_val} تغییر یافت.[/bold green]")

    try:
        asyncio.run(_scale())
    except Exception as exc:
        audit(action="service.scale", target=project, risk_level="high", status="error", details={"error": str(exc)[:200]})
        raise


@service_app.command("resize")
def resize(
    project: str = typer.Argument(..., help="نام پروژه"),
    plan_id: str = typer.Argument(..., help="شناسه پلن جدید (micro, small, medium, large, ...)"),
) -> None:
    """تغییر پلن سخت‌افزاری (CPU/RAM) پروژه."""
    token = require_token()

    approved = request_approval(
        operation=f"تغییر پلن سخت‌افزاری پروژه '{project}' به '{plan_id}'",
        details={"پروژه": project, "پلن جدید": plan_id},
        risk_level=RiskLevel.HIGH,
    )
    if not approved:
        audit(action="service.resize", target=project, risk_level="high", status="denied", details={"plan": plan_id})
        cancelled()
        return

    async def _resize() -> None:
        async with LiaraClient(token=token) as client:
            await client.change_plan(project, plan_id)
            audit(action="service.resize", target=project, risk_level="high", status="success", details={"plan": plan_id})
            console.print(f"[bold green]✅ پلن پروژه '{escape(project)}' با موفقیت به '{escape(plan_id)}' تغییر یافت.[/bold green]")

    try:
        asyncio.run(_resize())
    except Exception as exc:
        audit(action="service.resize", target=project, risk_level="high", status="error", details={"error": str(exc)[:200]})
        raise
