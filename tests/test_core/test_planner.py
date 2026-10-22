"""Tests for PlanRecommender."""

import pytest
from liara_agent.core.analyzer import ProjectAnalysis
from liara_agent.core.planner import PlanRecommender


def test_recommend_micro_for_small_project(sample_analysis: ProjectAnalysis):
    planner = PlanRecommender()
    rec = planner.recommend(sample_analysis)
    assert rec.recommended_plan in ("micro", "small")
    assert rec.reason != ""


def test_recommend_small_for_heavy_framework():
    analysis = ProjectAnalysis(
        platform="nodejs",
        framework="next",
        port=3000,
        start_cmd="npm start",
        build_cmd="npm run build",
        dependencies=["next", "react", "react-dom"],
        env_vars_needed=[],
        has_dockerfile=False,
        has_tests=False,
        project_size_mb=25.0,
        recommended_plan="small",
        analysis_notes=[],
    )
    planner = PlanRecommender()
    rec = planner.recommend(analysis)
    assert rec.recommended_plan in ("small", "medium")


def test_compare_plans():
    planner = PlanRecommender()
    diff = planner.compare_plans("micro", "small")
    assert diff["is_upgrade"] is True
    assert diff["diff"]["ram_gb"] > 0
