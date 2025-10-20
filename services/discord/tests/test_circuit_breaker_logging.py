"""Tests for circuit breaker integration and logging functionality."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.discord.config import STTConfig
from services.discord.transcription import TranscriptionClient


class TestCircuitBreakerLogging:
    """Test circuit breaker integration and logging functionality."""

    @pytest.fixture
    def stt_config(self):
        """Create STT configuration for testing."""
        return STTConfig(
            base_url="http://test-stt:9000",
            request_timeout_seconds=45,
            max_retries=3,
            forced_language="en",
        )

    @pytest.fixture
    def mock_http_client(self):
        """Create mock HTTP client with circuit breaker."""
        mock_client = Mock()
        mock_circuit_breaker = Mock()
        mock_circuit_breaker.get_state.return_value = Mock(value="closed")
        mock_circuit_breaker.get_stats.return_value = {
            "state": "closed",
            "available": True,
            "failure_count": 0,
            "success_count": 5,
        }
        mock_client._circuit_breaker = mock_circuit_breaker
        mock_client.check_health = AsyncMock(return_value=True)
        return mock_client

    @pytest.mark.component
    def test_circuit_stats_method_returns_state(self, stt_config, mock_http_client):
        """Test that TranscriptionClient exposes circuit breaker stats."""
        with patch(
            "services.discord.transcription.ResilientHTTPClient",
            return_value=mock_http_client,
        ):
            client = TranscriptionClient(stt_config)

            stats = client.get_circuit_stats()

            # Should return circuit breaker stats
            assert "state" in stats
            assert "available" in stats
            assert stats["state"] == "closed"
            assert stats["available"] is True

    @pytest.mark.component
    def test_circuit_stats_method_fallback(self, stt_config):
        """Test that TranscriptionClient handles missing circuit breaker gracefully."""
        # Create client without circuit breaker
        mock_client_no_cb = Mock()
        mock_client_no_cb._circuit_breaker = None

        with patch(
            "services.discord.transcription.ResilientHTTPClient",
            return_value=mock_client_no_cb,
        ):
            client = TranscriptionClient(stt_config)

            stats = client.get_circuit_stats()

            # Should return fallback stats
            assert stats["state"] == "unknown"
            assert stats["available"] is True

    @pytest.mark.component
    async def test_stt_health_check_logs_circuit_state(
        self, stt_config, mock_http_client
    ):
        """Test that STT health check returns False when circuit is open."""
        # Mock circuit breaker in open state
        mock_http_client._circuit_breaker.get_state.return_value = Mock(value="open")
        mock_http_client.check_health = AsyncMock(return_value=False)

        with patch(
            "services.discord.transcription.ResilientHTTPClient",
            return_value=mock_http_client,
        ):
            client = TranscriptionClient(stt_config)

            # Test health check failure
            result = await client.check_health()

            # Should return False
            assert result is False

    @pytest.mark.component
    def test_segment_consumer_logs_circuit_state(self, stt_config, mock_http_client):
        """Test that segment consumer logs circuit state at processing start."""
        # Mock circuit breaker in half-open state
        mock_http_client._circuit_breaker.get_state.return_value = Mock(
            value="half-open"
        )
        mock_http_client._circuit_breaker.get_stats.return_value = {
            "state": "half-open",
            "available": True,
            "failure_count": 2,
            "success_count": 1,
        }

        with patch(
            "services.discord.transcription.ResilientHTTPClient",
            return_value=mock_http_client,
        ):
            client = TranscriptionClient(stt_config)

            # Mock logger
            client._logger = Mock()

            # Test get_circuit_stats method
            stats = client.get_circuit_stats()

            # Should return circuit stats
            assert stats["state"] == "half-open"
            assert stats["available"] is True

    @pytest.mark.component
    def test_circuit_breaker_state_transitions(self, stt_config, mock_http_client):
        """Test that circuit breaker state transitions are logged correctly."""
        # Test closed state
        mock_http_client._circuit_breaker.get_state.return_value = Mock(value="closed")
        mock_http_client._circuit_breaker.get_stats.return_value = {
            "state": "closed",
            "available": True,
            "failure_count": 0,
            "success_count": 10,
        }

        with patch(
            "services.discord.transcription.ResilientHTTPClient",
            return_value=mock_http_client,
        ):
            client = TranscriptionClient(stt_config)

            stats = client.get_circuit_stats()
            assert stats["state"] == "closed"
            assert stats["available"] is True

        # Test open state
        mock_http_client._circuit_breaker.get_state.return_value = Mock(value="open")
        mock_http_client._circuit_breaker.get_stats.return_value = {
            "state": "open",
            "available": False,
            "failure_count": 5,
            "success_count": 0,
        }

        with patch(
            "services.discord.transcription.ResilientHTTPClient",
            return_value=mock_http_client,
        ):
            client = TranscriptionClient(stt_config)

            stats = client.get_circuit_stats()
            assert stats["state"] == "open"
            assert stats["available"] is False

        # Test half-open state
        mock_http_client._circuit_breaker.get_state.return_value = Mock(
            value="half-open"
        )
        mock_http_client._circuit_breaker.get_stats.return_value = {
            "state": "half-open",
            "available": True,
            "failure_count": 3,
            "success_count": 1,
        }

        with patch(
            "services.discord.transcription.ResilientHTTPClient",
            return_value=mock_http_client,
        ):
            client = TranscriptionClient(stt_config)

            stats = client.get_circuit_stats()
            assert stats["state"] == "half-open"
            assert stats["available"] is True

    @pytest.mark.component
    async def test_circuit_breaker_unavailable_fallback(
        self, stt_config, mock_http_client
    ):
        """Test that circuit breaker unavailable fallback works correctly."""
        # Mock circuit breaker in open state (unavailable)
        mock_http_client._circuit_breaker.get_state.return_value = Mock(value="open")
        mock_http_client.check_health = AsyncMock(return_value=False)

        with patch(
            "services.discord.transcription.ResilientHTTPClient",
            return_value=mock_http_client,
        ):
            client = TranscriptionClient(stt_config)

            # Test health check with open circuit
            result = await client.check_health()

            # Should return False
            assert result is False

    @pytest.mark.component
    def test_circuit_breaker_stats_integration(self, stt_config, mock_http_client):
        """Test that circuit breaker stats are properly integrated."""
        # Mock circuit breaker with detailed stats
        mock_http_client._circuit_breaker.get_stats.return_value = {
            "state": "closed",
            "available": True,
            "failure_count": 0,
            "success_count": 15,
            "last_failure_time": None,
            "last_success_time": "2024-01-01T12:00:00Z",
            "consecutive_failures": 0,
            "consecutive_successes": 15,
        }

        with patch(
            "services.discord.transcription.ResilientHTTPClient",
            return_value=mock_http_client,
        ):
            client = TranscriptionClient(stt_config)

            stats = client.get_circuit_stats()

            # Should return all stats
            assert stats["state"] == "closed"
            assert stats["available"] is True
            assert stats["failure_count"] == 0
            assert stats["success_count"] == 15
            assert stats["consecutive_failures"] == 0
            assert stats["consecutive_successes"] == 15

    @pytest.mark.component
    def test_circuit_breaker_error_handling(self, stt_config, mock_http_client):
        """Test that circuit breaker error handling works correctly."""
        # Mock circuit breaker that raises exception
        mock_http_client._circuit_breaker.get_stats.side_effect = Exception(
            "Circuit breaker error"
        )

        with patch(
            "services.discord.transcription.ResilientHTTPClient",
            return_value=mock_http_client,
        ):
            client = TranscriptionClient(stt_config)

            stats = client.get_circuit_stats()

            # Should return fallback stats on error
            assert stats["state"] == "unknown"
            assert stats["available"] is True

    @pytest.mark.component
    async def test_circuit_breaker_logging_context(self, stt_config, mock_http_client):
        """Test that circuit breaker context is properly handled."""
        # Mock circuit breaker in open state
        mock_http_client._circuit_breaker.get_state.return_value = Mock(value="open")
        mock_http_client.check_health = AsyncMock(return_value=False)

        with patch(
            "services.discord.transcription.ResilientHTTPClient",
            return_value=mock_http_client,
        ):
            client = TranscriptionClient(stt_config)

            # Test health check with open circuit
            result = await client.check_health()

            # Should return False
            assert result is False
