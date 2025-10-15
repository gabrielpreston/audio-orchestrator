"""
Standardized correlation ID generation for all services.

This module provides a consistent way to generate correlation IDs across all services
in the voice pipeline, ensuring proper hierarchical organization and traceability.
"""

import time


class CorrelationIDGenerator:
    """Standardized correlation ID generator for voice pipeline services."""

    @staticmethod
    def generate_discord_correlation_id(
        user_id: int, guild_id: int | None = None
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
        guild_part = f"-{guild_id}" if guild_id else ""
        return f"discord-{user_id}{guild_part}-{timestamp_ms}"

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
        return f"stt-{timestamp_ms}"

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
        return f"tts-{timestamp_ms}"

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
        user_part = f"{user_id}-" if user_id else ""
        return f"orchestrator-{user_part}{timestamp_ms}"

    @staticmethod
    def generate_mcp_correlation_id(
        source_correlation_id: str, client_name: str, tool_name: str
    ) -> str:
        """
        Generate a correlation ID for MCP tool calls.

        Format: mcp-{client_name}-{tool_name}-{source_id}

        Args:
            source_correlation_id: Source correlation ID from orchestrator
            client_name: MCP client name
            tool_name: MCP tool name

        Returns:
            Standardized correlation ID
        """
        return f"mcp-{client_name}-{tool_name}-{source_correlation_id}"

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
        context_part = f"-{context}" if context else ""
        return f"manual-{service}{context_part}-{timestamp_ms}"

    @staticmethod
    def parse_correlation_id(correlation_id: str) -> dict:
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

        elif service == "mcp":
            if len(parts) >= 4:
                return {
                    "service": "mcp",
                    "client_name": parts[1],
                    "tool_name": parts[2],
                    "source_id": "-".join(parts[3:]),
                    "raw": correlation_id,
                }

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
        return parsed["service"]

    @staticmethod
    def is_valid_correlation_id(correlation_id: str) -> bool:
        """
        Check if a correlation ID follows the expected format.

        Args:
            correlation_id: The correlation ID to validate

        Returns:
            True if valid, False otherwise
        """
        if not correlation_id or not isinstance(correlation_id, str):
            return False

        # Check for minimum length and basic format
        if len(correlation_id) < 10:  # Minimum reasonable length
            return False

        # Check for incomplete IDs (ending with dash)
        if correlation_id.endswith("-"):
            return False

        parsed = CorrelationIDGenerator.parse_correlation_id(correlation_id)
        return parsed["service"] != "unknown"


# Convenience functions for backward compatibility
def generate_discord_correlation_id(user_id: int, guild_id: int | None = None) -> str:
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


def generate_mcp_correlation_id(
    source_correlation_id: str, client_name: str, tool_name: str
) -> str:
    """Generate an MCP correlation ID."""
    return CorrelationIDGenerator.generate_mcp_correlation_id(
        source_correlation_id, client_name, tool_name
    )


def generate_manual_correlation_id(service: str, context: str | None = None) -> str:
    """Generate a manual correlation ID."""
    return CorrelationIDGenerator.generate_manual_correlation_id(service, context)


def parse_correlation_id(correlation_id: str) -> dict:
    """Parse a correlation ID."""
    return CorrelationIDGenerator.parse_correlation_id(correlation_id)


def get_service_from_correlation_id(correlation_id: str) -> str:
    """Get service name from correlation ID."""
    return CorrelationIDGenerator.get_service_from_correlation_id(correlation_id)


def is_valid_correlation_id(correlation_id: str) -> bool:
    """Check if correlation ID is valid."""
    return CorrelationIDGenerator.is_valid_correlation_id(correlation_id)
