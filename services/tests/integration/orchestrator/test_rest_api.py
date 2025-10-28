"""Integration tests for Orchestrator REST API endpoints."""

import pytest
import httpx


@pytest.mark.integration
class TestOrchestratorRestAPI:
    """Test Orchestrator REST API endpoints."""

    async def test_transcript_processing_endpoint(self):
        """Test POST /api/v1/transcripts endpoint."""
        async with httpx.AsyncClient() as client:
            # Test successful transcript processing
            request_data = {
                "transcript": "Hello, how are you today?",
                "user_id": "test_user_123",
                "channel_id": "test_channel_456",
                "correlation_id": "test_correlation_789",
                "metadata": {"source": "test"},
            }

            response = await client.post(
                "http://orchestrator:8200/api/v1/transcripts",
                json=request_data,
                timeout=30.0,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "response_text" in data
            assert data["correlation_id"] == request_data["correlation_id"]

    async def test_capabilities_endpoint(self):
        """Test GET /api/v1/capabilities endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://orchestrator:8200/api/v1/capabilities", timeout=10.0
            )

            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "orchestrator"
            assert "capabilities" in data
            assert len(data["capabilities"]) > 0

            # Check specific capabilities
            capability_names = [cap["name"] for cap in data["capabilities"]]
            assert "transcript_processing" in capability_names
            assert "discord_message_sending" in capability_names

    async def test_status_endpoint(self):
        """Test GET /api/v1/status endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://orchestrator:8200/api/v1/status", timeout=10.0
            )

            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "orchestrator"
            assert data["status"] == "healthy"
            assert "connections" in data
            assert len(data["connections"]) > 0

            # Check specific connections
            connection_names = [conn["service"] for conn in data["connections"]]
            assert "discord" in connection_names
            assert "flan" in connection_names

    async def test_transcript_processing_error_handling(self):
        """Test error handling in transcript processing."""
        async with httpx.AsyncClient() as client:
            # Test with invalid request data
            invalid_request = {
                "transcript": "",  # Empty transcript
                "user_id": "test_user",
                "channel_id": "test_channel",
            }

            response = await client.post(
                "http://orchestrator:8200/api/v1/transcripts",
                json=invalid_request,
                timeout=30.0,
            )

            # Should handle gracefully
            assert response.status_code in [200, 400, 422]

    async def test_correlation_id_propagation(self):
        """Test correlation ID propagation through REST API."""
        async with httpx.AsyncClient() as client:
            correlation_id = "test-correlation-propagation-123"
            request_data = {
                "transcript": "Test correlation ID propagation",
                "user_id": "test_user",
                "channel_id": "test_channel",
                "correlation_id": correlation_id,
            }

            response = await client.post(
                "http://orchestrator:8200/api/v1/transcripts",
                json=request_data,
                timeout=30.0,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["correlation_id"] == correlation_id

    async def test_concurrent_requests(self):
        """Test handling of concurrent requests."""
        import asyncio

        async def make_request(client: httpx.AsyncClient, request_id: int):
            request_data = {
                "transcript": f"Concurrent request {request_id}",
                "user_id": f"user_{request_id}",
                "channel_id": f"channel_{request_id}",
                "correlation_id": f"concurrent_test_{request_id}",
            }

            response = await client.post(
                "http://orchestrator:8200/api/v1/transcripts",
                json=request_data,
                timeout=30.0,
            )
            return response.status_code == 200

        async with httpx.AsyncClient() as client:
            # Make 5 concurrent requests
            tasks = [make_request(client, i) for i in range(5)]
            results = await asyncio.gather(*tasks)

            # All requests should succeed
            assert all(results)
