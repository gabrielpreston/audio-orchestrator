"""Correlation ID utilities for request tracing across services."""

from __future__ import annotations

import contextvars
import uuid
from typing import Optional

# Context variable for correlation ID
_correlation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from context."""
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID in the current context."""
    _correlation_id.set(correlation_id)


def clear_correlation_id() -> None:
    """Clear the correlation ID from the current context."""
    _correlation_id.set(None)


def ensure_correlation_id() -> str:
    """Get or generate a correlation ID for the current context."""
    correlation_id = get_correlation_id()
    if correlation_id is None:
        correlation_id = generate_correlation_id()
        set_correlation_id(correlation_id)
    return correlation_id


__all__ = [
    "generate_correlation_id",
    "get_correlation_id",
    "set_correlation_id",
    "clear_correlation_id",
    "ensure_correlation_id",
]
