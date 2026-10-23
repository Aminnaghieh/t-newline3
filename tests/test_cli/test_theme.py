"""Tests for the central CLI theme module and error rendering."""

from rich.console import Console

from liara_agent.cli.theme import (
    BOX,
    console,
    print_next_steps,
    render_error,
)
from liara_agent.utils.errors import LiaraApiError, ProjectNotFoundError


def capture(render_fn, *args, **kwargs) -> str:
    sink = Console(record=True, width=120)
    render_fn(*args, con=sink, **kwargs)
    return sink.export_text()


def test_render_error_liara_api_error():
    exc = LiaraApiError(status_code=404, message="not found", endpoint="/v1/apps/x")
    text = capture(render_error, exc)
    assert "404" in text
    assert "not found" in text
    assert "💡" in text  # hint present


def test_render_error_project_not_found():
    exc = ProjectNotFoundError("my-app")
    text = capture(render_error, exc)
    assert "my-app" in text
    assert "service list" in text  # hint mentions the next command


def test_render_error_generic_exception():
    text = capture(render_error, RuntimeError("boom"))
    assert "boom" in text


def test_print_next_steps_renders_commands():
    text = capture(print_next_steps, [("liara-agent monitor x --live", "پایش زنده")])
    assert "liara-agent monitor x --live" in text
    assert "پایش زنده" in text


def test_shared_console_uses_rounded_box():
    # ROUNDED box uses ╭/╮/╰/╯ corner glyphs.
    assert BOX.top_left == "╭"
    assert BOX.bottom_right == "╯"


def test_console_is_theme_console():
    # The shared console must exist and be a rich Console.
    from rich.console import Console as RichConsole

    assert isinstance(console, RichConsole)
