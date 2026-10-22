"""CLI entry point for liara-agent."""

from __future__ import annotations

import os
import sys

# Windows UTF-8 console output fix
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from liara_agent.cli.app import app


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
