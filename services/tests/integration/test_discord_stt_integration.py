"""Integration tests for Discord → STT service boundary."""

import contextlib

import httpx
import pytest

from services.tests.utils.service_helpers import docker_compose_test_context


@pytest.mark.integration
class TestDiscordSTTIntegration:
    """Test Discord to STT service HTTP boundary."""

    async def test_stt_transcribe_endpoint(self, base64_audio):
        """Test STT /transcribe endpoint with real service."""
        async with (
            docker_compose_test_context(["stt"]),
            httpx.AsyncClient() as client,
        ):
            response = await client.post(
                "http://stt:9000/transcribe",
                json={"audio": base64_audio},
                timeout=30.0,
            )

            assert response.status_code == 200
            data = response.json()
            assert "text" in data
            assert "language" in data
            assert isinstance(data["text"], str)

    async def test_stt_correlation_id_propagation(
        self, base64_audio, test_correlation_id
    ):
        """Test correlation ID propagation through STT service."""
        async with (
            docker_compose_test_context(["stt"]),
            httpx.AsyncClient() as client,
        ):
            response = await client.post(
                "http://stt:9000/transcribe",
                json={"audio": base64_audio, "correlation_id": test_correlation_id},
                timeout=30.0,
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("correlation_id") == test_correlation_id

    async def test_stt_error_handling_invalid_audio(self):
        """Test STT error handling with invalid audio."""
        async with (
            docker_compose_test_context(["stt"]),
            httpx.AsyncClient() as client,
        ):
            response = await client.post(
                "http://stt:9000/transcribe",
                json={"audio": "invalid-base64"},
                timeout=10.0,
            )

            assert response.status_code in [400, 422]

    async def test_stt_timeout_handling(self, base64_audio):
        """Test STT timeout behavior."""
        async with (
            docker_compose_test_context(["stt"]),
            httpx.AsyncClient() as client,
        ):
            with contextlib.suppress(httpx.TimeoutException):
                await client.post(
                    "http://stt:9000/transcribe",
                    json={"audio": base64_audio},
                    timeout=0.1,  # Very short timeout
                )

    async def test_stt_health_endpoint(self):
        """Test STT health endpoint accessibility."""
        async with (
            docker_compose_test_context(["stt"]),
            httpx.AsyncClient() as client,
        ):
            # Test live endpoint
            response = await client.get("http://stt:9000/health/live", timeout=5.0)
            assert response.status_code == 200

            # Test ready endpoint
            response = await client.get("http://stt:9000/health/ready", timeout=5.0)
            assert response.status_code in [200, 503]  # May be ready or not ready

            if response.status_code == 200:
                data = response.json()
                assert data["service"] == "stt"
                assert "status" in data
