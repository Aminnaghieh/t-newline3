"""Tests for the Rich-based metrics dashboard component."""

from rich.console import Console

from liara_agent.cli.components import dashboard as dash
from liara_agent.models.metrics import AlertEvent, MetricDataPoint, MonitorSnapshot


def make_snapshot(**overrides) -> MonitorSnapshot:
    base = {
        "project_name": "my-app",
        "status": "running",
        "is_deployed": True,
        "is_healthy": True,
        "plan_id": "small",
        "scale": 1,
        "cpu_percent": 30.0,
        "memory_percent": 40.0,
        "fetched_at": "2026-10-22 10:00:00 UTC",
    }
    base.update(overrides)
    return MonitorSnapshot(**base)


def series(*values: float) -> list[MetricDataPoint]:
    return [MetricDataPoint(timestamp=i, value=v) for i, v in enumerate(values)]


def make_alert(severity: str = "warning", message: str = "مصرف منابع بالاست") -> AlertEvent:
    return AlertEvent(
        rule_name="High CPU Usage",
        metric="cpu",
        current_value=90.0,
        threshold=80.0,
        severity=severity,
        message=message,
        triggered_at="now",
    )


def capture(renderable, width: int = 130) -> str:
    console = Console(record=True, width=width)
    console.print(renderable)
    return console.export_text()


# ─── Severity / color classification ─────────────────────────

def test_severity_for_boundaries():
    assert dash.severity_for(65.0, 70.0, 85.0) == "ok"
    assert dash.severity_for(69.9, 70.0, 85.0) == "ok"
    assert dash.severity_for(70.0, 70.0, 85.0) == "warn"
    assert dash.severity_for(84.9, 70.0, 85.0) == "warn"
    assert dash.severity_for(85.0, 70.0, 85.0) == "crit"


def test_color_for_mapping():
    assert dash.color_for(10.0, 70.0, 85.0) == "green"
    assert dash.color_for(72.0, 70.0, 85.0) == "yellow"
    assert dash.color_for(96.0, 70.0, 85.0) == "bold red"


# ─── Progress bar ────────────────────────────────────────────

def test_progress_bar_zero_is_empty():
    bar = dash.progress_bar(0.0)
    assert "0.0%" in bar
    assert "█" not in bar
    assert bar.count("░") == dash.BAR_WIDTH


def test_progress_bar_halfway():
    bar = dash.progress_bar(50.0)
    assert bar.count("█") == dash.BAR_WIDTH // 2
    assert "50.0%" in bar


def test_progress_bar_clamps_out_of_range():
    assert "100.0%" in dash.progress_bar(150.0)
    assert dash.progress_bar(150.0).count("█") == dash.BAR_WIDTH
    assert "0.0%" in dash.progress_bar(-5.0)


# ─── Sparkline ───────────────────────────────────────────────

def test_sparkline_empty_series_renders_dash():
    assert dash.sparkline([]).plain == "—"


def test_sparkline_length_and_blocks():
    spark = dash.sparkline(series(*range(10)), width=8)
    assert len(spark.plain) == 8
    assert all(c in dash.SPARK_BLOCKS for c in spark.plain)


def test_sparkline_fixed_scale_top_value():
    spark = dash.sparkline(series(50.0, 100.0), fixed_scale=100.0)
    assert spark.plain[-1] == "█"  # 100 at scale 100 -> top block


def test_sparkline_handles_all_zero_series():
    spark = dash.sparkline(series(0.0, 0.0, 0.0))
    assert spark.plain == "▁▁▁"


# ─── Trend arrow ─────────────────────────────────────────────

def test_trend_arrow_rising():
    assert dash.trend_arrow(series(*[i * 10 for i in range(20)])).plain.startswith("↑")


def test_trend_arrow_falling():
    assert dash.trend_arrow(series(*[200 - i * 10 for i in range(20)])).plain.startswith("↓")


def test_trend_arrow_stable():
    assert "پایدار" in dash.trend_arrow(series(*[50.0] * 20)).plain


def test_trend_arrow_single_point():
    assert dash.trend_arrow(series(50.0)) == dash.Text("→", style="dim")


# ─── Byte formatting ─────────────────────────────────────────

def test_format_bytes_boundaries():
    assert dash.format_bytes(1023) == "1023.0 B"
    assert dash.format_bytes(2048) == "2.0 KB"
    assert dash.format_bytes(1024 * 1024 * 1024 * 1.5) == "1.5 GB"


# ─── Composition ─────────────────────────────────────────────

def test_build_dashboard_renders_full_composite():
    snap = make_snapshot(
        cpu_percent=90.0,
        cpu_series=series(20.0, 30.0, 90.0),
        memory_series=series(40.0, 41.0, 42.0),
        net_rx_series=series(1000.0, 2000.0),
        net_tx_series=series(500.0),
    )
    text = capture(dash.build_dashboard(snap))

    assert "my-app" in text
    assert "STATUS: RUNNING" in text
    assert "DEPLOYED ✓" in text
    assert "PLAN: small" in text
    assert "SCALE: 1" in text
    assert "CPU" in text
    assert "RAM" in text
    assert "NET" in text
    assert "90.0%" in text
    assert "سالم" in text
    assert "2026-10-22 10:00:00 UTC" in text


def test_build_dashboard_warning_alert():
    snap = make_snapshot(alerts=[make_alert(severity="warning")], is_healthy=False)
    text = capture(dash.build_dashboard(snap))
    assert "⚠️" in text
    assert "هشدارها (1)" in text


def test_build_dashboard_critical_alert():
    snap = make_snapshot(alerts=[make_alert(severity="critical")], is_healthy=False)
    text = capture(dash.build_dashboard(snap))
    assert "🚨" in text
    assert "ناسالم" in text


def test_build_dashboard_issues_rendered():
    snap = make_snapshot(issues=["عدم دریافت اطلاعات پروژه: timeout"])
    text = capture(dash.build_dashboard(snap))
    assert "❗" in text
    assert "timeout" in text
    assert "هشدارها (1)" in text


def test_build_dashboard_recommendations():
    snap = make_snapshot(recommendations=["ارتقای پلن به CPU بیشتر"])
    text = capture(dash.build_dashboard(snap))
    assert "💡" in text
    assert "ارتقای پلن" in text


def test_build_dashboard_healthy_recommendations_empty():
    text = capture(dash.build_dashboard(make_snapshot()))
    assert "نیازی به اقدام فوری نیست" in text


def test_build_dashboard_handles_missing_series():
    snap = make_snapshot(cpu_percent=0.0, memory_percent=0.0)
    text = capture(dash.build_dashboard(snap))
    assert "—" in text
    assert "0.0%" in text


# ─── Console-facing API ──────────────────────────────────────

def test_show_dashboard_prints_snapshot():
    console = Console(record=True, width=130)
    dash.show_dashboard(make_snapshot(), console=console)
    assert "my-app" in console.export_text()


def test_show_live_dashboard_exits_on_interrupt():
    console = Console(record=True, width=130)

    def fetch():
        raise KeyboardInterrupt

    dash.show_live_dashboard(
        "my-app", fetch_snapshot_fn=fetch, refresh_interval=0, console=console
    )
    assert "متوقف" in console.export_text()


def test_show_live_dashboard_survives_fetch_errors():
    console = Console(record=True, width=130)
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("boom")
        raise KeyboardInterrupt  # second call exits cleanly

    dash.show_live_dashboard(
        "my-app", fetch_snapshot_fn=fetch, refresh_interval=0, console=console
    )
    text = console.export_text()
    assert "خطا در دریافت متریک‌ها" in text  # error panel was rendered
    assert "متوقف" in text  # and the loop kept running until the interrupt
