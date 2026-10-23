"""Alerting engine for proactive metric threshold checks."""

from __future__ import annotations

from datetime import UTC, datetime

from liara_agent.models.metrics import AlertEvent, AlertRule


class AlertEngine:
    """Client-side alerting engine evaluating metric streams."""

    def __init__(self, rules: list[AlertRule] | None = None) -> None:
        self.rules = rules or self._default_rules()

    def _default_rules(self) -> list[AlertRule]:
        return [
            AlertRule(
                name="High CPU Usage",
                metric="cpu",
                operator=">",
                threshold=80.0,
                severity="warning",
                message_template="مصرف پردازنده بالاست ({value}% > {threshold}%)",
            ),
            AlertRule(
                name="Critical CPU Usage",
                metric="cpu",
                operator=">",
                threshold=95.0,
                severity="critical",
                message_template="مصرف پردازنده در آستانه اشباع کامل است ({value}% > {threshold}%)",
            ),
            AlertRule(
                name="High Memory Usage",
                metric="memory",
                operator=">",
                threshold=85.0,
                severity="warning",
                message_template="مصرف رم بالاست ({value}% > {threshold}%) — خطر OOM",
            ),
            AlertRule(
                name="Critical Memory Usage",
                metric="memory",
                operator=">",
                threshold=95.0,
                severity="critical",
                message_template="مصرف رم بحرانی است ({value}% > {threshold}%) — امکان کرش سیستم",
            ),
        ]

    def add_rule(self, rule: AlertRule) -> None:
        """Add custom alert rule."""
        self.rules.append(rule)

    def check(self, current_metrics: dict[str, float]) -> list[AlertEvent]:
        """Check metrics map against configured rules."""
        events: list[AlertEvent] = []
        now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

        for rule in self.rules:
            if rule.metric not in current_metrics:
                continue

            val = current_metrics[rule.metric]
            triggered = False

            if rule.operator == ">" and val > rule.threshold or rule.operator == ">=" and val >= rule.threshold or rule.operator == "<" and val < rule.threshold or rule.operator == "<=" and val <= rule.threshold:
                triggered = True

            if triggered:
                msg = rule.message_template.format(value=f"{val:.1f}", threshold=rule.threshold)
                events.append(
                    AlertEvent(
                        rule_name=rule.name,
                        metric=rule.metric,
                        current_value=val,
                        threshold=rule.threshold,
                        severity=rule.severity,
                        message=msg,
                        triggered_at=now_str,
                    )
                )

        return events
