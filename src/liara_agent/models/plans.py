"""Plan catalog models and recommendation logic."""

from __future__ import annotations

from pydantic import BaseModel, Field

from liara_agent.utils.constants import PLAN_CATALOG


class PlanInfo(BaseModel):
    """Liara plan information."""
    id: str
    label: str
    cpu: float
    ram_gb: float
    disk_gb: float
    bandwidth_gb: int
    description: str


class PlanRecommendation(BaseModel):
    """AI-powered plan recommendation."""
    recommended_plan: str
    reason: str
    alternatives: list[str] = Field(default_factory=list)
    estimated_requirements: dict = Field(default_factory=dict)


def get_all_plans() -> list[PlanInfo]:
    """Get all available plans."""
    return [
        PlanInfo(id=plan_id, **info)
        for plan_id, info in PLAN_CATALOG.items()
    ]


def get_plan_by_id(plan_id: str) -> PlanInfo | None:
    """Get a specific plan by ID."""
    info = PLAN_CATALOG.get(plan_id)
    if info is None:
        return None
    return PlanInfo(id=plan_id, **info)
