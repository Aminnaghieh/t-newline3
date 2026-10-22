"""Human-in-the-Loop approval component for risky operations."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from liara_agent.utils.constants import RiskLevel
from liara_agent.utils.formatting import risk_badge

console = Console()


def _build_details_table(details: dict[str, str]) -> Table:
    """Build a Rich table from operation details dict."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("پارامتر", style="bold cyan", no_wrap=True)
    table.add_column("مقدار", style="white")
    for key, value in details.items():
        table.add_row(key, str(value))
    return table


def request_approval(
    operation: str,
    details: dict[str, str],
    risk_level: RiskLevel,
) -> bool:
    """Request human approval for an operation based on risk level.

    Args:
        operation: Human-readable description of the operation.
        details: Key-value pairs describing the operation parameters.
        risk_level: The risk classification of the operation.

    Returns:
        True if the user approved the operation, False otherwise.
    """
    badge = risk_badge(risk_level)
    details_table = _build_details_table(details)

    # ── LOW risk: auto-approve with notification ──────────────
    if risk_level == RiskLevel.LOW:
        panel = Panel(
            details_table,
            title=f"ℹ️  {operation}",
            subtitle=str(badge),
            border_style="green",
            padding=(1, 2),
        )
        console.print(panel)
        console.print("[green]✅ عملیات کم‌ریسک — اجرای خودکار[/green]\n")
        return True

    # ── MEDIUM risk: show and ask [Y/n] ──────────────────────
    if risk_level == RiskLevel.MEDIUM:
        panel = Panel(
            details_table,
            title=f"⚡ {operation}",
            subtitle=str(badge),
            border_style="yellow",
            padding=(1, 2),
        )
        console.print(panel)
        return Confirm.ask(
            "[yellow]آیا این عملیات اجرا شود؟[/yellow]",
            default=True,
        )

    # ── HIGH risk: show detailed impact, ask [yes/NO] ────────
    if risk_level == RiskLevel.HIGH:
        impact_text = Text()
        impact_text.append("⚠️  هشدار: ", style="bold red")
        impact_text.append(
            "این عملیات ممکن است بر سرویس در حال اجرا تأثیر بگذارد.\n"
        )
        impact_text.append(
            "قبل از تأیید، مطمئن شوید که از تأثیرات آن آگاه هستید."
        )

        panel = Panel(
            details_table,
            title=f"🔴 {operation}",
            subtitle=str(badge),
            border_style="red",
            padding=(1, 2),
        )
        console.print(panel)
        console.print(impact_text)
        console.print()
        return Confirm.ask(
            "[bold red]آیا مطمئن هستید؟[/bold red]",
            default=False,
        )

    # ── CRITICAL risk: require typing "CONFIRM" ──────────────
    if risk_level == RiskLevel.CRITICAL:
        impact_text = Text()
        impact_text.append("⛔ خطر بحرانی!\n", style="bold red blink")
        impact_text.append(
            "این عملیات غیرقابل بازگشت است و ممکن است باعث از دست رفتن داده یا قطع سرویس شود.\n\n",
            style="red",
        )
        impact_text.append(
            'برای تأیید، عبارت "CONFIRM" را تایپ کنید.',
            style="bold yellow",
        )

        panel = Panel(
            details_table,
            title=f"⛔ {operation}",
            subtitle=str(badge),
            border_style="bold red",
            padding=(1, 2),
        )
        console.print(panel)
        console.print(impact_text)
        console.print()

        response = Prompt.ask(
            '[bold red]برای تأیید "CONFIRM" را تایپ کنید[/bold red]'
        )
        if response.strip() == "CONFIRM":
            console.print("[green]✅ عملیات تأیید شد[/green]\n")
            return True
        else:
            console.print("[red]❌ عملیات لغو شد[/red]\n")
            return False

    # Fallback — should never reach here
    return False
