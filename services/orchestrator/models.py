"""Pydantic models for REST API endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TranscriptProcessRequest(BaseModel):
    """Request model for transcript processing."""

    transcript: str = Field(..., description="The transcript text to process")
    user_id: str = Field(..., description="Discord user ID")
    channel_id: str = Field(..., description="Discord channel ID")
    correlation_id: str | None = Field(None, description="Correlation ID for tracing")
    metadata: dict[str, Any] | None = Field(
        default_factory=dict, description="Additional metadata"
    )


class TranscriptProcessResponse(BaseModel):
    """Response model for transcript processing."""

    success: bool = Field(..., description="Whether processing was successful")
    response_text: str | None = Field(None, description="Generated response text")
    tool_calls: list[dict[str, Any]] | None = Field(
        None, description="Tool calls made during processing"
    )
    correlation_id: str | None = Field(None, description="Correlation ID for tracing")
    error: str | None = Field(None, description="Error message if processing failed")


class CapabilityInfo(BaseModel):
    """Information about a service capability."""

    name: str = Field(..., description="Capability name")
    description: str = Field(..., description="Capability description")
    parameters: dict[str, Any] | None = Field(None, description="Required parameters")


class CapabilitiesResponse(BaseModel):
    """Response model for service capabilities."""

    service: str = Field(..., description="Service name")
    capabilities: list[CapabilityInfo] = Field(
        ..., description="List of available capabilities"
    )
    version: str = Field(..., description="Service version")


class ConnectionInfo(BaseModel):
    """Information about a service connection."""

    service: str = Field(..., description="Service name")
    status: str = Field(..., description="Connection status")
    url: str | None = Field(None, description="Service URL")
    last_heartbeat: str | None = Field(None, description="Last heartbeat timestamp")


class StatusResponse(BaseModel):
    """Response model for service status."""

    service: str = Field(..., description="Service name")
    status: str = Field(..., description="Overall service status")
    connections: list[ConnectionInfo] = Field(..., description="Service connections")
    uptime: str | None = Field(None, description="Service uptime")
    version: str = Field(..., description="Service version")
