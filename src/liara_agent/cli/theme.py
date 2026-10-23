"""Central UI theme for the Liara SRE Agent terminal experience.

A single source of truth for the shared :class:`rich.Console`, the brand
palette, risk/status styling, error rendering and "next steps" hints — so
every command and component renders with the same look & feel.
"""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape as escape_markup
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

from liara_agent import __version__
from liara_agent.utils.errors import LiaraAgentError

# ─── Brand palette ───────────────────────────────────────────
PRIMARY = "cyan"
ACCENT = "magenta"
SUCCESS = "green"
WARNING = "yellow"
ERROR = "red"
MUTED = "dim"

# Named styles registered on the shared console.
RICH_THEME = Theme({
    "brand": f"bold {PRIMARY}",
    "accent": f"bold {ACCENT}",
    "ok": SUCCESS,
    "warn": WARNING,
    "err": f"bold {ERROR}",
    "muted": MUTED,
})

# Consistent rounded box style for all panels.
from rich import box  # noqa: E402  (placed after imports for readability)

BOX = box.ROUNDED

# Risk level → border style mapping (shared with approval components).
RISK_BORDER = {
    "low": SUCCESS,
    "medium": WARNING,
    "high": ERROR,
    "critical": f"bold {ERROR}",
}

# ─── Shared console ──────────────────────────────────────────
console = Console(theme=RICH_THEME, legacy_windows=False)


def set_no_color() -> None:
    """Disable colors globally (``--no-color`` flag)."""
    console.no_color = True
    console._color_system = None  # type: ignore[attr-defined]


# ─── Error rendering ─────────────────────────────────────────
def render_error(exc: Exception, con: Console | None = None) -> None:
    """Render an error with its message, hint and next-step suggestion."""
    out = con or console
    out.print()
    if isinstance(exc, LiaraAgentError):
        out.print(
            Panel(
                f"[bold red]❌ {escape_markup(str(exc.message))}[/bold red]"
                + (f"\n\n[dim]💡 {escape_markup(exc.hint)}[/dim]" if exc.hint else ""),
                title="⚠️ خطا",
                border_style=ERROR,
                box=BOX,
                padding=(1, 2),
            )
        )
    else:
        out.print(
            Panel(
                f"[bold red]❌ {escape_markup(str(exc))}[/bold red]",
                title="⚠️ خطای غیرمنتظره",
                border_style=ERROR,
                box=BOX,
                padding=(1, 2),
            )
        )


# ─── Next-step hints ─────────────────────────────────────────
def print_next_steps(hints: list[tuple[str, str]], con: Console | None = None) -> None:
    """Print a compact 'قدم‌های بعدی' block.

    Args:
        hints: list of ``(command, description)`` tuples.
    """
    out = con or console
    body = Text()
    for cmd, desc in hints:
        body.append("  ", style="dim")
        body.append(f"$ {cmd}", style=f"bold {PRIMARY}")
        body.append(f"  →  {desc}\n", style="white")
    out.print(
        Panel(
            body,
            title="🧭 قدم‌های بعدی",
            border_style=PRIMARY,
            box=BOX,
            padding=(1, 2),
        )
    )


# ─── Banner ──────────────────────────────────────────────────
_LOGO = r"""
██╗     ██╗ █████╗ ██████╗  █████╗
██║     ██║██╔══██╗██╔══██╗██╔══██╗
██║     ██║███████║██████╔╝███████║
██║     ██║██╔══██║██╔══██╗██╔══██║
███████╗██║██║  ██║██║  ██║██║  ██║
╚══════╝╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
"""


def render_banner(con: Console | None = None) -> None:
    """Render the ASCII-art welcome banner with version + commands."""
    out = con or console
    logo = Text(_LOGO, style=f"bold {PRIMARY}")
    meta = Text()
    meta.append(f"  🛡️ Liara SRE Agent v{__version__}\n", style=f"bold {PRIMARY}")
    meta.append("  دستیار هوشمند استقرار، پایش و عیب‌یابی روی Liara PaaS\n\n", style="white")
    meta.append("  init", style=f"bold {SUCCESS}")
    meta.append("      تحلیل و اولین دیپلوی\n", style="dim")
    meta.append("  deploy", style=f"bold {SUCCESS}")
    meta.append("    انتشار نسخه جدید\n", style="dim")
    meta.append("  monitor", style=f"bold {SUCCESS}")
    meta.append("   داشبورد پایش زنده\n", style="dim")
    meta.append("  debug", style=f"bold {SUCCESS}")
    meta.append("     عیب‌یابی هوشمند (RCA)\n", style="dim")
    meta.append("  service", style=f"bold {SUCCESS}")
    meta.append("   مدیریت سرویس‌ها\n", style="dim")
    meta.append("  logs", style=f"bold {SUCCESS}")
    meta.append("     مشاهده و استریم لاگ‌ها\n", style="dim")
    meta.append("  mcp", style=f"bold {SUCCESS}")
    meta.append("      سرور MCP برای ایجنت‌های AI\n", style="dim")
    meta.append("  config", style=f"bold {SUCCESS}")
    meta.append("    تنظیم توکن‌ها و کلیدها", style="dim")

    out.print()
    out.print(logo)
    out.print(meta)
    out.print()


def onboarding_hint(con: Console | None = None) -> None:
    """Hint shown when no API token is configured (first-run detection)."""
    out = con or console
    out.print(
        Panel(
            "[bold yellow]👋 به Liara SRE Agent خوش آمدید![/bold yellow]\n\n"
            "هنوز توکن API لیارا تنظیم نشده است. برای شروع:\n\n"
            f"  [bold {PRIMARY}]1.[/bold {PRIMARY}] توکن را از "
            "[link=https://console.liara.ir]console.liara.ir[/link] بگیرید\n"
            f"  [bold {PRIMARY}]2.[/bold {PRIMARY}] اجرا کنید: "
            "[bold green]liara-agent config set-token[/bold green]",
            title="🚀 شروع کار",
            border_style=WARNING,
            box=BOX,
            padding=(1, 2),
        )
    )
