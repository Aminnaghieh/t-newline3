"""Config command — set/get API tokens and configure agent preferences."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from liara_agent.api.client import LiaraClient
from liara_agent.storage.credentials import default_credential_store
from liara_agent.utils.config import get_settings

config_app = typer.Typer(
    name="config",
    help="⚙️ مدیریت تنظیمات و کلیدهای دسترسی (API Tokens)",
    no_args_is_help=True,
)
console = Console()


def _mask_secret(val: str) -> str:
    if not val or len(val) < 8:
        return "********" if val else "(تنظیم نشده)"
    return f"{val[:4]}...{val[-4:]}"


@config_app.command("set-token")
def set_token(
    token: str | None = typer.Option(None, "--token", "-t", help="توکن API لیارا"),
) -> None:
    """تنظیم و اعتبارسنجی توکن API پلتفرم لیارا."""
    if not token:
        console.print("[cyan]توکن API لیارا را از کنسول کاربری (https://console.liara.ir) دریافت کنید.[/cyan]")
        token = Prompt.ask("لطفاً توکن را وارد کنید", password=True)

    if not token.strip():
        console.print("[red]❌ توکن نمی‌تواند خالی باشد.[/red]")
        raise typer.Exit(1)

    token = token.strip()

    # Validate token by checking GET /v1/me
    console.print("[blue]🔍 در حال اعتبارسنجی توکن با سرور لیارا...[/blue]")
    async def _validate() -> bool:
        try:
            async with LiaraClient(token=token) as client:
                user = await client.get_user()
                name = user.get("user", {}).get("fullname", "") or user.get("user", {}).get("email", "")
                console.print(f"[green]✅ اتصال موفق به حساب: [bold]{name}[/bold][/green]")
                return True
        except Exception as e:
            console.print(f"[red]❌ اعتبارسنجی ناموفق: {e}[/red]")
            return False

    success = asyncio.run(_validate())
    if success:
        default_credential_store.store_token("LIARA_API_TOKEN", token)
        console.print("[bold green]✨ توکن با موفقیت در محیط امن ذخیره شد.[/bold green]")
    else:
        console.print("[yellow]توکن ذخیره نشد. لطفاً از صحت آن اطمینان حاصل فرمایید.[/yellow]")
        raise typer.Exit(1)


@config_app.command("set-openai-key")
def set_openai_key(
    key: str | None = typer.Option(None, "--key", "-k", help="کلید OpenAI API"),
) -> None:
    """تنظیم کلید OpenAI جهت فعال‌سازی قابلیت‌های هوش مصنوعی (SRE Copilot)."""
    if not key:
        key = Prompt.ask("لطفاً کلید OpenAI (sk-...) را وارد کنید", password=True)

    if not key.strip():
        console.print("[red]❌ کلید نمی‌تواند خالی باشد.[/red]")
        raise typer.Exit(1)

    key = key.strip()
    default_credential_store.store_token("OPENAI_API_KEY", key)
    console.print("[bold green]✨ کلید OpenAI با موفقیت ذخیره شد.[/bold green]")


@config_app.command("show")
def show_config() -> None:
    """نمایش تنظیمات فعلی و وضعیت کلیدها."""
    settings = get_settings()

    liara_token = default_credential_store.get_token("LIARA_API_TOKEN") or settings.liara_api_token
    openai_key = default_credential_store.get_token("OPENAI_API_KEY") or settings.openai_api_key

    table = Table(title="⚙️ پیکربندی Liara SRE Agent", show_header=True, header_style="bold cyan")
    table.add_column("پارامتر", style="bold")
    table.add_column("مقدار / وضعیت")

    table.add_row(
        "Liara API Token",
        f"[green]{_mask_secret(liara_token)}[/green]" if liara_token and not liara_token.endswith("xxxx") else "[red]❌ تنظیم نشده[/red]",
    )
    table.add_row("Base URL", settings.liara_api_base_url)
    table.add_row(
        "OpenAI API Key",
        f"[green]{_mask_secret(openai_key)}[/green]" if openai_key and not openai_key.endswith("xxxx") else "[yellow]⚠️ تنظیم نشده (ویژگی‌های AI غیرفعال)[/yellow]",
    )
    table.add_row("OpenAI Model", settings.openai_model)
    table.add_row("Language", settings.language)

    console.print(table)


@config_app.command("test")
def test_connections() -> None:
    """تست برقراری ارتباط با پلتفرم لیارا و هوش مصنوعی."""
    settings = get_settings()
    liara_token = default_credential_store.get_token("LIARA_API_TOKEN") or settings.liara_api_token
    openai_key = default_credential_store.get_token("OPENAI_API_KEY") or settings.openai_api_key

    async def _test() -> None:
        console.print("[bold]1. بررسی اتصال به Liara API:[/bold]")
        if not liara_token or liara_token.endswith("xxxx"):
            console.print("  [red]❌ توکن لیارا یافت نشد.[/red]")
        else:
            try:
                async with LiaraClient(token=liara_token) as client:
                    user_data = await client.get_user()
                    email = user_data.get("user", {}).get("email", "OK")
                    console.print(f"  [green]✅ متصل به لیارا ({email})[/green]")
            except Exception as e:
                console.print(f"  [red]❌ خطا در ارتباط با لیارا: {e}[/red]")

        console.print("\n[bold]2. بررسی اتصال به OpenAI:[/bold]")
        if not openai_key or openai_key.endswith("xxxx"):
            console.print("  [yellow]⚠️ کلید OpenAI تنظیم نشده است.[/yellow]")
        else:
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(
                    api_key=openai_key,
                    base_url=settings.openai_base_url,
                )
                models = await client.models.list()
                console.print(f"  [green]✅ متصل به OpenAI ({len(models.data)} مدل در دسترس)[/green]")
            except Exception as e:
                console.print(f"  [red]❌ خطا در ارتباط با OpenAI: {e}[/red]")

    asyncio.run(_test())
