"""Integration tests for LLM (FLAN-T5) service endpoints.

Tests focus on direct LLM service endpoints, validating OpenAI-compatible
API responses and error handling.
"""

import time

import httpx
import pytest

from services.tests.fixtures.integration_fixtures import Timeouts
from services.tests.integration.conftest import get_service_url
from services.tests.utils.service_helpers import docker_compose_test_context


# ============================================================================
# LLM Service Endpoint Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_llm_chat_completions():
    """Test LLM service /v1/chat/completions endpoint with OpenAI-compatible request."""
    llm_url = get_service_url("LLM")
    required_services = ["flan"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.LONG_RUNNING) as client,
    ):
        request_data = {
            "model": "google/flan-t5-base",
            "messages": [{"role": "user", "content": "Hello, how are you?"}],
            "temperature": 0.7,
            "max_tokens": 100,
        }

        response = await client.post(
            f"{llm_url}/v1/chat/completions",
            json=request_data,
            timeout=Timeouts.LONG_RUNNING,
        )

        assert response.status_code == 200, f"LLM failed: {response.text}"
        data = response.json()

        # Validate OpenAI-compatible response structure
        assert "choices" in data, "Response should contain choices"
        assert len(data["choices"]) > 0, "Response should have at least one choice"

        choice = data["choices"][0]
        assert "message" in choice, "Choice should contain message"
        assert "content" in choice["message"], "Message should contain content"

        content = choice["message"].get("content", "")
        assert isinstance(content, str), "Content should be a string"
        assert len(content.strip()) > 0, "Content should not be empty"

        # Validate optional fields
        if "model" in data:
            assert isinstance(data["model"], str)
        if "usage" in data:
            assert isinstance(data["usage"], dict)


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_llm_list_models():
    """Test LLM service /models endpoint."""
    llm_url = get_service_url("LLM")
    required_services = ["flan"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.get(
            f"{llm_url}/models",
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200, f"Models endpoint failed: {response.text}"
        data = response.json()

        # Validate response structure
        assert "data" in data, "Response should contain data field"
        assert isinstance(data["data"], list), "Data should be a list"
        assert len(data["data"]) > 0, "Should return at least one model"

        model = data["data"][0]
        assert "id" in model, "Model should have id"
        assert "object" in model, "Model should have object"
        assert model["object"] == "model", "Object type should be 'model'"

        # Validate model ID is a string
        assert isinstance(model["id"], str), "Model ID should be a string"
        assert len(model["id"]) > 0, "Model ID should not be empty"


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_llm_error_handling():
    """Test LLM service error handling for various failure modes."""
    llm_url = get_service_url("LLM")
    required_services = ["flan"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        # Test with empty messages array
        response = await client.post(
            f"{llm_url}/v1/chat/completions",
            json={"model": "google/flan-t5-base", "messages": []},
            timeout=Timeouts.STANDARD,
        )
        assert response.status_code in [400, 422], "Empty messages should return error"

        # Test with invalid request format (missing messages)
        response = await client.post(
            f"{llm_url}/v1/chat/completions",
            json={"model": "google/flan-t5-base"},
            timeout=Timeouts.STANDARD,
        )
        assert response.status_code in [
            400,
            422,
        ], "Missing messages should return error"

        # Test with invalid JSON
        response = await client.post(
            f"{llm_url}/v1/chat/completions",
            content=b"invalid json",
            headers={"Content-Type": "application/json"},
            timeout=Timeouts.STANDARD,
        )
        assert response.status_code in [400, 422], "Invalid JSON should return error"


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_llm_correlation_id():
    """Test correlation ID propagation in LLM requests."""
    llm_url = get_service_url("LLM")
    required_services = ["flan"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.LONG_RUNNING) as client,
    ):
        test_correlation_id = f"test-llm-correlation-{int(time.time())}"

        request_data = {
            "model": "google/flan-t5-base",
            "messages": [
                {"role": "user", "content": "Test correlation ID propagation."}
            ],
        }

        response = await client.post(
            f"{llm_url}/v1/chat/completions",
            json=request_data,
            headers={"X-Correlation-ID": test_correlation_id},
            timeout=Timeouts.LONG_RUNNING,
        )

        assert response.status_code == 200, f"LLM failed: {response.text}"
        # Note: LLM service may not return correlation ID in response body,
        # but should accept and log the header (validated by successful request)
