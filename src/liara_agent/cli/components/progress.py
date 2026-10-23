"""Progress bars and spinner components for CLI operations."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.status import Status

from liara_agent.cli.theme import console

# Deploy stages with labels (Persian)
DEPLOY_STAGES: list[tuple[str, str]] = [
    ("upload", "📦 آپلود سورس‌کد"),
    ("build", "🔨 ساخت ایمیج"),
    ("push", "📤 انتقال ایمیج"),
    ("start", "🚀 راه‌اندازی سرویس"),
    ("verify", "✅ بررسی سلامت"),
]


def deploy_progress() -> Progress:
    """Create a Rich progress bar configured for deployment stages.

    Usage:
        with deploy_progress() as progress:
            task = progress.add_task("دیپلوی", total=1.0)
            def cb(msg, p):
                progress.update(task, description=msg, completed=p)
            # ... perform stage work ...
            progress.update(task, completed=1.0)

    Returns:
        A configured Rich Progress instance.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40, complete_style="green", finished_style="bold green"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )


@contextmanager
def operation_spinner(message: str) -> Generator[Status, None, None]:
    """Context manager that shows a spinner while an operation runs.

    Args:
        message: The status message to display next to the spinner.

    Usage:
        with operation_spinner("در حال دریافت اطلاعات..."):
            await fetch_data()
    """
    with console.status(f"[bold cyan]{message}[/bold cyan]", spinner="dots") as status:
        yield status


def stage_progress(stages: list[tuple[str, str]], delay: float = 0.0) -> Progress:
    """Create a multi-stage progress bar.

    Args:
        stages: List of (stage_id, label) tuples.
        delay: Optional delay between stages for visual effect (seconds).

    Returns:
        A configured Rich Progress instance.
    """
    return Progress(
        SpinnerColumn("dots"),
        TextColumn("[bold]{task.description}[/bold]"),
        BarColumn(bar_width=30, complete_style="green", finished_style="bold green"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )


def simple_progress(description: str = "در حال پردازش...") -> Progress:
    """Create a simple indeterminate progress bar.

    Args:
        description: Text to display alongside the progress bar.

    Returns:
        A configured Rich Progress instance.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn(f"[cyan]{description}[/cyan]"),
        BarColumn(bar_width=40),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )
