"""Service management command — start, stop, restart, scale, resize, and env updates."""

from __future__ import annotations

import asyncio
from typing import Optional
import os
import typer
from rich.console import Console
from rich.table import Table

from liara_agent.api.client import LiaraClient
from liara_agent.cli.components.approval import request_approval
from liara_agent.storage.credentials import default_credential_store
from liara_agent.utils.config import get_settings
from liara_agent.utils.constants import RiskLevel
from dotenv import load_dotenv
load_dotenv()
service_app = typer.Typer(
    name="service",
    help="⚡ مدیریت عملیات زیرساخت، وضعیت، مقیاس‌پذیری و تنظیمات سرویس‌ها",
    no_args_is_help=True,
)
console = Console()


def _get_client_and_token() -> str:
    settings = get_settings()
    token = default_credential_store.get_token("LIARA_API_TOKEN") or settings.liara_api_token
    if not token or token.endswith("xxxx"):
        console.print("[yellow]⚠️ ابتدا توکن API لیارا را تنظیم کنید:[/yellow]")
        console.print("  [cyan]liara-agent config set-token[/cyan]\n")
        raise typer.Exit(1)
    return token


@service_app.command("list")
def list_projects() -> None:
    """مشاهده لیست تمام اپلیکیشن‌های موجود در حساب لیارا."""
    token = _get_client_and_token()

    async def _list() -> None:
        async with LiaraClient(token=token, team_id=os.getenv("LIARA_TEAM_ID")) as client:
            print("DEBUG team_id:", client._team_id)
            print("DEBUG token:", token[:20] if token else None)
            resp = await client.get_projects()
            print("DEBUG resp:", resp)
            table = Table(title="📋 لیست اپلیکیشن‌های شما در لیارا", show_header=True, header_style="bold cyan")
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
                    f"[{status_color}]{p.status}[/{status_color}]",
                    str(p.scale),
                    "بله" if p.isDeployed else "خیر",
                )
            console.print(table)

    asyncio.run(_list())


@service_app.command("info")
def project_info(project: str = typer.Argument(..., help="نام پروژه")) -> None:
    """مشاهده جزئیات کامل و وضعیت یک پروژه."""
    token = _get_client_and_token()

    async def _info() -> None:
        async with LiaraClient(token=token) as client:
            resp = await client.get_project(project)
            p = resp.project

            table = Table(title=f"ℹ️ جزئیات پروژه: {project}", show_header=False)
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
    token = _get_client_and_token()

    approved = request_approval(
        operation=f"راه‌اندازی مجدد (Restart) پروژه '{project}'",
        details={"پروژه": project, "اثر": "توقف موقت چند ثانیه‌ای و راه‌اندازی کانتینرها"},
        risk_level=RiskLevel.MEDIUM,
    )
    if not approved:
        console.print("[yellow]عملیات لغو شد.[/yellow]")
        return

    async def _restart() -> None:
        async with LiaraClient(token=token) as client:
            await client.restart_project(project)
            console.print(f"[bold green]✅ پروژه '{project}' با موفقیت ری‌استارت شد.[/bold green]")

    asyncio.run(_restart())


@service_app.command("scale")
def scale(
    project: str = typer.Argument(..., help="نام پروژه"),
    scale_val: int = typer.Argument(..., help="1 برای روشن و 0 برای خاموش کردن"),
) -> None:
    """تغییر وضعیت اسکیل (روشن یا خاموش کردن اپلیکیشن)."""
    token = _get_client_and_token()

    approved = request_approval(
        operation=f"تغییر مقیاس (Scale) پروژه '{project}' به {scale_val}",
        details={
            "پروژه": project,
            "وضعیت هدف": "روشن (Scale 1)" if scale_val == 1 else "خاموش (Scale 0)",
        },
        risk_level=RiskLevel.HIGH,
    )
    if not approved:
        console.print("[yellow]عملیات لغو شد.[/yellow]")
        return

    async def _scale() -> None:
        async with LiaraClient(token=token) as client:
            await client.scale_project(project, scale_val)
            console.print(f"[bold green]✅ وضعیت اسکیل پروژه '{project}' به {scale_val} تغییر یافت.[/bold green]")

    asyncio.run(_scale())


@service_app.command("resize")
def resize(
    project: str = typer.Argument(..., help="نام پروژه"),
    plan_id: str = typer.Argument(..., help="شناسه پلن جدید (micro, small, medium, large, ...)"),
) -> None:
    """تغییر پلن سخت‌افزاری (CPU/RAM) پروژه."""
    token = _get_client_and_token()

    approved = request_approval(
        operation=f"تغییر پلن سخت‌افزاری پروژه '{project}' به '{plan_id}'",
        details={"پروژه": project, "پلن جدید": plan_id},
        risk_level=RiskLevel.HIGH,
    )
    if not approved:
        console.print("[yellow]عملیات لغو شد.[/yellow]")
        return

    async def _resize() -> None:
        async with LiaraClient(token=token) as client:
            await client.change_plan(project, plan_id)
            console.print(f"[bold green]✅ پلن پروژه '{project}' با موفقیت به '{plan_id}' تغییر یافت.[/bold green]")

    asyncio.run(_resize())
