"""Pydantic models for metrics and monitoring."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MetricDataPoint(BaseModel):
    """A single metric data point."""
    timestamp: float | int = Field(default=0)
    value: float = Field(default=0.0)


class MetricsReport(BaseModel):
    """Metrics report from Liara API."""
    model_config = ConfigDict(extra="allow")

    cpu: list[MetricDataPoint] = Field(default_factory=list)
    memory: list[MetricDataPoint] = Field(default_factory=list)
    network_rx: list[MetricDataPoint] = Field(default_factory=list)
    network_tx: list[MetricDataPoint] = Field(default_factory=list)


class LogEntry(BaseModel):
    """A single log entry."""
    model_config = ConfigDict(extra="allow")

    timestamp: str | None = Field(default=None)
    message: str = Field(default="")
    level: str = Field(default="info")
    source: str = Field(default="app")


class LogsResponse(BaseModel):
    """Response from GET /v1/projects/{name}/logs."""
    model_config = ConfigDict(extra="allow")

    logs: list[LogEntry] = Field(default_factory=list)



class HealthStatus(BaseModel):
    """Health status of a project."""
    is_healthy: bool = True
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    is_deployed: bool = False
    status: str = "unknown"
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class AlertRule(BaseModel):
    """Alert rule configuration."""
    name: str
    metric: str
    operator: str = ">"  # >, <, >=, <=
    threshold: float
    duration_seconds: int = 60
    severity: str = "warning"  # info, warning, critical
    message_template: str = ""


class AlertEvent(BaseModel):
    """Triggered alert event."""
    rule_name: str
    metric: str
    current_value: float
    threshold: float
    severity: str
    message: str
    triggered_at: str
