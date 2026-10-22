"""MCP command — start Model Context Protocol server for Claude Desktop, Cursor, etc."""

from __future__ import annotations

import typer
from rich.console import Console

from liara_agent.mcp.server import run_mcp_server

mcp_app = typer.Typer(
    name="mcp",
    help="🔌 راه‌اندازی سرور پروتکل استاندارد هوش مصنوعی (Model Context Protocol - MCP)",
    no_args_is_help=False,
)
console = Console(stderr=True)


@mcp_app.callback(invoke_without_command=True)
def start_mcp() -> None:
    """اجرای سرور MCP روی ورودی/خروجی استاندارد (stdio) جهت اتصال به Claude Desktop, Cursor و سایر ایجنت‌ها."""
    # Stdio transport requires stdout/stdin to be clean JSON-RPC, so logs go to stderr
    run_mcp_server()
