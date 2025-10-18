"""Tests for correlation ID validation functionality."""

import time

import pytest

from services.common.correlation import is_valid_correlation_id, validate_correlation_id


class TestCorrelationIDValidation:
    """Test correlation ID validation."""

    @pytest.fixture
    def valid_correlation_ids(self):
        """Sample of valid correlation IDs for each service."""
        return {
            "discord": "discord-123456-789012-1704067200000-12345678",
            "discord_no_guild": "discord-123456-1704067200000-12345678",
            "stt": "stt-1704067200000-12345678",
            "stt_chained": "stt-discord-123456-789012-1704067200000-12345678",
            "tts": "tts-1704067200000-12345678",
            "tts_chained": "tts-orchestrator-123456-1704067200000-12345678",
            "orchestrator": "orchestrator-123456-1704067200000-12345678",
            "orchestrator_chained": "orchestrator-stt-1704067200000-12345678",
            "mcp": "mcp-weather_client-get_weather-orchestrator-123456-1704067200000-12345678",
            "manual": "manual-test_service-debug-1704067200000-12345678",
        }

    @pytest.fixture
    def invalid_correlation_ids(self):
        """Invalid IDs with expected error messages."""
        return [
            (None, "Correlation ID is required and must be a string"),
            ("", "Correlation ID is required and must be a string"),
            ("short", "Correlation ID too short (minimum 10 characters)"),
            ("a" * 501, "Correlation ID too long (maximum 500 characters)"),
            ("invalid@chars", "Correlation ID contains invalid characters"),
            ("-starts-with-hyphen", "Correlation ID cannot start or end with hyphen"),
            ("ends-with-hyphen-", "Correlation ID cannot start or end with hyphen"),
            ("unknown-service-12345", "Correlation ID has unknown service prefix"),
            ("invalid-service-12345", "Correlation ID has unknown service prefix"),
            ("badformat-12345", "Correlation ID has unknown service prefix"),
        ]

    @pytest.mark.unit
    def test_valid_ids(self, valid_correlation_ids):
        """Test validation of valid correlation IDs."""
        for service, correlation_id in valid_correlation_ids.items():
            is_valid, error_msg = validate_correlation_id(correlation_id)
            assert is_valid, f"Valid {service} ID failed validation: {error_msg}"
            assert error_msg == ""

    @pytest.mark.unit
    def test_invalid_ids(self, invalid_correlation_ids):
        """Test validation of invalid correlation IDs."""
        for correlation_id, expected_error in invalid_correlation_ids:
            is_valid, error_msg = validate_correlation_id(correlation_id)
            assert not is_valid, f"Invalid ID should fail validation: {correlation_id}"
            assert (
                expected_error in error_msg
            ), f"Expected error '{expected_error}' not in '{error_msg}'"

    @pytest.mark.unit
    def test_validation_edge_cases(self):
        """Test edge cases in validation."""
        min_id = "a" * 10
        is_valid, error_msg = validate_correlation_id(min_id)
        assert not is_valid

        # Test a very long ID that exceeds the 500 character limit
        max_id = "discord-" + "a" * 500
        is_valid, error_msg = validate_correlation_id(max_id)
        assert not is_valid

        valid_min_id = "discord-123456-1704067200000-12345678"
        is_valid, error_msg = validate_correlation_id(valid_min_id)
        assert is_valid

    @pytest.mark.unit
    def test_is_valid_correlation_id(self):
        """Test the is_valid_correlation_id convenience function."""
        valid_id = "discord-123456-1704067200000-12345678"
        assert is_valid_correlation_id(valid_id)

        invalid_id = "invalid-service-12345"
        assert not is_valid_correlation_id(invalid_id)

        # Test with None - should return False
        assert not is_valid_correlation_id(None)  # type: ignore[arg-type]

    @pytest.mark.unit
    def test_validation_performance(self):
        """Test validation performance with many IDs."""
        valid_ids = [
            "discord-123456-1704067200000-12345678",
            "stt-1704067200000-12345678",
            "tts-1704067200000-12345678",
        ]

        start_time = time.time()
        for _ in range(1000):
            for correlation_id in valid_ids:
                is_valid, _ = validate_correlation_id(correlation_id)
                assert is_valid
        end_time = time.time()

        assert (end_time - start_time) < 1.0
