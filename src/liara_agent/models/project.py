"""Pydantic models for Liara projects/apps."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    """Request body for creating a new project."""
    name: str = Field(..., description="Project name (lowercase, alphanumeric, hyphens)")
    planID: str = Field(default="micro", description="Plan ID")
    platform: str = Field(..., description="Platform type (nodejs, python, go, ...)")
    readOnlyRootFilesystem: bool = Field(default=False)
    network: str = Field(default="default")


class ProjectEnv(BaseModel):
    """Environment variable."""
    key: str
    value: str


class ProjectUpdateEnvs(BaseModel):
    """Request body for updating environment variables."""
    project: str
    variables: list[ProjectEnv]


class ScaleRequest(BaseModel):
    """Request body for scaling a project on/off."""
    scale: int = Field(..., description="1 = on, 0 = off")


class ResizeRequest(BaseModel):
    """Request body for changing plan."""
    planID: str


class ProjectInfo(BaseModel):
    """Project information from Liara API."""
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(default="", alias="_id")
    project_id: str = Field(default="")
    name: str = Field(default="", alias="project_id")
    type: str = Field(default="")
    status: str = Field(default="")
    scale: int = Field(default=0)
    planID: str = Field(default="")
    created_at: str | None = Field(default=None)
    updated_at: str | None = Field(default=None)
    isDeployed: bool = Field(default=False)

    # Optional fields from detailed response
    port: int | None = Field(default=None)
    envs: list[dict] | None = Field(default=None)
    disk: list[dict] | None = Field(default=None)
    domains: list[dict] | None = Field(default=None)


class ProjectListResponse(BaseModel):
    """Response from GET /v1/projects."""
    projects: list[ProjectInfo] = Field(default_factory=list)


class ProjectDetailResponse(BaseModel):
    """Response from GET /v1/projects/{name}."""
    project: ProjectInfo
