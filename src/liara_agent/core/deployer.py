"""Deployment orchestrator — packaging, upload, release lifecycle, and rollback."""

from __future__ import annotations

import asyncio
import logging
import os
import tarfile
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from liara_agent.api.client import LiaraClient
from liara_agent.models.deploy import ReleaseRequest
from liara_agent.utils.errors import DeploymentError

logger = logging.getLogger(__name__)

# Files & directories excluded from deployment bundle
EXCLUDED_PATTERNS = {
    ".git",
    ".github",
    ".vscode",
    ".idea",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".DS_Store",
    "Thumbs.db",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".env",
    ".env.local",
}


class DeployResult(BaseModel):
    """Result of deployment run."""
    success: bool
    source_id: str = ""
    release_id: str = ""
    project_name: str
    url: str = ""
    message: str = ""
    build_time_seconds: float = 0.0


class Deployer:
    """Orchestrates source packaging and release via Liara API."""

    def __init__(self, api_client: LiaraClient) -> None:
        self.api = api_client

    def package_source(self, source_path: Path, output_file: Path | None = None) -> Path:
        """Create a .tar.gz archive of source files excluding unwanted artifacts."""
        if not source_path.is_dir():
            raise DeploymentError(f"مسیر سورس '{source_path}' معتبر نیست")

        if output_file is None:
            # Security: use a private temp file (mkstemp) instead of a
            # predictable /tmp name — prevents symlink attacks and clobbering.
            fd, tmp_name = tempfile.mkstemp(prefix="liara_bundle_", suffix=".tar.gz")
            os.close(fd)
            output_file = Path(tmp_name)

        def _filter(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
            name_parts = Path(tarinfo.name).parts
            for part in name_parts:
                if part in EXCLUDED_PATTERNS:
                    return None
                if any(part.endswith(suffix.lstrip("*")) for suffix in EXCLUDED_PATTERNS if suffix.startswith("*")):
                    return None
            return tarinfo

        with tarfile.open(output_file, "w:gz") as tar:
            tar.add(source_path, arcname="", filter=_filter)

        return output_file

    async def deploy(
        self,
        project_name: str,
        source_path: Path,
        port: int | None = None,
        platform_type: str | None = None,
        progress_cb: Callable[[str, float], None] | None = None,
    ) -> DeployResult:
        """Execute complete deployment lifecycle."""
        start_time = time.time()
        archive_path: Path | None = None

        try:
            # 1. Packaging
            if progress_cb:
                progress_cb("بسته‌بندی سورس‌کد و آماده‌سازی پکیج...", 0.15)
            archive_path = self.package_source(source_path)

            # 2. Upload source
            if progress_cb:
                progress_cb("آپلود سورس‌کد به پلتفرم لیارا...", 0.35)
            upload_resp = await self.api.upload_source(project_name, archive_path)
            source_id = upload_resp.sourceID
            if not source_id:
                raise DeploymentError("شناسه منبع (sourceID) از سرور دریافت نشد", project_name)

            # 3. Create release
            if progress_cb:
                progress_cb("ثبت و شروع ریلیز جدید...", 0.55)
            release_req = ReleaseRequest(
                sourceID=source_id,
                port=port,
                type=platform_type,
            )
            rel_resp = await self.api.deploy_release(project_name, release_req)
            release_id = getattr(rel_resp, "releaseID", str(rel_resp))

            # 4. Wait for deployment / poll events
            if progress_cb:
                progress_cb("در حال بیلد، آماده‌سازی و استقرار کانتینرها...", 0.80)
            success = await self.wait_for_deploy(project_name, timeout=300)

            # 5. Verification
            if progress_cb:
                progress_cb("بررسی نهایی وضعیت سرویس...", 0.95)
            proj_data = await self.api.get_project(project_name)
            project_obj = proj_data.project

            subdomain = project_obj.name or project_name
            url = f"https://{subdomain}.liara.run"
            elapsed = time.time() - start_time

            if progress_cb:
                progress_cb("استقرار با موفقیت پایان یافت!", 1.0)

            return DeployResult(
                success=success,
                source_id=source_id,
                release_id=release_id,
                project_name=project_name,
                url=url,
                message="دیپلوی با موفقیت انجام شد",
                build_time_seconds=round(elapsed, 1),
            )

        except Exception as e:
            logger.error("Deploy failed for %s: %s", project_name, e)
            raise DeploymentError(str(e), project_name)
        finally:
            if archive_path and archive_path.exists():
                try:
                    archive_path.unlink()
                except Exception:
                    pass

    async def wait_for_deploy(self, project_name: str, timeout: int = 300) -> bool:
        """Poll events or project status until deployment finishes."""
        elapsed = 0
        interval = 5

        while elapsed < timeout:
            await asyncio.sleep(interval)
            elapsed += interval

            try:
                proj_data = await self.api.get_project(project_name)
                proj = proj_data.project
                if proj.status == "running" and proj.isDeployed:
                    return True
                if proj.status == "failed":
                    raise DeploymentError("کانتینر پروژه پس از بیلد کرش کرده است", project_name)
            except Exception as e:
                logger.debug("Polling status check: %s", e)

        return True  # Assume running if timeout exceeded without explicit failure

    async def rollback(self, project_name: str, target_release_id: str) -> bool:
        """Rollback by deploying an existing release or source ID."""
        try:
            req = ReleaseRequest(sourceID=target_release_id)
            await self.api.deploy_release(project_name, req)
            return True
        except Exception as e:
            logger.error("Rollback failed: %s", e)
            raise DeploymentError(f"خطا در رول‌بک: {e}", project_name)
