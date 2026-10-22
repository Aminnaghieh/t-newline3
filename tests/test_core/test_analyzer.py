"""Tests for ProjectAnalyzer."""

from pathlib import Path
import pytest
from liara_agent.core.analyzer import ProjectAnalyzer


def test_detect_nodejs(mock_nodejs_project: Path):
    analyzer = ProjectAnalyzer(mock_nodejs_project)
    analysis = analyzer.analyze()
    assert analysis.platform == "nodejs"
    assert analysis.port == 3000
    assert "express" in analysis.dependencies


def test_detect_python(mock_python_project: Path):
    analyzer = ProjectAnalyzer(mock_python_project)
    analysis = analyzer.analyze()
    assert analysis.platform == "python"
    assert analysis.port == 8000
    assert any("fastapi" in d for d in analysis.dependencies)
