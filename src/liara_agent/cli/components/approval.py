"""Human-in-the-Loop approval component — the unified Security Gateway.

Every risky operation renders through the same "security gateway card":
risk badge, operation details, impact statement, optional approval hash and
a tier-appropriate confirmation prompt (LOW auto-runs, MEDIUM asks Y/n,
HIGH defaults to NO, CRITICAL requires typing ``CONFIRM``).
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from liara_agent.cli.theme import BOX, console, escape_markup
from liara_agent.utils.constants import RiskLevel
from liara_agent.utils.formatting import risk_badge

# Persian tier labels + impact statements.
_RISK_TITLES = {
    RiskLevel.LOW: "عملیات کم‌ریسک",
    RiskLevel.MEDIUM: "عملیات متوسط",
    RiskLevel.HIGH: "عملیات پرریسک",
    RiskLevel.CRITICAL: "عملیات بحرانی",
}

_IMPACT_TEXTS = {
    RiskLevel.LOW: "خواندن داده و مشاهده وضعیت — بدون تغییر در زیرساخت.",
    RiskLevel.MEDIUM: "این عملیات سرویس شما را موقتاً تحت تأثیر قرار می‌دهد.",
    RiskLevel.HIGH: (
        "این عملیات ممکن است بر سرویس در حال اجرا یا هزینه شما تأثیر بگذارد."
    ),
    RiskLevel.CRITICAL: (
        "این عملیات غیرقابل بازگشت است و ممکن است باعث از دست رفتن داده یا قطع سرویس شود."
    ),
}


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
    approval_hash: str | None = None,
    con: Console | None = None,
) -> bool:
    """Request human approval for an operation based on risk level.

    Args:
        operation: Human-readable description of the operation.
        details: Key-value pairs describing the operation parameters.
        risk_level: The risk classification of the operation.
        approval_hash: Optional tamper-evident hash binding this approval to
            the exact action (shown in the gateway card).
        con: Optional console override (tests).

    Returns:
        True if the user approved the operation, False otherwise.
    """
    out = con or console
    badge = risk_badge(risk_level)
    op_escaped = escape_markup(operation)

    # Gateway card body: details + impact + optional approval hash.
    body_parts: list[Text | Table] = [_build_details_table(details)]
    impact = Text()
    impact.append("⚠️  ", style="bold yellow")
    impact.append(_IMPACT_TEXTS.get(risk_level, ""), style="white")
    body_parts.append(impact)
    if approval_hash:
        hash_line = Text()
        hash_line.append("🔐 کد تأیید عملیات: ", style="dim")
        hash_line.append(approval_hash, style="bold yellow")
        hash_line.append("  (این کد عملیات را به پروژه هدف مقید می‌کند)", style="dim")
        body_parts.append(hash_line)

    from rich.console import Group

    border = {
        RiskLevel.LOW: "green",
        RiskLevel.MEDIUM: "yellow",
        RiskLevel.HIGH: "red",
        RiskLevel.CRITICAL: "bold red",
    }[risk_level]

    card = Panel(
        Group(*body_parts),
        title=f"🛡️ دروازه تایید عملیات — {op_escaped}",
        subtitle=str(badge),
        border_style=border,
        box=BOX,
        padding=(1, 2),
    )
    out.print()
    out.print(card)

    # ── Tier-specific confirmation ────────────────────────────
    if risk_level == RiskLevel.LOW:
        out.print("[green]✅ عملیات کم‌ریسک — اجرای خودکار[/green]\n")
        return True

    if risk_level == RiskLevel.MEDIUM:
        return Confirm.ask("[yellow]آیا این عملیات اجرا شود؟[/yellow]", default=True)

    if risk_level == RiskLevel.HIGH:
        out.print("[bold red]هشدار: پیش از تایید، از تأثیرات عملیات مطمئن شوید.[/bold red]")
        return Confirm.ask("[bold red]آیا مطمئن هستید؟[/bold red]", default=False)

    # CRITICAL: require typing CONFIRM
    warn = Text()
    warn.append("⛔ خطر بحرانی!\n", style="bold red blink")
    warn.append(
        "برای تأیید، عبارت CONFIRM را دقیقاً تایپ کنید.",
        style="bold yellow",
    )
    out.print(warn)
    out.print()
    response = Prompt.ask('[bold red]"CONFIRM" را تایپ کنید[/bold red]')
    if response.strip() == "CONFIRM":
        out.print("[green]✅ عملیات تأیید شد[/green]\n")
        return True
    out.print("[red]❌ عملیات لغو شد[/red]\n")
    return False
