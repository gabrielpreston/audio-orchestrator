"""
Standardized correlation ID generation for all services.

This module provides a consistent way to generate correlation IDs across all services
in the voice pipeline, ensuring proper hierarchical organization and traceability.
"""

import re
import time
import uuid
from typing import Any


def _generate_unique_suffix() -> str:
    """Generate a short unique suffix to prevent collisions."""
    return str(uuid.uuid4())[:8]


def validate_correlation_id(correlation_id: str | None) -> tuple[bool, str]:
    """Validate correlation ID format and content.

    Args:
        correlation_id: The correlation ID to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not correlation_id or not isinstance(correlation_id, str):
        return False, "Correlation ID is required and must be a string"

    # Check length limits
    if len(correlation_id) < 10:
        return False, "Correlation ID too short (minimum 10 characters)"

    if len(correlation_id) > 500:
        return False, "Correlation ID too long (maximum 500 characters)"

    # Check for valid characters only (alphanumeric, hyphens, underscores)
    if not re.match(r"^[a-zA-Z0-9\-_]+$", correlation_id):
        return (
            False,
            "Correlation ID contains invalid characters (only alphanumeric, hyphens, and underscores allowed)",
        )

    # Check for incomplete IDs
    if correlation_id.endswith("-") or correlation_id.startswith("-"):
        return False, "Correlation ID cannot start or end with hyphen"

    # Validate known service prefixes
    parsed = CorrelationIDGenerator.parse_correlation_id(correlation_id)
    if parsed["service"] == "unknown":
        return False, "Correlation ID has unknown service prefix"

    return True, ""


class CorrelationIDGenerator:
    """Standardized correlation ID generator for voice pipeline services."""

    @staticmethod
    def generate_discord_correlation_id(
        user_id: int | None, guild_id: int | None = None
    ) -> str:
        """
        Generate a correlation ID for Discord voice interactions.

        Format: discord-{user_id}-{guild_id}-{timestamp_ms}

        Args:
            user_id: Discord user ID
            guild_id: Optional Discord guild ID

        Returns:
            Standardized correlation ID
        """
        if user_id is None:
            raise ValueError("user_id cannot be None")

        timestamp_ms = int(time.time() * 1000)
        unique_suffix = _generate_unique_suffix()
        guild_part = f"-{guild_id}" if guild_id else ""
        return f"discord-{user_id}{guild_part}-{timestamp_ms}-{unique_suffix}"

    @staticmethod
    def generate_stt_correlation_id(source_correlation_id: str | None = None) -> str:
        """
        Generate a correlation ID for STT service.

        If source_correlation_id is provided, it will be used as the base.
        Otherwise, generates a new STT-specific ID.

        Format: stt-{source_id} or stt-{timestamp_ms}

        Args:
            source_correlation_id: Optional source correlation ID from upstream service

        Returns:
            Standardized correlation ID
        """
        if source_correlation_id:
            return f"stt-{source_correlation_id}"

        timestamp_ms = int(time.time() * 1000)
        unique_suffix = _generate_unique_suffix()
        return f"stt-{timestamp_ms}-{unique_suffix}"

    @staticmethod
    def generate_tts_correlation_id(source_correlation_id: str | None = None) -> str:
        """
        Generate a correlation ID for TTS service.

        If source_correlation_id is provided, it will be used as the base.
        Otherwise, generates a new TTS-specific ID.

        Format: tts-{source_id} or tts-{timestamp_ms}

        Args:
            source_correlation_id: Optional source correlation ID from upstream service

        Returns:
            Standardized correlation ID
        """
        if source_correlation_id:
            return f"tts-{source_correlation_id}"

        timestamp_ms = int(time.time() * 1000)
        unique_suffix = _generate_unique_suffix()
        return f"tts-{timestamp_ms}-{unique_suffix}"

    @staticmethod
    def generate_orchestrator_correlation_id(
        source_correlation_id: str | None = None, user_id: str | None = None
    ) -> str:
        """
        Generate a correlation ID for orchestrator service.

        If source_correlation_id is provided, it will be used as the base.
        Otherwise, generates a new orchestrator-specific ID.

        Format: orchestrator-{source_id} or orchestrator-{user_id}-{timestamp_ms}

        Args:
            source_correlation_id: Optional source correlation ID from upstream service
            user_id: Optional user ID for context

        Returns:
            Standardized correlation ID
        """
        if source_correlation_id:
            return f"orchestrator-{source_correlation_id}"

        timestamp_ms = int(time.time() * 1000)
        unique_suffix = _generate_unique_suffix()
        user_part = f"{user_id}-" if user_id else ""
        return f"orchestrator-{user_part}{timestamp_ms}-{unique_suffix}"

    # External tool correlation functions removed - using REST API now

    @staticmethod
    def generate_manual_correlation_id(service: str, context: str | None = None) -> str:
        """
        Generate a correlation ID for manual operations.

        Format: manual-{service}-{context}-{timestamp_ms}

        Args:
            service: Service name
            context: Optional context identifier

        Returns:
            Standardized correlation ID
        """
        timestamp_ms = int(time.time() * 1000)
        unique_suffix = _generate_unique_suffix()
        context_part = f"-{context}" if context else ""
        return f"manual-{service}{context_part}-{timestamp_ms}-{unique_suffix}"

    @staticmethod
    def parse_correlation_id(correlation_id: str) -> dict[str, Any]:
        """
        Parse a correlation ID to extract its components.

        Args:
            correlation_id: The correlation ID to parse

        Returns:
            Dictionary with parsed components
        """
        parts = correlation_id.split("-")

        if len(parts) < 2:
            return {
                "service": "unknown",
                "type": "unknown",
                "timestamp": None,
                "raw": correlation_id,
            }

        service = parts[0]

        # Handle different correlation ID formats
        if service == "discord":
            if len(parts) >= 4:
                return {
                    "service": "discord",
                    "user_id": parts[1],
                    "guild_id": parts[2] if parts[2] != parts[3] else None,
                    "timestamp": parts[-1],
                    "raw": correlation_id,
                }
            else:
                return {
                    "service": "discord",
                    "user_id": parts[1],
                    "guild_id": None,
                    "timestamp": parts[-1],
                    "raw": correlation_id,
                }

        elif service in ["stt", "tts", "orchestrator"]:
            return {
                "service": service,
                "source_id": "-".join(parts[1:]) if len(parts) > 1 else None,
                "timestamp": parts[-1] if parts[-1].isdigit() else None,
                "raw": correlation_id,
            }

        # External service handling removed - using REST API now

        elif service == "manual":
            return {
                "service": "manual",
                "context": parts[2] if len(parts) > 2 else None,
                "timestamp": parts[-1] if parts[-1].isdigit() else None,
                "raw": correlation_id,
            }

        return {
            "service": "unknown",
            "type": "unknown",
            "timestamp": None,
            "raw": correlation_id,
        }

    @staticmethod
    def get_service_from_correlation_id(correlation_id: str) -> str:
        """
        Extract the service name from a correlation ID.

        Args:
            correlation_id: The correlation ID to analyze

        Returns:
            Service name
        """
        parsed = CorrelationIDGenerator.parse_correlation_id(correlation_id)
        return str(parsed["service"])

    @staticmethod
    def is_valid_correlation_id(correlation_id: str | None) -> bool:
        """
        Check if a correlation ID follows the expected format.

        Args:
            correlation_id: The correlation ID to validate

        Returns:
            True if valid, False otherwise
        """
        valid, _ = validate_correlation_id(correlation_id)
        return valid


# Convenience functions for backward compatibility
def generate_discord_correlation_id(
    user_id: int | None, guild_id: int | None = None
) -> str:
    """Generate a Discord correlation ID."""
    return CorrelationIDGenerator.generate_discord_correlation_id(user_id, guild_id)


def generate_stt_correlation_id(source_correlation_id: str | None = None) -> str:
    """Generate an STT correlation ID."""
    return CorrelationIDGenerator.generate_stt_correlation_id(source_correlation_id)


def generate_tts_correlation_id(source_correlation_id: str | None = None) -> str:
    """Generate a TTS correlation ID."""
    return CorrelationIDGenerator.generate_tts_correlation_id(source_correlation_id)


def generate_orchestrator_correlation_id(
    source_correlation_id: str | None = None, user_id: str | None = None
) -> str:
    """Generate an orchestrator correlation ID."""
    return CorrelationIDGenerator.generate_orchestrator_correlation_id(
        source_correlation_id, user_id
    )


# External tool correlation functions removed - using REST API now


def generate_manual_correlation_id(service: str, context: str | None = None) -> str:
    """Generate a manual correlation ID."""
    return CorrelationIDGenerator.generate_manual_correlation_id(service, context)


def parse_correlation_id(correlation_id: str) -> dict[str, Any]:
    """Parse a correlation ID."""
    return CorrelationIDGenerator.parse_correlation_id(correlation_id)


def get_service_from_correlation_id(correlation_id: str) -> str:
    """Get service name from correlation ID."""
    return CorrelationIDGenerator.get_service_from_correlation_id(correlation_id)


def is_valid_correlation_id(correlation_id: str | None) -> bool:
    """Check if correlation ID is valid."""
    return CorrelationIDGenerator.is_valid_correlation_id(correlation_id)


__all__ = [
    "CorrelationIDGenerator",
    "generate_discord_correlation_id",
    "generate_manual_correlation_id",
    "generate_orchestrator_correlation_id",
    "generate_stt_correlation_id",
    "generate_tts_correlation_id",
    "get_service_from_correlation_id",
    "is_valid_correlation_id",
    "parse_correlation_id",
    "validate_correlation_id",
]
