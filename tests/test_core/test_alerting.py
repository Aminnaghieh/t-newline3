"""Tests for AlertEngine."""

from liara_agent.core.alerting import AlertEngine
from liara_agent.models.metrics import AlertRule


def test_alert_triggers_on_high_cpu():
    engine = AlertEngine()
    events = engine.check({"cpu": 85.0, "memory": 40.0})
    assert len(events) == 1
    assert events[0].metric == "cpu"
    assert events[0].severity == "warning"


def test_alert_triggers_on_critical_memory():
    engine = AlertEngine()
    events = engine.check({"cpu": 10.0, "memory": 96.0})
    assert any(e.metric == "memory" and e.severity == "critical" for e in events)


def test_no_alert_on_normal_metrics():
    engine = AlertEngine()
    events = engine.check({"cpu": 25.0, "memory": 30.0})
    assert len(events) == 0
