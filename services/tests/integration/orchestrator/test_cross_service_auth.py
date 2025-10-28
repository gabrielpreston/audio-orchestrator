"""Integration tests for cross-service authentication."""

import httpx
import pytest


@pytest.mark.integration
class TestCrossServiceAuthentication:
    """Test authentication between services."""

    async def test_orchestrator_llm_auth_flow(self, test_auth_token):
        """Test Bearer token auth: Orchestrator → LLM."""
        async with httpx.AsyncClient() as client:
            # Test with valid auth token
            response = await client.post(
                "http://flan:8100/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "Test message"}],
                    "max_tokens": 50,
                },
                headers={"Authorization": f"Bearer {test_auth_token}"},
                timeout=30.0,
            )
            assert response.status_code == 200
            data = response.json()
            assert "choices" in data

    async def test_orchestrator_tts_auth_flow(self, test_auth_token):
        """Test Bearer token auth: Orchestrator → TTS."""
        async with httpx.AsyncClient() as client:
            # Test with valid auth token
            response = await client.post(
                "http://bark:7100/synthesize",
                json={
                    "text": "Test synthesis",
                    "voice": "en_US-lessac-medium",
                    "correlation_id": "test-correlation-123",
                },
                headers={"Authorization": f"Bearer {test_auth_token}"},
                timeout=30.0,
            )
            assert response.status_code in [
                200,
                422,
            ], f"TTS synthesis failed: {response.status_code} - {response.text}"
            # Note: 422 may occur if voice parameter is invalid
            # Should return audio data
            assert response.headers["content-type"] == "audio/wav"

    async def test_unauthorized_access_rejected(self):
        """Test 401 responses without auth tokens."""
        async with httpx.AsyncClient() as client:
            # Test LLM without auth
            response = await client.post(
                "http://flan:8100/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "Test message"}],
                },
                timeout=10.0,
            )
            assert response.status_code == 401

            # Test TTS without auth
            response = await client.post(
                "http://bark:7100/synthesize",
                json={
                    "text": "Test synthesis",
                    "voice": "en_US-lessac-medium",
                },
                timeout=10.0,
            )
            assert response.status_code == 401

    async def test_discord_rest_endpoints_no_auth(self):
        """Test Discord REST API endpoints are public (no auth required)."""
        async with httpx.AsyncClient() as client:
            # Test Discord REST API endpoints without auth
            endpoints = [
                ("GET", "http://discord:8001/api/v1/capabilities"),
                ("POST", "http://discord:8001/api/v1/messages"),
                ("POST", "http://discord:8001/api/v1/notifications/transcript"),
            ]

            for method, endpoint in endpoints:
                if method == "GET":
                    response = await client.get(endpoint, timeout=15.0)
                else:
                    response = await client.post(
                        endpoint,
                        json={"test": "data"},
                        timeout=15.0,
                    )
                # Should not require authentication for internal service communication
                assert response.status_code in [200, 422]  # 422 for invalid data is OK

    async def test_invalid_auth_token_rejected(self):
        """Test invalid auth tokens are rejected."""
        async with httpx.AsyncClient() as client:
            # Test with invalid token
            response = await client.post(
                "http://flan:8100/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "Test message"}],
                },
                headers={"Authorization": "Bearer invalid-token"},
                timeout=10.0,
            )
            assert response.status_code == 401

            # Test with malformed auth header
            response = await client.post(
                "http://bark:7100/synthesize",
                json={
                    "text": "Test synthesis",
                    "voice": "en_US-lessac-medium",
                },
                headers={"Authorization": "InvalidFormat"},
                timeout=10.0,
            )
            assert response.status_code == 401

    async def test_missing_auth_header_rejected(self):
        """Test missing auth headers are rejected."""
        async with httpx.AsyncClient() as client:
            # Test LLM without Authorization header
            response = await client.post(
                "http://flan:8100/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "Test message"}],
                },
                timeout=10.0,
            )
            assert response.status_code == 401

            # Test TTS without Authorization header
            response = await client.post(
                "http://bark:7100/synthesize",
                json={
                    "text": "Test synthesis",
                    "voice": "en_US-lessac-medium",
                },
                timeout=10.0,
            )
            assert response.status_code == 401

    async def test_auth_token_propagation_through_pipeline(
        self,
        test_auth_token,
        test_voice_context,
        test_voice_transcript,
        test_voice_correlation_id,
    ):
        """Test auth token propagation through voice pipeline."""
        async with httpx.AsyncClient() as client:
            # Test complete pipeline with auth
            # Step 1: STT (no auth required)
            stt_response = await client.post(
                "http://stt:9000/transcribe",
                files={"file": ("test.wav", b"fake audio data", "audio/wav")},
                timeout=30.0,
            )
            # STT may fail with fake data, but should not be auth-related
            assert stt_response.status_code in [
                200,
                400,
                422,
                500,
            ], f"STT with fake audio: {stt_response.status_code}"
            # Note: 500 is acceptable for malformed audio data

            # Step 2: Orchestrator (no auth required for REST API endpoints)
            orch_response = await client.post(
                "http://orchestrator:8200/api/v1/transcripts",
                json={
                    "guild_id": test_voice_context["guild_id"],
                    "channel_id": test_voice_context["channel_id"],
                    "user_id": test_voice_context["user_id"],
                    "transcript": test_voice_transcript,
                    "correlation_id": test_voice_correlation_id,
                },
                timeout=60.0,
            )
            assert orch_response.status_code == 200

            # Step 3: TTS (requires auth)
            tts_response = await client.post(
                "http://bark:7100/synthesize",
                json={
                    "text": "Test response",
                    "voice": "en_US-lessac-medium",
                    "correlation_id": test_voice_correlation_id,
                },
                headers={"Authorization": f"Bearer {test_auth_token}"},
                timeout=30.0,
            )
            assert tts_response.status_code == 200

    async def test_auth_error_responses(self):
        """Test auth error response format."""
        async with httpx.AsyncClient() as client:
            # Test LLM auth error response
            response = await client.post(
                "http://flan:8100/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "Test message"}],
                },
                timeout=10.0,
            )
            assert response.status_code == 401
            data = response.json()
            assert "detail" in data

            # Test TTS auth error response
            response = await client.post(
                "http://bark:7100/synthesize",
                json={
                    "text": "Test synthesis",
                    "voice": "en_US-lessac-medium",
                },
                timeout=10.0,
            )
            assert response.status_code == 401
            data = response.json()
            assert "detail" in data
