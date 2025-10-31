"""Shared utilities for HTTP header propagation."""

from __future__ import annotations

from collections.abc import Mapping


def inject_correlation_id(headers: Mapping[str, str] | None = None) -> dict[str, str]:
    """Inject correlation ID from context into headers if not present.

    This utility function provides a single source of truth for correlation ID
    propagation across all HTTP client implementations.

    Args:
        headers: Optional existing headers dict

    Returns:
        New headers dict with correlation ID added (if available in context)
    """
    result = dict(headers or {})

    # Only inject if not already present
    if "X-Correlation-ID" in result:
        return result

    # Try to get correlation ID from async context
    try:
        from services.common.middleware import get_correlation_id

        correlation_id = get_correlation_id()
        if correlation_id:
            result["X-Correlation-ID"] = correlation_id
    except ImportError:
        # Middleware not available, skip injection
        pass

    return result


def get_correlation_id_from_context() -> str | None:
    """Get correlation ID from async context (convenience function).

    Returns:
        Correlation ID if available, None otherwise
    """
    try:
        from services.common.middleware import get_correlation_id

        return get_correlation_id()
    except ImportError:
        return None


__all__ = ["inject_correlation_id", "get_correlation_id_from_context"]
