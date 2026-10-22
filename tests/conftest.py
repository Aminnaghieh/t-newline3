"""Pytest fixtures and test setup for liara-agent."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator

import pytest

from liara_agent.core.analyzer import ProjectAnalysis


@pytest.fixture
def temp_project_dir() -> Generator[Path, None, None]:
    """Create a temporary project directory for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def mock_nodejs_project(temp_project_dir: Path) -> Path:
    """Create a mock Node.js project."""
    pkg_json = temp_project_dir / "package.json"
    pkg_json.write_text(
        '{"name": "test-app", "scripts": {"start": "node index.js"}, "dependencies": {"express": "^4.18.0"}}',
        encoding="utf-8",
    )
    index_js = temp_project_dir / "index.js"
    index_js.write_text("const port = process.env.PORT || 3000;", encoding="utf-8")
    return temp_project_dir


@pytest.fixture
def mock_python_project(temp_project_dir: Path) -> Path:
    """Create a mock Python project."""
    reqs = temp_project_dir / "requirements.txt"
    reqs.write_text("fastapi==0.100.0\nuvicorn==0.23.0\n", encoding="utf-8")
    app_py = temp_project_dir / "main.py"
    app_py.write_text(
        "import os\nfrom fastapi import FastAPI\napp = FastAPI()\nport = int(os.environ.get('PORT', 8000))\n",
        encoding="utf-8",
    )
    return temp_project_dir


@pytest.fixture
def sample_analysis() -> ProjectAnalysis:
    """Sample ProjectAnalysis fixture."""
    return ProjectAnalysis(
        platform="nodejs",
        framework="express",
        port=3000,
        start_cmd="npm start",
        build_cmd=None,
        dependencies=["express", "cors", "dotenv"],
        env_vars_needed=["PORT", "DATABASE_URL"],
        has_dockerfile=False,
        has_tests=True,
        project_size_mb=4.5,
        recommended_plan="micro",
        analysis_notes=["Express framework detected"],
    )
