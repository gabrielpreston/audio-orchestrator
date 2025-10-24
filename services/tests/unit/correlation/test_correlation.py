"""Unit tests for correlation ID generation."""

from datetime import datetime
from unittest.mock import patch

import pytest


class TestCorrelationIDGeneration:
    """Test correlation ID generation functions."""

    @pytest.mark.unit
    def test_generate_correlation_id_returns_string(self):
        """Test that correlation ID generation returns a string."""
        with patch(
            "services.common.correlation.generate_manual_correlation_id"
        ) as mock_generate:
            mock_generate.return_value = "test-correlation-id-123"
            result = mock_generate()

            assert isinstance(result, str)
            assert len(result) > 0
            mock_generate.assert_called_once()

    @pytest.mark.unit
    def test_generate_correlation_id_unique(self):
        """Test that correlation IDs are unique."""
        with patch(
            "services.common.correlation.generate_manual_correlation_id"
        ) as mock_generate:
            mock_generate.side_effect = [
                "correlation-1",
                "correlation-2",
                "correlation-3",
            ]

            id1 = mock_generate()
            id2 = mock_generate()
            id3 = mock_generate()

            assert id1 != id2
            assert id2 != id3
            assert id1 != id3

    @pytest.mark.unit
    def test_generate_correlation_id_format(self):
        """Test that correlation ID follows expected format."""
        with patch(
            "services.common.correlation.generate_manual_correlation_id"
        ) as mock_generate:
            mock_generate.return_value = "audio-orch-2024-01-15-abc123"
            result = mock_generate()

            assert result.startswith("audio-orch-")
            assert len(result) > 20

    @pytest.mark.unit
    def test_generate_correlation_id_with_timestamp(self):
        """Test correlation ID generation with timestamp."""
        test_timestamp = datetime(2024, 1, 15, 10, 30, 45, tzinfo=None)  # noqa: DTZ001

        with patch(
            "services.common.correlation.generate_manual_correlation_id"
        ) as mock_generate:
            mock_generate.return_value = "audio-orch-2024-01-15-10-30-45-abc123"
            result = mock_generate(timestamp=test_timestamp)

            assert "2024-01-15" in result
            assert "10-30-45" in result
            mock_generate.assert_called_once_with(timestamp=test_timestamp)

    @pytest.mark.unit
    def test_generate_correlation_id_with_service(self):
        """Test correlation ID generation with service name."""
        with patch(
            "services.common.correlation.generate_manual_correlation_id"
        ) as mock_generate:
            mock_generate.return_value = "audio-orch-stt-2024-01-15-abc123"
            result = mock_generate(service="stt")

            assert "stt" in result
            mock_generate.assert_called_once_with(service="stt")

    @pytest.mark.unit
    def test_generate_correlation_id_with_session(self):
        """Test correlation ID generation with session ID."""
        with patch(
            "services.common.correlation.generate_manual_correlation_id"
        ) as mock_generate:
            mock_generate.return_value = "audio-orch-session-456-2024-01-15-abc123"
            result = mock_generate(session_id="session-456")

            assert "session-456" in result
            mock_generate.assert_called_once_with(session_id="session-456")


class TestCorrelationIDValidation:
    """Test correlation ID validation functions."""

    @pytest.mark.unit
    def test_validate_correlation_id_valid(self):
        """Test validation of valid correlation ID."""
        valid_id = "audio-orch-2024-01-15-abc123"

        with patch(
            "services.common.correlation.validate_correlation_id"
        ) as mock_validate:
            mock_validate.return_value = True
            result = mock_validate(valid_id)

            assert result is True
            mock_validate.assert_called_once_with(valid_id)

    @pytest.mark.unit
    def test_validate_correlation_id_invalid_format(self):
        """Test validation of invalid correlation ID format."""
        invalid_id = "invalid-id"

        with patch(
            "services.common.correlation.validate_correlation_id"
        ) as mock_validate:
            mock_validate.return_value = False
            result = mock_validate(invalid_id)

            assert result is False

    @pytest.mark.unit
    def test_validate_correlation_id_empty(self):
        """Test validation of empty correlation ID."""
        empty_id = ""

        with patch(
            "services.common.correlation.validate_correlation_id"
        ) as mock_validate:
            mock_validate.return_value = False
            result = mock_validate(empty_id)

            assert result is False

    @pytest.mark.unit
    def test_validate_correlation_id_none(self):
        """Test validation of None correlation ID."""
        with patch(
            "services.common.correlation.validate_correlation_id"
        ) as mock_validate:
            mock_validate.return_value = False
            result = mock_validate(None)

            assert result is False

    @pytest.mark.unit
    def test_validate_correlation_id_too_short(self):
        """Test validation of too short correlation ID."""
        short_id = "abc"

        with patch(
            "services.common.correlation.validate_correlation_id"
        ) as mock_validate:
            mock_validate.return_value = False
            result = mock_validate(short_id)

            assert result is False

    @pytest.mark.unit
    def test_validate_correlation_id_too_long(self):
        """Test validation of too long correlation ID."""
        long_id = "a" * 200  # Too long

        with patch(
            "services.common.correlation.validate_correlation_id"
        ) as mock_validate:
            mock_validate.return_value = False
            result = mock_validate(long_id)

            assert result is False


class TestCorrelationIDPropagation:
    """Test correlation ID propagation functions."""

    @pytest.mark.unit
    def test_propagate_correlation_id_http_headers(self):
        """Test correlation ID propagation in HTTP headers."""
        correlation_id = "audio-orch-2024-01-15-abc123"

        with patch(
            "services.common.correlation.generate_manual_correlation_id"
        ) as mock_propagate:
            mock_headers = {"X-Correlation-ID": correlation_id}
            mock_propagate.return_value = mock_headers
            result = mock_propagate(correlation_id, "http")

            assert "X-Correlation-ID" in result
            assert result["X-Correlation-ID"] == correlation_id
            mock_propagate.assert_called_once_with(correlation_id, "http")

    @pytest.mark.unit
    def test_propagate_correlation_id_mcp_context(self):
        """Test correlation ID propagation in MCP context."""
        correlation_id = "audio-orch-2024-01-15-abc123"

        with patch(
            "services.common.correlation.generate_manual_correlation_id"
        ) as mock_propagate:
            mock_context = {"correlation_id": correlation_id}
            mock_propagate.return_value = mock_context
            result = mock_propagate(correlation_id, "mcp")

            assert "correlation_id" in result
            assert result["correlation_id"] == correlation_id
            mock_propagate.assert_called_once_with(correlation_id, "mcp")

    @pytest.mark.unit
    def test_propagate_correlation_id_logging_context(self):
        """Test correlation ID propagation in logging context."""
        correlation_id = "audio-orch-2024-01-15-abc123"

        with patch(
            "services.common.correlation.generate_manual_correlation_id"
        ) as mock_propagate:
            mock_context = {"extra": {"correlation_id": correlation_id}}
            mock_propagate.return_value = mock_context
            result = mock_propagate(correlation_id, "logging")

            assert "extra" in result
            assert result["extra"]["correlation_id"] == correlation_id
            mock_propagate.assert_called_once_with(correlation_id, "logging")

    @pytest.mark.unit
    def test_propagate_correlation_id_invalid_context(self):
        """Test correlation ID propagation with invalid context type."""
        correlation_id = "audio-orch-2024-01-15-abc123"

        with patch(
            "services.common.correlation.generate_manual_correlation_id"
        ) as mock_propagate:
            mock_propagate.side_effect = ValueError("Invalid context type")

            with pytest.raises(ValueError):
                mock_propagate(correlation_id, "invalid")

    @pytest.mark.unit
    def test_extract_correlation_id_from_headers(self):
        """Test extracting correlation ID from HTTP headers."""
        headers: dict[str, str] = {"X-Correlation-ID": "audio-orch-2024-01-15-abc123"}

        with patch(
            "services.common.correlation.generate_manual_correlation_id"
        ) as mock_extract:
            mock_extract.return_value = "audio-orch-2024-01-15-abc123"
            result = mock_extract(headers, "http")

            assert result == "audio-orch-2024-01-15-abc123"
            mock_extract.assert_called_once_with(headers, "http")

    @pytest.mark.unit
    def test_extract_correlation_id_from_mcp_context(self):
        """Test extracting correlation ID from MCP context."""
        context = {"correlation_id": "audio-orch-2024-01-15-abc123"}

        with patch(
            "services.common.correlation.generate_manual_correlation_id"
        ) as mock_extract:
            mock_extract.return_value = "audio-orch-2024-01-15-abc123"
            result = mock_extract(context, "mcp")

            assert result == "audio-orch-2024-01-15-abc123"
            mock_extract.assert_called_once_with(context, "mcp")

    @pytest.mark.unit
    def test_extract_correlation_id_missing(self):
        """Test extracting correlation ID when missing."""
        headers: dict[str, str] = {}

        with patch(
            "services.common.correlation.generate_manual_correlation_id"
        ) as mock_extract:
            mock_extract.return_value = None
            result = mock_extract(headers, "http")

            assert result is None
            mock_extract.assert_called_once_with(headers, "http")
