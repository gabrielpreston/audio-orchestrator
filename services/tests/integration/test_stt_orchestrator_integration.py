"""Integration tests for STT → Orchestrator service boundary."""

import httpx
import pytest


@pytest.mark.integration
class TestSTTOrchestratorIntegration:
    """Test STT to Orchestrator service HTTP boundary."""

    async def test_orchestrator_process_transcript(
        self,
        test_transcript,
        test_auth_token,
        test_guild_id,
        test_channel_id,
        test_user_id,
    ):
        """Test orchestrator transcript processing endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://orchestrator:8000/process",
                json={
                    "guild_id": test_guild_id,
                    "channel_id": test_channel_id,
                    "user_id": test_user_id,
                    "transcript": test_transcript,
                },
                headers={"Authorization": f"Bearer {test_auth_token}"},
                timeout=60.0,
            )

            assert response.status_code == 200
            data = response.json()
            assert "response" in data or "text" in data

    async def test_orchestrator_authentication(self, test_transcript):
        """Test orchestrator authentication requirements."""
        async with httpx.AsyncClient() as client:
            # Test without auth token
            response = await client.post(
                "http://orchestrator:8000/process",
                json={"transcript": test_transcript},
                timeout=10.0,
            )

            assert response.status_code == 401

    async def test_orchestrator_health_endpoint(self):
        """Test orchestrator health endpoint accessibility."""
        async with httpx.AsyncClient() as client:
            # Test live endpoint
            response = await client.get(
                "http://orchestrator:8000/health/live", timeout=5.0
            )
            assert response.status_code == 200

            # Test ready endpoint
            response = await client.get(
                "http://orchestrator:8000/health/ready", timeout=5.0
            )
            assert response.status_code in [200, 503]  # May be ready or not ready

            if response.status_code == 200:
                data = response.json()
                assert data["service"] == "orchestrator"
                assert "status" in data

    async def test_orchestrator_correlation_id_propagation(
        self,
        test_transcript,
        test_auth_token,
        test_correlation_id,
        test_guild_id,
        test_channel_id,
        test_user_id,
    ):
        """Test correlation ID propagation through orchestrator."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://orchestrator:8000/process",
                json={
                    "guild_id": test_guild_id,
                    "channel_id": test_channel_id,
                    "user_id": test_user_id,
                    "transcript": test_transcript,
                    "correlation_id": test_correlation_id,
                },
                headers={"Authorization": f"Bearer {test_auth_token}"},
                timeout=60.0,
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("correlation_id") == test_correlation_id
