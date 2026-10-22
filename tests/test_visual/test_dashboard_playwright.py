"""Playwright (browser) visual tests for the metrics dashboard HTML export.

The dashboard is a Rich terminal renderable; these tests export it as styled
HTML and verify it inside a real Chromium browser, capturing screenshots as
artifacts.
"""

from pathlib import Path

import pytest
from rich.console import Console
from rich.terminal_theme import TerminalTheme

from liara_agent.cli.components import dashboard as dash
from liara_agent.models.metrics import AlertEvent, MetricDataPoint, MonitorSnapshot

playwright = pytest.importorskip("playwright")

SCREENSHOT_DIR = Path(__file__).parents[2] / "docs" / "demo" / "screenshots"

# GitHub-dark-ish palette so the export looks like a real dashboard, not paper.
DARK_THEME = TerminalTheme(
    background=(13, 17, 23),
    foreground=(201, 209, 217),
    normal=[
        (48, 54, 61),       # black
        (248, 81, 73),      # red
        (63, 185, 80),      # green
        (210, 153, 34),     # yellow
        (56, 139, 243),     # blue
        (188, 140, 255),    # magenta
        (57, 190, 193),     # cyan
        (230, 237, 243),    # white
    ],
    bright=[
        (110, 118, 129),
        (255, 123, 114),
        (63, 185, 80),
        (227, 179, 65),
        (116, 195, 252),
        (188, 140, 255),
        (110, 238, 238),
        (240, 246, 252),
    ],
)


def series(*values: float) -> list[MetricDataPoint]:
    return [MetricDataPoint(timestamp=1000 + i * 10, value=v) for i, v in enumerate(values)]


def build_critical_snapshot() -> MonitorSnapshot:
    return MonitorSnapshot(
        project_name="shop-api",
        status="running",
        is_deployed=True,
        is_healthy=False,
        plan_id="small",
        scale=1,
        cpu_percent=96.0,
        memory_percent=99.0,
        cpu_series=series(12, 18, 25, 22, 30, 45, 60, 72, 84, 91, 88, 93,
                          90, 87, 92, 95, 94, 96, 91, 88),
        memory_series=series(40, 42, 45, 51, 58, 63, 67, 70, 74, 79, 83, 86,
                             88, 90, 93, 95, 96, 97, 98, 99),
        net_rx_series=series(
            2_000_000, 2_500_000, 1_800_000, 900_000,
            400_000, 240_000, 120_000, 60_000, 30_000, 15_000,
        ),
        net_tx_series=series(
            500_000, 700_000, 650_000, 300_000,
            150_000, 90_000, 45_000, 24_000, 12_000, 6_000,
        ),
        alerts=[
            AlertEvent(
                rule_name="High CPU Usage",
                metric="cpu",
                current_value=96.0,
                threshold=95.0,
                severity="critical",
                message="مصرف CPU بحرانی (96.0% > 95.0%)",
                triggered_at="10:32:11",
            ),
            AlertEvent(
                rule_name="High Memory Usage",
                metric="memory",
                current_value=99.0,
                threshold=85.0,
                severity="critical",
                message="مصرف حافظه 99.0% — خطر OOM",
                triggered_at="10:32:11",
            ),
        ],
        issues=["کانتینر ۲ ساعت پیش OOMKilled شده است"],
        recommendations=[
            "ارتقای پلن (RAM بیشتر)",
            "لاگ‌های Memory Leak را در زمان Peak بررسی کنید",
        ],
        fetched_at="2026-10-22 10:32:11 UTC",
    )


def build_healthy_snapshot() -> MonitorSnapshot:
    return MonitorSnapshot(
        project_name="shop-api",
        status="running",
        is_deployed=True,
        is_healthy=True,
        plan_id="standard-plus",
        scale=2,
        cpu_percent=34.0,
        memory_percent=67.0,
        cpu_series=series(10, 14, 12, 18, 15, 20, 17, 22, 19, 24,
                          21, 26, 23, 28, 25, 30, 27, 32, 29, 34),
        memory_series=series(35, 37, 38, 41, 43, 44, 46, 48, 50, 52,
                             53, 55, 57, 58, 60, 61, 63, 64, 66, 67),
        net_rx_series=series(
            40_000_000, 45_000_000, 50_000_000, 48_000_000,
            52_000_000, 55_000_000, 58_000_000, 60_000_000,
            62_000_000, 65_000_000,
        ),
        net_tx_series=series(
            8_000_000, 9_500_000, 10_200_000, 11_000_000,
            12_400_000, 13_000_000, 14_100_000, 15_000_000,
            16_200_000, 17_500_000,
        ),
        alerts=[],
        issues=[],
        recommendations=[],
        fetched_at="2026-10-22 10:45:00 UTC",
    )


def export_dashboard_html(snapshot: MonitorSnapshot) -> str:
    console = Console(record=True, width=112)
    console.print(dash.build_dashboard(snapshot))
    return console.export_html(theme=DARK_THEME, clear=True)


def render_and_check(snapshot: MonitorSnapshot, shot_name: str, checks: list[str]) -> Path:
    html = export_dashboard_html(snapshot)
    html_path = SCREENSHOT_DIR / f"{shot_name}.html"
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")

    shot_path = SCREENSHOT_DIR / f"{shot_name}.png"
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 950})
        page.goto(html_path.resolve().as_uri())
        body = page.locator("body").inner_text()

        for needle in checks:
            assert needle in body, f"expected {needle!r} in rendered dashboard"

        page.screenshot(path=str(shot_path), full_page=True)
        browser.close()
    return shot_path


def test_critical_dashboard_in_browser():
    shot = render_and_check(
        build_critical_snapshot(),
        "dashboard_critical",
        checks=[
            "LIARA SRE AGENT",
            "STATUS: RUNNING",
            "PLAN: small",
            "96.0%",
            "99.0%",
            "ناسالم",
            "🚨",
            "خطر OOM",
            "هشدارها (3)",
        ],
    )
    assert shot.exists() and shot.stat().st_size > 10_000


def test_healthy_dashboard_in_browser():
    shot = render_and_check(
        build_healthy_snapshot(),
        "dashboard_healthy",
        checks=[
            "LIARA SRE AGENT",
            "STATUS: RUNNING",
            "PLAN: standard-plus",
            "34.0%",
            "67.0%",
            "سالم",
            "✅",
            "هشدارها (0)",
            "نیازی به اقدام فوری نیست",
        ],
    )
    assert shot.exists() and shot.stat().st_size > 10_000
