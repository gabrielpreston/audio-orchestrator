"""Integration tests for Discord REST API endpoints."""

import pytest
import httpx


@pytest.mark.integration
class TestDiscordRestAPI:
    """Test Discord REST API endpoints."""

    async def test_capabilities_endpoint(self):
        """Test GET /api/v1/capabilities endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://discord:8001/api/v1/capabilities", timeout=10.0
            )

            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "discord"
            assert "capabilities" in data
            assert len(data["capabilities"]) > 0

            # Check specific capabilities
            capability_names = [cap["name"] for cap in data["capabilities"]]
            assert "send_message" in capability_names
            assert "transcript_notification" in capability_names

    async def test_send_message_endpoint(self):
        """Test POST /api/v1/messages endpoint."""
        async with httpx.AsyncClient() as client:
            request_data = {
                "channel_id": "test_channel_123",
                "content": "Test message from integration test",
                "correlation_id": "test_correlation_456",
                "metadata": {"source": "test"},
            }

            response = await client.post(
                "http://discord:8001/api/v1/messages", json=request_data, timeout=30.0
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "message_id" in data
            assert data["correlation_id"] == request_data["correlation_id"]

    async def test_transcript_notification_endpoint(self):
        """Test POST /api/v1/notifications/transcript endpoint."""
        async with httpx.AsyncClient() as client:
            request_data = {
                "transcript": "Hello, this is a test transcript",
                "user_id": "test_user_789",
                "channel_id": "test_channel_123",
                "correlation_id": "test_correlation_789",
                "metadata": {"source": "test"},
            }

            response = await client.post(
                "http://discord:8001/api/v1/notifications/transcript",
                json=request_data,
                timeout=30.0,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["correlation_id"] == request_data["correlation_id"]

    async def test_send_message_error_handling(self):
        """Test error handling in send message endpoint."""
        async with httpx.AsyncClient() as client:
            # Test with invalid request data
            invalid_request = {
                "channel_id": "",  # Empty channel ID
                "content": "Test message",
            }

            response = await client.post(
                "http://discord:8001/api/v1/messages",
                json=invalid_request,
                timeout=30.0,
            )

            # Should handle gracefully
            assert response.status_code in [200, 400, 422]

    async def test_transcript_notification_error_handling(self):
        """Test error handling in transcript notification endpoint."""
        async with httpx.AsyncClient() as client:
            # Test with invalid request data
            invalid_request = {
                "transcript": "",  # Empty transcript
                "user_id": "test_user",
                "channel_id": "test_channel",
            }

            response = await client.post(
                "http://discord:8001/api/v1/notifications/transcript",
                json=invalid_request,
                timeout=30.0,
            )

            # Should handle gracefully
            assert response.status_code in [200, 400, 422]

    async def test_correlation_id_propagation(self):
        """Test correlation ID propagation through REST API."""
        async with httpx.AsyncClient() as client:
            correlation_id = "test-correlation-propagation-456"

            # Test message sending
            message_request = {
                "channel_id": "test_channel",
                "content": "Test correlation ID propagation",
                "correlation_id": correlation_id,
            }

            response = await client.post(
                "http://discord:8001/api/v1/messages",
                json=message_request,
                timeout=30.0,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["correlation_id"] == correlation_id

            # Test transcript notification
            transcript_request = {
                "transcript": "Test correlation ID propagation",
                "user_id": "test_user",
                "channel_id": "test_channel",
                "correlation_id": correlation_id,
            }

            response = await client.post(
                "http://discord:8001/api/v1/notifications/transcript",
                json=transcript_request,
                timeout=30.0,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["correlation_id"] == correlation_id

    async def test_concurrent_requests(self):
        """Test handling of concurrent requests."""
        import asyncio

        async def make_message_request(client: httpx.AsyncClient, request_id: int):
            request_data = {
                "channel_id": f"channel_{request_id}",
                "content": f"Concurrent message {request_id}",
                "correlation_id": f"concurrent_test_{request_id}",
            }

            response = await client.post(
                "http://discord:8001/api/v1/messages", json=request_data, timeout=30.0
            )
            return response.status_code == 200

        async with httpx.AsyncClient() as client:
            # Make 5 concurrent requests
            tasks = [make_message_request(client, i) for i in range(5)]
            results = await asyncio.gather(*tasks)

            # All requests should succeed
            assert all(results)
