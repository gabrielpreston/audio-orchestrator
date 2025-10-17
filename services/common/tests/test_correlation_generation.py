"""Tests for correlation ID generation functionality."""

import re
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from services.common.correlation import (
    generate_discord_correlation_id,
    generate_manual_correlation_id,
    generate_mcp_correlation_id,
    generate_orchestrator_correlation_id,
    generate_stt_correlation_id,
    generate_tts_correlation_id,
)


class TestCorrelationIDGeneration:
    """Test correlation ID generation for all services."""

    @pytest.mark.unit
    def test_discord_correlation_id_basic(self):
        """Test basic Discord correlation ID generation."""
        result = generate_discord_correlation_id(123456, 789012)
        assert result.startswith("discord-123456-789012-")
        assert len(result.split("-")) >= 4

        result = generate_discord_correlation_id(123456)
        assert result.startswith("discord-123456-")
        assert len(result.split("-")) >= 3

    @pytest.mark.unit
    def test_discord_correlation_id_validation(self):
        """Test Discord correlation ID input validation."""
        with pytest.raises(ValueError, match="user_id cannot be None"):
            generate_discord_correlation_id(None)  # type: ignore[arg-type]

        result = generate_discord_correlation_id(123456, 789012)
        assert result.startswith("discord-123456-789012-")
        assert len(result.split("-")) >= 4

    @pytest.mark.unit
    def test_stt_correlation_id_standalone(self):
        """Test STT correlation ID generation without source."""
        result = generate_stt_correlation_id()
        assert result.startswith("stt-")
        assert len(result.split("-")) >= 2

    @pytest.mark.unit
    def test_stt_correlation_id_with_source(self):
        """Test STT correlation ID generation with source ID."""
        source_id = "discord-123456-789012-1704067200000-12345678"
        result = generate_stt_correlation_id(source_id)
        expected = f"stt-{source_id}"
        assert result == expected

    @pytest.mark.unit
    def test_tts_correlation_id_standalone(self):
        """Test TTS correlation ID generation without source."""
        result = generate_tts_correlation_id()
        assert result.startswith("tts-")
        assert len(result.split("-")) >= 2

    @pytest.mark.unit
    def test_tts_correlation_id_with_source(self):
        """Test TTS correlation ID generation with source ID."""
        source_id = "orchestrator-123456-1704067200000-12345678"
        result = generate_tts_correlation_id(source_id)
        expected = f"tts-{source_id}"
        assert result == expected

    @pytest.mark.unit
    def test_orchestrator_correlation_id_standalone(self):
        """Test orchestrator correlation ID generation without source."""
        result = generate_orchestrator_correlation_id(user_id="123456")
        assert result.startswith("orchestrator-123456-")
        assert len(result.split("-")) >= 3

        result = generate_orchestrator_correlation_id()
        assert result.startswith("orchestrator-")
        assert len(result.split("-")) >= 2

    @pytest.mark.unit
    def test_orchestrator_correlation_id_with_source(self):
        """Test orchestrator correlation ID generation with source ID."""
        source_id = "stt-discord-123456-789012-1704067200000-12345678"
        result = generate_orchestrator_correlation_id(source_id)
        expected = f"orchestrator-{source_id}"
        assert result == expected

    @pytest.mark.unit
    def test_mcp_correlation_id(self):
        """Test MCP correlation ID generation."""
        source_id = "orchestrator-123456-1704067200000-12345678"
        result = generate_mcp_correlation_id(source_id, "weather_client", "get_weather")
        expected = f"mcp-weather_client-get_weather-{source_id}"
        assert result == expected

    @pytest.mark.unit
    def test_manual_correlation_id(self):
        """Test manual correlation ID generation."""
        result = generate_manual_correlation_id("test_service", "debug")
        assert result.startswith("manual-test_service-debug-")
        assert len(result.split("-")) >= 4

        result = generate_manual_correlation_id("test_service")
        assert result.startswith("manual-test_service-")
        assert len(result.split("-")) >= 3

    @pytest.mark.unit
    def test_uuid_suffix_uniqueness(self):
        """Test that UUID suffixes ensure uniqueness."""
        ids = set()
        for _ in range(1000):
            id_ = generate_discord_correlation_id(123456)
            assert id_ not in ids, f"Duplicate ID generated: {id_}"
            ids.add(id_)

        assert len(ids) == 1000

    @pytest.mark.unit
    def test_timestamp_accuracy(self):
        """Test that timestamp component is accurate."""
        start_time = time.time()
        id_ = generate_discord_correlation_id(123456)
        end_time = time.time()

        parts = id_.split("-")
        timestamp_ms = int(parts[-2])

        timestamp_seconds = timestamp_ms / 1000
        # Allow for small timing differences
        assert start_time - 1 <= timestamp_seconds <= end_time + 1

    @pytest.mark.unit
    def test_format_compliance(self):
        """Test that all generated IDs follow documented formats."""
        discord_id = generate_discord_correlation_id(123456, 789012)
        assert re.match(r"^discord-\d+-\d+-\d+-\w{8}$", discord_id)

        stt_id = generate_stt_correlation_id()
        assert re.match(r"^stt-\d+-\w{8}$", stt_id)

        tts_id = generate_tts_correlation_id()
        assert re.match(r"^tts-\d+-\w{8}$", tts_id)

        orchestrator_id = generate_orchestrator_correlation_id(user_id="123456")
        assert re.match(r"^orchestrator-\d+-\d+-\w{8}$", orchestrator_id)

        mcp_id = generate_mcp_correlation_id("test_source", "client", "tool")
        assert re.match(r"^mcp-\w+-\w+-.+$", mcp_id)

        manual_id = generate_manual_correlation_id("service", "context")
        assert re.match(r"^manual-\w+-\w+-\d+-\w{8}$", manual_id)

    @pytest.mark.unit
    def test_backward_compatibility(self):
        """Test that convenience functions still work."""
        assert callable(generate_discord_correlation_id)
        assert callable(generate_stt_correlation_id)
        assert callable(generate_tts_correlation_id)
        assert callable(generate_orchestrator_correlation_id)
        assert callable(generate_mcp_correlation_id)
        assert callable(generate_manual_correlation_id)

        assert isinstance(generate_discord_correlation_id(123456), str)
        assert isinstance(generate_stt_correlation_id(), str)
        assert isinstance(generate_tts_correlation_id(), str)
        assert isinstance(generate_orchestrator_correlation_id(), str)
        assert isinstance(generate_mcp_correlation_id("source", "client", "tool"), str)
        assert isinstance(generate_manual_correlation_id("service"), str)

    @pytest.mark.unit
    def test_edge_cases(self):
        """Test edge cases in correlation ID generation."""
        large_id = generate_discord_correlation_id(999999999999999999)
        assert large_id.startswith("discord-999999999999999999-")

        zero_id = generate_discord_correlation_id(0)
        assert zero_id.startswith("discord-0-")

        long_source = "a" * 400
        stt_id = generate_stt_correlation_id(long_source)
        assert stt_id == f"stt-{long_source}"

        mcp_id = generate_mcp_correlation_id("source", "client_name", "tool_name")
        assert mcp_id == "mcp-client_name-tool_name-source"

    @pytest.mark.unit
    def test_concurrent_generation(self):
        """Test concurrent generation of correlation IDs."""

        def generate_id():
            return generate_discord_correlation_id(123456)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(generate_id) for _ in range(100)]
            ids = [future.result() for future in futures]

        assert len(set(ids)) == 100

        for id_ in ids:
            assert re.match(r"^discord-123456-\d+-\w{8}$", id_)

    @pytest.mark.unit
    def test_hierarchical_chaining(self):
        """Test hierarchical correlation ID chaining."""
        discord_id = generate_discord_correlation_id(123456, 789012)
        assert discord_id.startswith("discord-")

        stt_id = generate_stt_correlation_id(discord_id)
        assert stt_id == f"stt-{discord_id}"

        orchestrator_id = generate_orchestrator_correlation_id(stt_id)
        assert orchestrator_id == f"orchestrator-{stt_id}"

        tts_id = generate_tts_correlation_id(orchestrator_id)
        assert tts_id == f"tts-{orchestrator_id}"

        mcp_id = generate_mcp_correlation_id(tts_id, "weather", "get_weather")
        assert mcp_id == f"mcp-weather-get_weather-{tts_id}"

    @pytest.mark.unit
    def test_source_id_preservation(self):
        """Test that source IDs are preserved correctly in chaining."""
        original_id = "discord-123456-789012-1704067200000-12345678"

        stt_id = generate_stt_correlation_id(original_id)
        assert stt_id.endswith(original_id)

        tts_id = generate_tts_correlation_id(original_id)
        assert tts_id.endswith(original_id)

        orchestrator_id = generate_orchestrator_correlation_id(original_id)
        assert orchestrator_id.endswith(original_id)
