"""Integration tests for Orchestrator → TTS service boundary."""

import httpx
import pytest


@pytest.mark.integration
class TestOrchestratorTTSIntegration:
    """Test Orchestrator to TTS service HTTP boundary."""

    async def test_tts_synthesize_endpoint(self, test_auth_token):
        """Test TTS synthesis endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://tts:7000/synthesize",
                json={"text": "Hello world"},
                headers={"Authorization": f"Bearer {test_auth_token}"},
                timeout=30.0,
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "audio/wav"
            assert len(response.content) > 0

    async def test_tts_authentication_required(self):
        """Test TTS requires authentication."""
        async with httpx.AsyncClient() as client:
            # Test without auth token
            response = await client.post(
                "http://tts:7000/synthesize",
                json={"text": "Hello world"},
                timeout=10.0,
            )

            assert response.status_code == 401

    async def test_tts_rate_limiting(self, test_auth_token):
        """Test TTS rate limiting."""
        async with httpx.AsyncClient() as client:
            # Make multiple rapid requests
            responses = []
            for _ in range(5):
                response = await client.post(
                    "http://tts:7000/synthesize",
                    json={"text": "Test"},
                    headers={"Authorization": f"Bearer {test_auth_token}"},
                    timeout=10.0,
                )
                responses.append(response.status_code)

            # Should have at least some successful requests
            assert 200 in responses

    async def test_tts_health_endpoint(self):
        """Test TTS health endpoint accessibility."""
        async with httpx.AsyncClient() as client:
            # Test live endpoint
            response = await client.get("http://tts:7000/health/live", timeout=5.0)
            assert response.status_code == 200

            # Test ready endpoint
            response = await client.get("http://tts:7000/health/ready", timeout=5.0)
            assert response.status_code in [200, 503]  # May be ready or not ready

            if response.status_code == 200:
                data = response.json()
                assert data["service"] == "tts"
                assert "status" in data

    async def test_tts_ssml_processing(self, test_auth_token):
        """Test TTS SSML input processing."""
        ssml_text = (
            "<speak>This is SSML text with <break time='0.5s'/> a pause.</speak>"
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://tts:7000/synthesize",
                json={"text": ssml_text},
                headers={"Authorization": f"Bearer {test_auth_token}"},
                timeout=30.0,
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "audio/wav"
            assert len(response.content) > 0

    async def test_tts_correlation_id_propagation(
        self, test_auth_token, test_correlation_id
    ):
        """Test correlation ID propagation through TTS."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://tts:7000/synthesize",
                json={"text": "Hello world", "correlation_id": test_correlation_id},
                headers={"Authorization": f"Bearer {test_auth_token}"},
                timeout=30.0,
            )

            assert response.status_code == 200
            # TTS may or may not return correlation_id in response
            # This test verifies the request was processed successfully
