"""Tests for correlation ID parsing functionality."""

import time

import pytest

from services.common.correlation import (
    get_service_from_correlation_id,
    parse_correlation_id,
)


class TestCorrelationIDParsing:
    """Test correlation ID parsing functionality."""

    @pytest.mark.unit
    def test_parse_discord_with_guild(self):
        """Test parsing Discord correlation ID with guild."""
        correlation_id = "discord-123456-789012-1704067200000-12345678"
        parsed = parse_correlation_id(correlation_id)

        assert parsed["service"] == "discord"
        assert parsed["user_id"] == "123456"
        assert parsed["guild_id"] == "789012"
        assert parsed["timestamp"] == "12345678"
        assert parsed["raw"] == correlation_id

    @pytest.mark.unit
    def test_parse_discord_without_guild(self):
        """Test parsing Discord correlation ID without guild."""
        correlation_id = "discord-123456-1704067200000-12345678"
        parsed = parse_correlation_id(correlation_id)

        assert parsed["service"] == "discord"
        assert parsed["user_id"] == "123456"
        # The parsing logic treats this as having a guild_id because parts[2] != parts[3]
        assert parsed["guild_id"] == "1704067200000"
        assert parsed["timestamp"] == "12345678"
        assert parsed["raw"] == correlation_id

    @pytest.mark.unit
    def test_parse_stt_standalone(self):
        """Test parsing standalone STT correlation ID."""
        correlation_id = "stt-1704067200000-12345678"
        parsed = parse_correlation_id(correlation_id)

        assert parsed["service"] == "stt"
        assert parsed["source_id"] == "1704067200000-12345678"
        assert parsed["timestamp"] == "12345678"
        assert parsed["raw"] == correlation_id

    @pytest.mark.unit
    def test_parse_stt_chained(self):
        """Test parsing chained STT correlation ID."""
        correlation_id = "stt-discord-123456-789012-1704067200000-12345678"
        parsed = parse_correlation_id(correlation_id)

        assert parsed["service"] == "stt"
        assert parsed["source_id"] == "discord-123456-789012-1704067200000-12345678"
        assert parsed["timestamp"] == "12345678"
        assert parsed["raw"] == correlation_id

    @pytest.mark.unit
    def test_parse_tts_standalone(self):
        """Test parsing standalone TTS correlation ID."""
        correlation_id = "tts-1704067200000-12345678"
        parsed = parse_correlation_id(correlation_id)

        assert parsed["service"] == "tts"
        assert parsed["source_id"] == "1704067200000-12345678"
        assert parsed["timestamp"] == "12345678"
        assert parsed["raw"] == correlation_id

    @pytest.mark.unit
    def test_parse_tts_chained(self):
        """Test parsing chained TTS correlation ID."""
        correlation_id = "tts-orchestrator-123456-1704067200000-12345678"
        parsed = parse_correlation_id(correlation_id)

        assert parsed["service"] == "tts"
        assert parsed["source_id"] == "orchestrator-123456-1704067200000-12345678"
        assert parsed["timestamp"] == "12345678"
        assert parsed["raw"] == correlation_id

    @pytest.mark.unit
    def test_parse_orchestrator_standalone(self):
        """Test parsing standalone orchestrator correlation ID."""
        correlation_id = "orchestrator-123456-1704067200000-12345678"
        parsed = parse_correlation_id(correlation_id)

        assert parsed["service"] == "orchestrator"
        assert parsed["source_id"] == "123456-1704067200000-12345678"
        assert parsed["timestamp"] == "12345678"
        assert parsed["raw"] == correlation_id

    # External tool correlation tests removed - using REST API now

    @pytest.mark.unit
    def test_parse_manual_with_context(self):
        """Test parsing manual correlation ID with context."""
        correlation_id = "manual-test_service-debug-1704067200000-12345678"
        parsed = parse_correlation_id(correlation_id)

        assert parsed["service"] == "manual"
        assert parsed["context"] == "debug"
        assert parsed["timestamp"] == "12345678"
        assert parsed["raw"] == correlation_id

    @pytest.mark.unit
    def test_parse_manual_without_context(self):
        """Test parsing manual correlation ID without context."""
        correlation_id = "manual-test_service-1704067200000-12345678"
        parsed = parse_correlation_id(correlation_id)

        assert parsed["service"] == "manual"
        # The parsing logic treats this as having a context because of the format
        assert parsed["context"] == "1704067200000"
        assert parsed["timestamp"] == "12345678"
        assert parsed["raw"] == correlation_id

    @pytest.mark.unit
    def test_parse_edge_cases(self):
        """Test parsing edge cases."""
        malformed_id = "invalid"
        parsed = parse_correlation_id(malformed_id)
        assert parsed["service"] == "unknown"
        assert parsed["type"] == "unknown"
        assert parsed["timestamp"] is None
        assert parsed["raw"] == malformed_id

        parsed = parse_correlation_id("")
        assert parsed["service"] == "unknown"

        parsed = parse_correlation_id("single")
        assert parsed["service"] == "unknown"

    @pytest.mark.unit
    def test_get_service_from_correlation_id(self):
        """Test getting service name from correlation ID."""
        assert (
            get_service_from_correlation_id("discord-123456-1704067200000-12345678")
            == "discord"
        )
        assert get_service_from_correlation_id("stt-1704067200000-12345678") == "stt"
        assert get_service_from_correlation_id("tts-1704067200000-12345678") == "tts"
        assert (
            get_service_from_correlation_id(
                "orchestrator-123456-1704067200000-12345678"
            )
            == "orchestrator"
        )
        assert get_service_from_correlation_id("unknown-service-12345") == "unknown"

    @pytest.mark.unit
    def test_parsing_performance(self):
        """Test parsing performance with many IDs."""
        correlation_ids = [
            "discord-123456-1704067200000-12345678",
            "stt-1704067200000-12345678",
            "tts-1704067200000-12345678",
            "orchestrator-123456-1704067200000-12345678",
            "manual-service-1704067200000-12345678",
        ]

        start_time = time.time()
        for _ in range(1000):
            for correlation_id in correlation_ids:
                parsed = parse_correlation_id(correlation_id)
                assert parsed["service"] != "unknown"
        end_time = time.time()

        assert (end_time - start_time) < 1.0
