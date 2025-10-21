"""Integration tests for MCP (Model Context Protocol) functionality."""

import contextlib

import httpx
import pytest


@pytest.mark.integration
class TestMCPIntegration:
    """Test MCP integration across services."""

    async def test_mcp_tool_discovery(self):
        """Test /mcp/tools endpoint returns Discord tools."""
        async with httpx.AsyncClient() as client:
            # Test Discord MCP tools endpoint
            response = await client.get("http://discord:8001/mcp/tools")
            assert response.status_code == 200
            data = response.json()
            assert "tools" in data
            assert len(data["tools"]) > 0

            # Verify expected Discord tools are present
            tool_names = [tool["name"] for tool in data["tools"]]
            assert "discord.send_message" in tool_names
            assert "discord.transcript" in tool_names

            # Test Orchestrator MCP tools endpoint
            response = await client.get("http://orchestrator:8000/mcp/tools")
            assert response.status_code == 200
            data = response.json()
            assert "tools" in data

    async def test_mcp_tool_execution_discord_send_message(
        self, test_mcp_tool_request, test_auth_token
    ):
        """Test discord.send_message tool via orchestrator."""
        async with httpx.AsyncClient() as client:
            # Test tool execution through orchestrator
            response = await client.post(
                "http://orchestrator:8000/mcp/tools",
                json=test_mcp_tool_request,
                headers={"Authorization": f"Bearer {test_auth_token}"},
                timeout=30.0,
            )
            assert response.status_code == 200
            data = response.json()
            assert "result" in data
            assert data["tool"] == test_mcp_tool_request["tool"]

    async def test_mcp_no_authentication_for_internal_endpoints(self):
        """Test MCP HTTP endpoints are public for internal services."""
        async with httpx.AsyncClient() as client:
            # Test Discord MCP endpoints without auth
            endpoints = [
                "http://discord:8001/mcp/tools",
                "http://discord:8001/mcp/send_message",
                "http://discord:8001/mcp/transcript",
            ]

            for endpoint in endpoints:
                if endpoint.endswith("/tools"):
                    response = await client.get(endpoint)
                else:
                    response = await client.post(
                        endpoint,
                        json={"test": "data"},
                        timeout=5.0,
                    )
                # Should not require authentication for internal service communication
                assert response.status_code in [200, 422]  # 422 for invalid data is OK

    async def test_mcp_tool_schema_validation(self):
        """Test MCP tool schema validation."""
        async with httpx.AsyncClient() as client:
            # Test with valid tool request
            valid_request = {
                "tool": "discord.send_message",
                "args": {
                    "guild_id": "123456789",
                    "channel_id": "987654321",
                    "message": "Valid test message",
                },
            }

            response = await client.post(
                "http://orchestrator:8000/mcp/tools",
                json=valid_request,
                timeout=30.0,
            )
            assert response.status_code == 200

            # Test with invalid tool request
            invalid_request = {"tool": "nonexistent.tool", "args": {}}

            response = await client.post(
                "http://orchestrator:8000/mcp/tools",
                json=invalid_request,
                timeout=30.0,
            )
            assert response.status_code in [400, 404]  # Should reject invalid tool

    async def test_mcp_correlation_id_propagation(
        self, test_voice_context, test_voice_transcript, test_voice_correlation_id
    ):
        """Test correlation ID propagation through MCP."""
        async with httpx.AsyncClient() as client:
            # Test transcript with correlation ID
            transcript_data = {
                "guild_id": test_voice_context["guild_id"],
                "channel_id": test_voice_context["channel_id"],
                "user_id": test_voice_context["user_id"],
                "transcript": test_voice_transcript,
                "correlation_id": test_voice_correlation_id,
            }

            response = await client.post(
                "http://discord:8001/mcp/transcript",
                json=transcript_data,
                timeout=30.0,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["correlation_id"] == test_voice_correlation_id

    async def test_mcp_error_handling(self):
        """Test MCP error handling and recovery."""
        async with httpx.AsyncClient() as client:
            # Test with malformed JSON
            response = await client.post(
                "http://orchestrator:8000/mcp/tools",
                data="invalid json",
                headers={"Content-Type": "application/json"},
                timeout=10.0,
            )
            assert response.status_code == 422

            # Test with missing required fields
            incomplete_request = {
                "tool": "discord.send_message",
                # Missing args
            }

            response = await client.post(
                "http://orchestrator:8000/mcp/tools",
                json=incomplete_request,
                timeout=10.0,
            )
            assert response.status_code in [400, 422]

    async def test_mcp_timeout_handling(self):
        """Test MCP timeout behavior."""
        async with httpx.AsyncClient() as client:
            # Test with very short timeout
            with contextlib.suppress(httpx.TimeoutException):
                await client.post(
                    "http://orchestrator:8000/mcp/tools",
                    json={
                        "tool": "discord.send_message",
                        "args": {
                            "guild_id": "123456789",
                            "channel_id": "987654321",
                            "message": "Test message",
                        },
                    },
                    timeout=0.1,  # Very short timeout
                )

    async def test_mcp_concurrent_requests(self):
        """Test MCP handling of concurrent requests."""
        import asyncio

        async def make_request():
            async with httpx.AsyncClient() as client:
                return await client.get("http://discord:8001/mcp/tools", timeout=10.0)

        # Make 3 concurrent requests
        tasks = [make_request() for _ in range(3)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed or handle gracefully
        for response in responses:
            if isinstance(response, Exception):
                # Timeout or connection errors are acceptable
                assert isinstance(response, (httpx.TimeoutException, httpx.ConnectError))
            else:
                assert hasattr(response, "status_code")
                assert response.status_code == 200
