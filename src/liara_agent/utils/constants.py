"""Constants and enums used across the application."""

from enum import StrEnum


# ─── Liara API ────────────────────────────────────────────────
LIARA_API_BASE_URL = "https://api.liara.ir"
LIARA_WS_BASE_URL = "wss://api.liara.ir"
LIARA_CONSOLE_URL = "https://console.liara.ir"
LIARA_DOCS_URL = "https://developers.liara.ir"

# ─── Rate Limits (conservative) ──────────────────────────────
RATE_LIMIT_READ_PER_MIN = 60
RATE_LIMIT_WRITE_PER_MIN = 20
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF = 2.0  # seconds

# ─── Polling Intervals ───────────────────────────────────────
DEPLOY_POLL_INTERVAL = 5  # seconds
EVENTS_POLL_INTERVAL = 30  # seconds
METRICS_POLL_INTERVAL = 10  # seconds
HEALTH_CHECK_INTERVAL = 60  # seconds


class Platform(StrEnum):
    """Supported Liara platforms."""
    NODEJS = "nodejs"
    PYTHON = "python"
    GO = "go"
    PHP = "php"
    RUBY = "ruby"
    DOTNET = "dotnet"
    STATIC = "static"
    DOCKER = "docker"
    JAVA = "java"
    RUST = "rust"
    DENO = "deno"
    BUN = "bun"


class PlanID(StrEnum):
    """Available Liara plan IDs."""
    MICRO = "micro"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    XLARGE = "xlarge"
    XXLARGE = "xxlarge"


class AppStatus(StrEnum):
    """Application status values."""
    RUNNING = "running"
    STOPPED = "stopped"
    DEPLOYING = "deploying"
    FAILED = "failed"
    BUILDING = "building"
    STARTING = "starting"


class RiskLevel(StrEnum):
    """Operation risk levels for Human-in-the-Loop."""
    LOW = "low"          # Auto-execute (read operations, status checks)
    MEDIUM = "medium"    # Notify & execute (restart, env update)
    HIGH = "high"        # Require explicit approval (scale, plan change, delete)
    CRITICAL = "critical"  # Double confirmation (delete project, rollback)


class DeployStatus(StrEnum):
    """Deployment status."""
    PENDING = "pending"
    BUILDING = "building"
    PUSHING = "pushing"
    RUNNING = "running"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MetricType(StrEnum):
    """Metric types for monitoring."""
    CPU = "cpu"
    MEMORY = "memory"
    NETWORK = "network"
    DISK = "disk"


class MetricPeriod(StrEnum):
    """Time periods for metrics."""
    ONE_HOUR = "1h"
    SIX_HOURS = "6h"
    ONE_DAY = "24h"
    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"


class ErrorCategory(StrEnum):
    """Error categories for RCA."""
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CODE_BUG = "code_bug"
    CONFIG_ERROR = "config_error"
    DEPENDENCY_FAILURE = "dependency_failure"
    NETWORK_ISSUE = "network_issue"
    BUILD_FAILURE = "build_failure"
    PERMISSION_ERROR = "permission_error"
    UNKNOWN = "unknown"


# ─── Plan Catalog (local mapping) ────────────────────────────
PLAN_CATALOG: dict[str, dict] = {
    "ir-small": {
        "cpu": 0.5, "ram_gb": 0.5, "disk_gb": 1.0,
        "bandwidth_gb": 50, "label": "IR Small",
        "description": "پلن اقتصادی دیتاسنتر ایران — مناسب تست و شروع",
    },
    "ir-medium": {
        "cpu": 1.0, "ram_gb": 1.0, "disk_gb": 2.5,
        "bandwidth_gb": 100, "label": "IR Medium",
        "description": "پلن استاندارد دیتاسنتر ایران — مناسب استارتاپ‌ها",
    },
    "standard-base": {
        "cpu": 1.0, "ram_gb": 2.0, "disk_gb": 5.0,
        "bandwidth_gb": 200, "label": "Standard Base",
        "description": "پلن استاندارد پایه با ۲ گیگ رم برای فریم‌ورک‌های سنگین‌تر",
    },
    "standard-plus": {
        "cpu": 2.0, "ram_gb": 4.0, "disk_gb": 10.0,
        "bandwidth_gb": 400, "label": "Standard Plus",
        "description": "مناسب پروژه‌های با ترافیک متوسط و پروداکشن",
    },
    "pro": {
        "cpu": 4.0, "ram_gb": 8.0, "disk_gb": 25.0,
        "bandwidth_gb": 800, "label": "Pro",
        "description": "پلن حرفه‌ای برای بارهای کاری سنگین",
    },
    "pro-plus": {
        "cpu": 6.0, "ram_gb": 16.0, "disk_gb": 50.0,
        "bandwidth_gb": 1500, "label": "Pro Plus",
        "description": "بالاترین سطح سازمانی — پردازش‌های فشرده",
    },
    # Aliases for convenience
    "micro": {
        "cpu": 0.5, "ram_gb": 0.5, "disk_gb": 1.0,
        "bandwidth_gb": 50, "label": "IR Small (Micro)",
        "description": "مناسب تست و پروژه‌های شخصی کوچک",
    },
    "small": {
        "cpu": 1.0, "ram_gb": 1.0, "disk_gb": 2.5,
        "bandwidth_gb": 100, "label": "IR Medium (Small)",
        "description": "مناسب پروژه‌های کوچک و استارتاپ‌ها",
    },
    "medium": {
        "cpu": 2.0, "ram_gb": 2.0, "disk_gb": 5.0,
        "bandwidth_gb": 200, "label": "Standard Base (Medium)",
        "description": "مناسب پروژه‌های متوسط با ترافیک معقول",
    },
}

# ─── Project Detection Patterns ──────────────────────────────
PLATFORM_DETECTION: dict[str, dict] = {
    "nodejs": {
        "files": ["package.json"],
        "default_port": 3000,
        "start_cmd": "npm start",
    },
    "python": {
        "files": ["requirements.txt", "Pipfile", "pyproject.toml", "setup.py"],
        "default_port": 8000,
        "start_cmd": "python app.py",
    },
    "go": {
        "files": ["go.mod"],
        "default_port": 8080,
        "start_cmd": "go run .",
    },
    "php": {
        "files": ["composer.json", "index.php"],
        "default_port": 80,
        "start_cmd": "php -S 0.0.0.0:80",
    },
    "ruby": {
        "files": ["Gemfile"],
        "default_port": 3000,
        "start_cmd": "bundle exec rails server",
    },
    "dotnet": {
        "files": ["*.csproj", "*.fsproj"],
        "default_port": 5000,
        "start_cmd": "dotnet run",
    },
    "static": {
        "files": ["index.html"],
        "default_port": 80,
        "start_cmd": None,
    },
    "docker": {
        "files": ["Dockerfile", "docker-compose.yml"],
        "default_port": None,
        "start_cmd": None,
    },
    "java": {
        "files": ["pom.xml", "build.gradle", "build.gradle.kts"],
        "default_port": 8080,
        "start_cmd": "java -jar app.jar",
    },
    "rust": {
        "files": ["Cargo.toml"],
        "default_port": 8080,
        "start_cmd": "cargo run --release",
    },
    "deno": {
        "files": ["deno.json", "deno.jsonc", "mod.ts"],
        "default_port": 8000,
        "start_cmd": "deno run --allow-net mod.ts",
    },
    "bun": {
        "files": ["bun.lockb", "bunfig.toml"],
        "default_port": 3000,
        "start_cmd": "bun start",
    },
}
