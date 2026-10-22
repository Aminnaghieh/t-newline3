"""SQLite database manager for local persistence and state management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite

from liara_agent.utils.config import DB_PATH


class Database:
    """Async SQLite database manager for liara-agent."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path

    async def initialize(self) -> None:
        """Create tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    name TEXT PRIMARY KEY,
                    platform TEXT,
                    plan_id TEXT,
                    port INTEGER,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS deployments (
                    id TEXT PRIMARY KEY,
                    project_name TEXT,
                    source_id TEXT,
                    release_id TEXT,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    details TEXT
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    action TEXT NOT NULL,
                    target TEXT,
                    risk_level TEXT,
                    status TEXT,
                    details TEXT
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.commit()

    async def save_project(self, project: dict[str, Any]) -> None:
        """Save or update project information."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO projects (name, platform, plan_id, port, status, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project.get("name") or project.get("project_id"),
                    project.get("platform") or project.get("type"),
                    project.get("planID") or project.get("plan_id"),
                    project.get("port"),
                    project.get("status"),
                    json.dumps(project, ensure_ascii=False),
                ),
            )
            await db.commit()

    async def get_project(self, name: str) -> dict[str, Any] | None:
        """Retrieve project by name."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT metadata FROM projects WHERE name = ?", (name,)) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return json.loads(row[0])
                return None

    async def save_deployment(self, deployment: dict[str, Any]) -> None:
        """Save deployment record."""
        dep_id = deployment.get("id") or deployment.get("releaseID") or deployment.get("sourceID", "dep_unknown")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO deployments (id, project_name, source_id, release_id, status, details)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(dep_id),
                    deployment.get("project_name", ""),
                    deployment.get("sourceID"),
                    deployment.get("releaseID"),
                    deployment.get("status", "unknown"),
                    json.dumps(deployment, ensure_ascii=False),
                ),
            )
            await db.commit()

    async def get_deployments(self, project: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get past deployments for a project."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT details FROM deployments WHERE project_name = ? ORDER BY created_at DESC LIMIT ?",
                (project, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [json.loads(r[0]) for r in rows if r[0]]

    async def save_audit_log(
        self,
        action: str,
        target: str = "",
        risk_level: str = "low",
        status: str = "success",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Save an audit log entry."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO audit_logs (action, target, risk_level, status, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    action,
                    target,
                    risk_level,
                    status,
                    json.dumps(details or {}, ensure_ascii=False),
                ),
            )
            await db.commit()

    async def get_audit_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent audit logs."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT id, timestamp, action, target, risk_level, status, details FROM audit_logs ORDER BY id DESC LIMIT ?",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                results = []
                for row in rows:
                    results.append({
                        "id": row[0],
                        "timestamp": row[1],
                        "action": row[2],
                        "target": row[3],
                        "risk_level": row[4],
                        "status": row[5],
                        "details": json.loads(row[6]) if row[6] else {},
                    })
                return results


_default_db: Database | None = None


async def get_db() -> Database:
    """Get initialized default database."""
    global _default_db
    if _default_db is None:
        _default_db = Database()
        await _default_db.initialize()
    return _default_db
