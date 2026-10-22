"""Pydantic models for deployments and releases."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SourceUploadResponse(BaseModel):
    """Response from POST /v2/projects/{name}/sources."""
    sourceID: str = Field(default="")


class ReleaseRequest(BaseModel):
    """Request body for POST /v2/projects/{name}/releases."""
    sourceID: str
    port: int | None = Field(default=None)
    type: str | None = Field(default=None)
    buildCmd: str | None = Field(default=None)
    startCmd: str | None = Field(default=None)


class ReleaseInfo(BaseModel):
    """Release/deployment information."""
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(default="", alias="_id")
    status: str = Field(default="")
    type: str = Field(default="")
    port: int | None = Field(default=None)
    created_at: str | None = Field(default=None)
    sourceID: str | None = Field(default=None)
    releaseID: str | None = Field(default=None)


class ReleasesResponse(BaseModel):
    """Response from GET /v1/projects/{name}/releases."""
    releases: list[ReleaseInfo] = Field(default_factory=list)


class DeployEvent(BaseModel):
    """Deployment event."""
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(default="", alias="_id")
    type: str = Field(default="")
    message: str = Field(default="")
    status: str = Field(default="")
    created_at: str | None = Field(default=None)



class EventsResponse(BaseModel):
    """Response from GET /v1/projects/{name}/events."""
    events: list[DeployEvent] = Field(default_factory=list)
