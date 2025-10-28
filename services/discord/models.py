"""Pydantic models for Discord REST API endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MessageSendRequest(BaseModel):
    """Request model for sending Discord messages."""

    channel_id: str = Field(..., description="Discord channel ID")
    content: str = Field(..., description="Message content")
    correlation_id: str | None = Field(None, description="Correlation ID for tracing")
    metadata: dict[str, Any] | None = Field(
        default_factory=dict, description="Additional metadata"
    )


class MessageSendResponse(BaseModel):
    """Response model for sending Discord messages."""

    success: bool = Field(..., description="Whether message was sent successfully")
    message_id: str | None = Field(None, description="Discord message ID")
    correlation_id: str | None = Field(None, description="Correlation ID for tracing")
    error: str | None = Field(None, description="Error message if sending failed")


class TranscriptNotificationRequest(BaseModel):
    """Request model for transcript notifications."""

    transcript: str = Field(..., description="The transcript text")
    user_id: str = Field(..., description="Discord user ID")
    channel_id: str = Field(..., description="Discord channel ID")
    correlation_id: str | None = Field(None, description="Correlation ID for tracing")
    metadata: dict[str, Any] | None = Field(
        default_factory=dict, description="Additional metadata"
    )


class TranscriptNotificationResponse(BaseModel):
    """Response model for transcript notifications."""

    success: bool = Field(
        ..., description="Whether notification was processed successfully"
    )
    correlation_id: str | None = Field(None, description="Correlation ID for tracing")
    error: str | None = Field(None, description="Error message if processing failed")


class CapabilityInfo(BaseModel):
    """Information about a Discord capability."""

    name: str = Field(..., description="Capability name")
    description: str = Field(..., description="Capability description")
    parameters: dict[str, Any] | None = Field(None, description="Required parameters")


class CapabilitiesResponse(BaseModel):
    """Response model for Discord capabilities."""

    service: str = Field(..., description="Service name")
    capabilities: list[CapabilityInfo] = Field(
        ..., description="List of available capabilities"
    )
    version: str = Field(..., description="Service version")
