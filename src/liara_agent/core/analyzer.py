"""Project analyzer — detects language, framework, and configuration."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pydantic import BaseModel, Field

from liara_agent.utils.constants import PLAN_CATALOG, PLATFORM_DETECTION
from liara_agent.utils.errors import AnalysisError

# ─── Models ───────────────────────────────────────────────────


class ProjectAnalysis(BaseModel):
    """Result of a full project analysis."""

    platform: str
    framework: str | None = None
    port: int
    start_cmd: str
    build_cmd: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    env_vars_needed: list[str] = Field(default_factory=list)
    has_dockerfile: bool = False
    has_tests: bool = False
    project_size_mb: float = 0.0
    recommended_plan: str = "micro"
    analysis_notes: list[str] = Field(default_factory=list)


# ─── Analyzer ─────────────────────────────────────────────────

# Frameworks detectable per platform
_FRAMEWORK_MARKERS: dict[str, dict[str, list[str]]] = {
    "nodejs": {
        "next": ["next.config.js", "next.config.mjs", "next.config.ts"],
        "nuxt": ["nuxt.config.js", "nuxt.config.ts"],
        "nest": ["nest-cli.json"],
        "express": [],  # detected via package.json dependencies
        "fastify": [],
    },
    "python": {
        "django": ["manage.py"],
        "flask": [],
        "fastapi": [],
        "streamlit": [],
    },
    "go": {
        "gin": [],
        "fiber": [],
        "echo": [],
    },
    "php": {
        "laravel": ["artisan"],
    },
    "ruby": {
        "rails": ["Rakefile", "config/routes.rb"],
    },
    "java": {
        "spring": [],
    },
}

# Common env-var patterns to search for in source code
_ENV_VAR_PATTERN = re.compile(
    r"""(?:"""
    r"""os\.environ\.get\(['\"](\w+)['\"]"""       # Python os.environ.get("X")
    r"""|os\.environ\[['\"](\w+)['\"]"""           # Python os.environ["X"]
    r"""|os\.getenv\(['\"](\w+)['\"]"""            # Python os.getenv("X")
    r"""|process\.env\.(\w+)"""                     # Node.js process.env.X
    r"""|os\.Getenv\(['\"](\w+)['\"]"""            # Go os.Getenv("X")
    r""")""",
)

# Source file extensions to scan for env vars
_SCANNABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rb", ".php",
    ".java", ".rs", ".mjs", ".cjs",
}

# Directories excluded from scanning
_EXCLUDED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "vendor", "target",
}


class ProjectAnalyzer:
    """Analyzes a project directory to detect language, framework, and configuration."""

    def __init__(self, project_path: Path) -> None:
        if not project_path.is_dir():
            raise AnalysisError(f"مسیر '{project_path}' یک دایرکتوری معتبر نیست")
        self.path = project_path

    # ── public API ────────────────────────────────────────────

    def analyze(self) -> ProjectAnalysis:
        """Run full project analysis and return a consolidated report."""
        notes: list[str] = []

        platform = self.detect_platform()
        if platform == "unknown":
            notes.append("پلتفرم به‌طور خودکار تشخیص داده نشد — لطفاً دستی مشخص کنید")

        framework = self.detect_framework()
        port = self.detect_port()
        start_cmd = self.detect_start_command()
        build_cmd = self.detect_build_command()
        deps = self.get_dependencies()
        env_vars = self.get_env_vars()
        has_dockerfile = (self.path / "Dockerfile").exists()
        has_tests = self._has_tests()
        size_mb = self._calculate_size_mb()
        resources = self.estimate_resource_needs()
        recommended = resources.get("recommended_plan", "micro")

        if has_dockerfile and platform != "docker":
            notes.append("Dockerfile موجود است — امکان دیپلوی با پلتفرم docker نیز وجود دارد")
        if not env_vars:
            notes.append("هیچ متغیر محیطی در سورس‌کد شناسایی نشد")
        if framework:
            notes.append(f"فریم‌ورک '{framework}' تشخیص داده شد")

        return ProjectAnalysis(
            platform=platform,
            framework=framework,
            port=port,
            start_cmd=start_cmd,
            build_cmd=build_cmd,
            dependencies=deps,
            env_vars_needed=env_vars,
            has_dockerfile=has_dockerfile,
            has_tests=has_tests,
            project_size_mb=round(size_mb, 2),
            recommended_plan=recommended,
            analysis_notes=notes,
        )

    # ── detection helpers ─────────────────────────────────────

    def detect_platform(self) -> str:
        """Detect the primary platform/language using marker files."""
        for platform, info in PLATFORM_DETECTION.items():
            marker_files: list[str] = info["files"]
            for pattern in marker_files:
                # Support glob patterns (e.g. *.csproj)
                if "*" in pattern or "?" in pattern:
                    if any(self.path.glob(pattern)):
                        return platform
                elif (self.path / pattern).exists():
                    return platform
        return "unknown"

    def detect_framework(self) -> str | None:
        """Detect the framework within the detected platform."""
        platform = self.detect_platform()
        markers = _FRAMEWORK_MARKERS.get(platform, {})

        # 1) Check for marker files specific to each framework
        for framework, files in markers.items():
            for f in files:
                if (self.path / f).exists():
                    return framework

        # 2) Check dependency manifests
        if platform == "nodejs":
            return self._detect_node_framework()
        if platform == "python":
            return self._detect_python_framework()
        if platform == "go":
            return self._detect_go_framework()
        if platform == "java":
            return self._detect_java_framework()

        return None

    def detect_port(self) -> int:
        """Detect the application port from config files or fall back to default."""
        # Check liara.json (Liara's own config file)
        liara_json = self.path / "liara.json"
        if liara_json.exists():
            try:
                data = json.loads(liara_json.read_text(encoding="utf-8"))
                if "port" in data:
                    return int(data["port"])
            except (json.JSONDecodeError, ValueError):
                pass

        # Check .env / .env.example for PORT variable
        for env_file in (".env", ".env.example", ".env.sample"):
            env_path = self.path / env_file
            if env_path.exists():
                try:
                    for line in env_path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line.startswith("PORT="):
                            return int(line.split("=", 1)[1].strip().strip("\"'"))
                except (ValueError, UnicodeDecodeError):
                    pass

        # Check package.json "config.port" or "scripts.start" for --port
        pkg = self.path / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8"))
                if "config" in data and "port" in data["config"]:
                    return int(data["config"]["port"])
                start_script = data.get("scripts", {}).get("start", "")
                port_match = re.search(r"--port[= ](\d+)", start_script)
                if port_match:
                    return int(port_match.group(1))
                port_match = re.search(r"-p[= ](\d+)", start_script)
                if port_match:
                    return int(port_match.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

        # Fall back to platform default
        platform = self.detect_platform()
        info = PLATFORM_DETECTION.get(platform, {})
        default_port = info.get("default_port")
        return int(default_port) if default_port is not None else 3000

    def detect_start_command(self) -> str:
        """Detect the start command from project configuration."""
        # Check liara.json
        liara_json = self.path / "liara.json"
        if liara_json.exists():
            try:
                data = json.loads(liara_json.read_text(encoding="utf-8"))
                if "start" in data:
                    return str(data["start"])
            except (json.JSONDecodeError, ValueError):
                pass

        # Check Procfile
        procfile = self.path / "Procfile"
        if procfile.exists():
            try:
                for line in procfile.read_text(encoding="utf-8").splitlines():
                    if line.startswith("web:"):
                        return line.split(":", 1)[1].strip()
            except UnicodeDecodeError:
                pass

        # Check package.json scripts.start
        pkg = self.path / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8"))
                start = data.get("scripts", {}).get("start")
                if start:
                    return str(start)
            except (json.JSONDecodeError, ValueError):
                pass

        # Framework-specific defaults
        framework = self.detect_framework()
        if framework == "django":
            return "python manage.py runserver 0.0.0.0:8000"
        if framework == "flask":
            return "flask run --host=0.0.0.0"
        if framework == "fastapi":
            return "uvicorn app.main:app --host 0.0.0.0 --port 8000"
        if framework == "streamlit":
            return "streamlit run app.py --server.port 8000"
        if framework == "next":
            return "npm run start"

        # Platform default
        platform = self.detect_platform()
        info = PLATFORM_DETECTION.get(platform, {})
        cmd = info.get("start_cmd")
        return str(cmd) if cmd else "echo 'no start command detected'"

    def detect_build_command(self) -> str | None:
        """Detect the build command if the project requires a build step."""
        # Check liara.json
        liara_json = self.path / "liara.json"
        if liara_json.exists():
            try:
                data = json.loads(liara_json.read_text(encoding="utf-8"))
                if "build" in data:
                    return str(data["build"])
            except (json.JSONDecodeError, ValueError):
                pass

        # Check package.json scripts.build
        pkg = self.path / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8"))
                build = data.get("scripts", {}).get("build")
                if build:
                    return str(build)
            except (json.JSONDecodeError, ValueError):
                pass

        platform = self.detect_platform()
        if platform == "go":
            return "go build -o app ."
        if platform == "rust":
            return "cargo build --release"
        if platform == "java":
            if (self.path / "pom.xml").exists():
                return "mvn package -DskipTests"
            if (self.path / "build.gradle").exists() or (self.path / "build.gradle.kts").exists():
                return "./gradlew build"
        if platform == "dotnet":
            return "dotnet publish -c Release"

        return None

    def get_dependencies(self) -> list[str]:
        """Get project dependencies from the manifest file."""
        platform = self.detect_platform()

        if platform == "nodejs":
            return self._get_node_dependencies()
        if platform == "python":
            return self._get_python_dependencies()
        if platform == "go":
            return self._get_go_dependencies()
        if platform == "ruby":
            return self._get_ruby_dependencies()
        if platform == "php":
            return self._get_php_dependencies()

        return []

    def estimate_resource_needs(self) -> dict:
        """Estimate CPU/RAM/Disk needs based on project size, type, and framework."""
        size_mb = self._calculate_size_mb()
        platform = self.detect_platform()
        framework = self.detect_framework()
        deps = self.get_dependencies()

        # Base resource requirements by platform
        cpu_weight = {
            "go": 0.4, "rust": 0.4, "static": 0.1,
            "nodejs": 0.6, "python": 0.7, "java": 1.0,
            "dotnet": 0.8, "php": 0.5, "ruby": 0.6,
        }.get(platform, 0.5)

        ram_weight = {
            "go": 0.3, "rust": 0.3, "static": 0.1,
            "nodejs": 0.6, "python": 0.6, "java": 1.0,
            "dotnet": 0.7, "php": 0.4, "ruby": 0.5,
        }.get(platform, 0.5)

        # Framework multipliers
        framework_multiplier = {
            "next": 1.5, "nuxt": 1.5, "nest": 1.3,
            "django": 1.3, "spring": 1.5,
        }.get(framework or "", 1.0)

        # Dependency count impact
        dep_factor = 1.0 + min(len(deps) / 100.0, 0.5)

        estimated_cpu = round(cpu_weight * framework_multiplier * dep_factor, 2)
        estimated_ram_gb = round(ram_weight * framework_multiplier * dep_factor, 2)
        estimated_disk_gb = max(round(size_mb / 1024 * 2, 2), 0.5)

        # Choose the smallest plan that fits
        recommended_plan = "micro"
        for plan_id, info in PLAN_CATALOG.items():
            if (
                info["cpu"] >= estimated_cpu
                and info["ram_gb"] >= estimated_ram_gb
                and info["disk_gb"] >= estimated_disk_gb
            ):
                recommended_plan = plan_id
                break

        return {
            "estimated_cpu": estimated_cpu,
            "estimated_ram_gb": estimated_ram_gb,
            "estimated_disk_gb": estimated_disk_gb,
            "recommended_plan": recommended_plan,
        }

    def get_env_vars(self) -> list[str]:
        """Detect required environment variables from source code."""
        env_vars: set[str] = set()
        # Built-in or common vars that shouldn't be reported as project-specific
        common_vars = {
            "PATH", "HOME", "USER", "SHELL", "NODE_ENV", "PYTHONPATH",
            "LANG", "TERM", "PWD", "HOSTNAME", "PORT",
        }

        for root, dirs, files in os.walk(self.path):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in _EXCLUDED_DIRS]
            for fname in files:
                fpath = Path(root) / fname
                if fpath.suffix not in _SCANNABLE_EXTENSIONS:
                    continue
                try:
                    content = fpath.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for match in _ENV_VAR_PATTERN.finditer(content):
                    # The pattern has multiple groups; pick the first non-None
                    var = next((g for g in match.groups() if g is not None), None)
                    if var and var not in common_vars:
                        env_vars.add(var)

        # Also pull from .env.example
        env_example = self.path / ".env.example"
        if env_example.exists():
            try:
                for line in env_example.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key = line.split("=", 1)[0].strip()
                        if key and key not in common_vars:
                            env_vars.add(key)
            except UnicodeDecodeError:
                pass

        return sorted(env_vars)

    # ── private helpers ───────────────────────────────────────

    def _read_json(self, filename: str) -> dict | None:
        """Safely read and parse a JSON file."""
        path = self.path / filename
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _has_tests(self) -> bool:
        """Check if the project has a test directory or test files."""
        test_dirs = ["test", "tests", "__tests__", "spec", "specs", "test_"]
        for d in test_dirs:
            if (self.path / d).is_dir():
                return True
        # Check for test files at top level
        test_patterns = ["test_*.py", "*_test.py", "*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts"]
        for pat in test_patterns:
            if any(self.path.rglob(pat)):
                return True
        return False

    def _calculate_size_mb(self) -> float:
        """Calculate total project size in MB, excluding excluded dirs."""
        total = 0
        for root, dirs, files in os.walk(self.path):
            dirs[:] = [d for d in dirs if d not in _EXCLUDED_DIRS]
            for fname in files:
                try:
                    total += (Path(root) / fname).stat().st_size
                except OSError:
                    pass
        return total / (1024 * 1024)

    # ── Node.js ───────────────────────────────────────────────

    def _detect_node_framework(self) -> str | None:
        """Detect Node.js framework from package.json dependencies."""
        data = self._read_json("package.json")
        if not data:
            return None
        all_deps = {
            *data.get("dependencies", {}).keys(),
            *data.get("devDependencies", {}).keys(),
        }
        # Order matters — most specific first
        if "next" in all_deps:
            return "next"
        if "@nestjs/core" in all_deps:
            return "nest"
        if "nuxt" in all_deps or "nuxt3" in all_deps:
            return "nuxt"
        if "fastify" in all_deps:
            return "fastify"
        if "express" in all_deps:
            return "express"
        return None

    def _get_node_dependencies(self) -> list[str]:
        data = self._read_json("package.json")
        if not data:
            return []
        return sorted(data.get("dependencies", {}).keys())

    # ── Python ────────────────────────────────────────────────

    def _detect_python_framework(self) -> str | None:
        """Detect Python framework from requirements or pyproject."""
        deps = {d.lower() for d in self._get_python_dependencies()}
        if "django" in deps:
            return "django"
        if "fastapi" in deps:
            return "fastapi"
        if "flask" in deps:
            return "flask"
        if "streamlit" in deps:
            return "streamlit"
        return None

    def _get_python_dependencies(self) -> list[str]:
        deps: list[str] = []
        # requirements.txt
        req = self.path / "requirements.txt"
        if req.exists():
            try:
                for line in req.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith(("#", "-")):
                        # Strip version specifiers
                        pkg = re.split(r"[><=!~;@\[]", line)[0].strip()
                        if pkg:
                            deps.append(pkg)
            except UnicodeDecodeError:
                pass
            return sorted(set(deps))

        # pyproject.toml — simple regex parse (avoid toml dependency)
        pyproject = self.path / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text(encoding="utf-8")
                in_deps = False
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("dependencies") and "=" in stripped:
                        in_deps = True
                        continue
                    if in_deps:
                        if stripped.startswith("]"):
                            break
                        match = re.match(r'["\']([a-zA-Z0-9_-]+)', stripped)
                        if match:
                            deps.append(match.group(1))
            except UnicodeDecodeError:
                pass
            return sorted(set(deps))

        # Pipfile — simple regex
        pipfile = self.path / "Pipfile"
        if pipfile.exists():
            try:
                content = pipfile.read_text(encoding="utf-8")
                in_packages = False
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped == "[packages]":
                        in_packages = True
                        continue
                    if stripped.startswith("[") and in_packages:
                        break
                    if in_packages and "=" in stripped:
                        pkg = stripped.split("=")[0].strip().strip('"').strip("'")
                        if pkg:
                            deps.append(pkg)
            except UnicodeDecodeError:
                pass

        return sorted(set(deps))

    # ── Go ────────────────────────────────────────────────────

    def _detect_go_framework(self) -> str | None:
        go_mod = self.path / "go.mod"
        if not go_mod.exists():
            return None
        try:
            content = go_mod.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return None
        if "github.com/gin-gonic/gin" in content:
            return "gin"
        if "github.com/gofiber/fiber" in content:
            return "fiber"
        if "github.com/labstack/echo" in content:
            return "echo"
        return None

    def _get_go_dependencies(self) -> list[str]:
        go_mod = self.path / "go.mod"
        if not go_mod.exists():
            return []
        deps: list[str] = []
        try:
            in_require = False
            for line in go_mod.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("require"):
                    if "(" in stripped:
                        in_require = True
                        continue
                    # Single-line require
                    parts = stripped.split()
                    if len(parts) >= 2:
                        deps.append(parts[1])
                    continue
                if in_require:
                    if stripped == ")":
                        in_require = False
                        continue
                    parts = stripped.split()
                    if parts:
                        deps.append(parts[0])
        except UnicodeDecodeError:
            pass
        return sorted(set(deps))

    # ── Ruby ──────────────────────────────────────────────────

    def _get_ruby_dependencies(self) -> list[str]:
        gemfile = self.path / "Gemfile"
        if not gemfile.exists():
            return []
        deps: list[str] = []
        try:
            for line in gemfile.read_text(encoding="utf-8").splitlines():
                match = re.match(r"gem\s+['\"]([^'\"]+)['\"]", line.strip())
                if match:
                    deps.append(match.group(1))
        except UnicodeDecodeError:
            pass
        return sorted(set(deps))

    # ── PHP ───────────────────────────────────────────────────

    def _get_php_dependencies(self) -> list[str]:
        data = self._read_json("composer.json")
        if not data:
            return []
        return sorted(data.get("require", {}).keys())

    # ── Java ──────────────────────────────────────────────────

    def _detect_java_framework(self) -> str | None:
        pom = self.path / "pom.xml"
        if pom.exists():
            try:
                content = pom.read_text(encoding="utf-8")
                if "spring-boot" in content:
                    return "spring"
            except UnicodeDecodeError:
                pass
        for gradle_file in ("build.gradle", "build.gradle.kts"):
            gf = self.path / gradle_file
            if gf.exists():
                try:
                    content = gf.read_text(encoding="utf-8")
                    if "spring" in content.lower():
                        return "spring"
                except UnicodeDecodeError:
                    pass
        return None
