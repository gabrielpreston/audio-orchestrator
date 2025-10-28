"""Integration tests for Discord service HTTP API endpoints."""

import contextlib

import httpx
import pytest


@pytest.mark.integration
class TestDiscordServiceIntegration:
    """Test Discord service HTTP API endpoints."""

    async def test_discord_http_api_endpoints(self):
        """Test Discord REST API endpoints: /api/v1/messages, /api/v1/notifications/transcript, /api/v1/capabilities"""
        async with httpx.AsyncClient() as client:
            # Test /api/v1/capabilities endpoint (no auth required)
            response = await client.get("http://discord:8001/api/v1/capabilities")
            assert response.status_code == 200
            data = response.json()
            assert "capabilities" in data
            assert len(data["capabilities"]) > 0

            # Test /api/v1/messages endpoint
            send_message_data = {
                "channel_id": "987654321",
                "content": "Test message from integration test",
                "correlation_id": "test_correlation_123",
            }
            response = await client.post(
                "http://discord:8001/api/v1/messages",
                json=send_message_data,
                timeout=30.0,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "message_id" in data

            # Test /api/v1/notifications/transcript endpoint
            transcript_data = {
                "transcript": "Test transcript",
                "user_id": "12345",
                "channel_id": "987654321",
                "correlation_id": "test-correlation-123",
            }
            response = await client.post(
                "http://discord:8001/api/v1/notifications/transcript",
                json=transcript_data,
                timeout=30.0,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    async def test_discord_health_endpoints(self):
        """Test Discord service health endpoints."""
        async with httpx.AsyncClient() as client:
            # Test live endpoint
            response = await client.get("http://discord:8001/health/live", timeout=15.0)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "alive"
            assert data["service"] == "discord"

            # Test ready endpoint
            response = await client.get(
                "http://discord:8001/health/ready", timeout=15.0
            )
            assert response.status_code in [200, 503]  # May be ready or not ready
            if response.status_code == 200:
                data = response.json()
                assert data["service"] == "discord"
                assert "components" in data

    async def test_discord_stt_orchestrator_chain(
        self,
        realistic_voice_audio_multipart,
        test_voice_context,
        test_voice_transcript,
        test_voice_correlation_id,
        test_auth_token,
    ):
        """Test: Mock Discord → Real STT → Real Orchestrator"""
        async with httpx.AsyncClient() as client:
            # Step 1: STT transcription (using multipart form data)
            stt_response = await client.post(
                "http://stt:9000/transcribe",
                files=realistic_voice_audio_multipart,
                timeout=30.0,
            )
            assert stt_response.status_code == 200
            stt_data = stt_response.json()
            assert "text" in stt_data
            transcript = stt_data["text"]

            # Step 2: Orchestrator processing
            orch_response = await client.post(
                "http://orchestrator-enhanced:8200/api/v1/transcripts",
                json={
                    "guild_id": test_voice_context["guild_id"],
                    "channel_id": test_voice_context["channel_id"],
                    "user_id": test_voice_context["user_id"],
                    "transcript": transcript,
                    "correlation_id": test_voice_correlation_id,
                },
                timeout=60.0,
            )
            assert orch_response.status_code == 200
            orch_data = orch_response.json()
            assert "status" in orch_data

    async def test_discord_correlation_id_propagation(
        self, test_voice_context, test_voice_transcript, test_voice_correlation_id
    ):
        """Test correlation ID propagation through Discord service."""
        async with httpx.AsyncClient() as client:
            transcript_data = {
                "guild_id": test_voice_context["guild_id"],
                "channel_id": test_voice_context["channel_id"],
                "user_id": test_voice_context["user_id"],
                "transcript": test_voice_transcript,
                "correlation_id": test_voice_correlation_id,
            }

            response = await client.post(
                "http://discord:8001/api/v1/notifications/transcript",
                json=transcript_data,
                timeout=30.0,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["correlation_id"] == test_voice_correlation_id

    async def test_discord_error_handling(self):
        """Test Discord service error handling."""
        async with httpx.AsyncClient() as client:
            # Test with invalid JSON
            response = await client.post(
                "http://discord:8001/api/v1/messages",
                json={"invalid": "data"},
                timeout=10.0,
            )
            # Should handle gracefully - either 200 with error or 422
            assert response.status_code in [200, 422]

    async def test_discord_timeout_handling(self):
        """Test Discord service timeout behavior."""
        async with httpx.AsyncClient() as client:
            # Test with very short timeout
            with contextlib.suppress(httpx.TimeoutException):
                await client.post(
                    "http://discord:8001/api/v1/messages",
                    json={
                        "guild_id": "123456789",
                        "channel_id": "987654321",
                        "message": "Test message",
                    },
                    timeout=0.1,  # Very short timeout
                )
