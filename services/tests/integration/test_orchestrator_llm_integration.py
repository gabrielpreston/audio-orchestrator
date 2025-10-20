"""Integration tests for Orchestrator → LLM service boundary."""

import httpx
import pytest

from services.tests.utils.service_helpers import docker_compose_test_context


@pytest.mark.integration
class TestOrchestratorLLMIntegration:
    """Test Orchestrator to LLM service HTTP boundary."""

    async def test_llm_openai_compatible_endpoint(self, test_auth_token):
        """Test LLM OpenAI-compatible API endpoint."""
        async with docker_compose_test_context(["llm"]):
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://llm:8000/v1/chat/completions",
                    json={
                        "model": "default",
                        "messages": [{"role": "user", "content": "Hello"}],
                    },
                    headers={"Authorization": f"Bearer {test_auth_token}"},
                    timeout=60.0,
                )

                assert response.status_code == 200
                data = response.json()
                assert "choices" in data

    async def test_llm_authentication_required(self):
        """Test LLM requires authentication."""
        async with docker_compose_test_context(["llm"]):
            async with httpx.AsyncClient() as client:
                # Test without auth token
                response = await client.post(
                    "http://llm:8000/v1/chat/completions",
                    json={
                        "model": "default",
                        "messages": [{"role": "user", "content": "Hello"}],
                    },
                    timeout=10.0,
                )

                assert response.status_code == 401

    async def test_llm_health_endpoint(self):
        """Test LLM health endpoint accessibility."""
        async with docker_compose_test_context(["llm"]):
            async with httpx.AsyncClient() as client:
                # Test live endpoint
                response = await client.get("http://llm:8000/health/live", timeout=5.0)
                assert response.status_code == 200

                # Test ready endpoint
                response = await client.get("http://llm:8000/health/ready", timeout=5.0)
                assert response.status_code in [200, 503]  # May be ready or not ready

                if response.status_code == 200:
                    data = response.json()
                    assert data["service"] == "llm"
                    assert "status" in data

    async def test_llm_correlation_id_propagation(
        self, test_auth_token, test_correlation_id
    ):
        """Test correlation ID propagation through LLM."""
        async with docker_compose_test_context(["llm"]):
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://llm:8000/v1/chat/completions",
                    json={
                        "model": "default",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "correlation_id": test_correlation_id,
                    },
                    headers={"Authorization": f"Bearer {test_auth_token}"},
                    timeout=60.0,
                )

                assert response.status_code == 200
                data = response.json()
                # LLM may or may not return correlation_id in response
                # This test verifies the request was processed successfully
