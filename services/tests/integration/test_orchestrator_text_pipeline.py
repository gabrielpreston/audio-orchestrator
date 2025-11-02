"""Focused integration tests for orchestrator text input/output pipeline.

These tests focus on bite-sized chunks of the pipeline: sending text to the
orchestrator and validating text responses. Each test is small, focused, and
provides fast feedback during development.
"""

import time

import httpx
import pytest

from services.tests.fixtures.integration_fixtures import Timeouts
from services.tests.integration.conftest import get_service_url
from services.tests.utils.service_helpers import docker_compose_test_context


# ============================================================================
# Basic Text Input/Output Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_simple_text_input():
    """Test basic text input to orchestrator returns text response."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": "Hello",
                "user_id": "test_user",
                "channel_id": "test_channel",
            },
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()

        # Validate response structure
        assert "response_text" in data, "Response should contain response_text"
        assert isinstance(data["response_text"], str), "response_text should be string"
        assert len(data["response_text"]) > 0, "Response should not be empty"

        # Validate success flag
        assert data.get("success") is True, "Response should indicate success"


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_question_input():
    """Test orchestrator handles question format transcripts."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": "What is the weather like today?",
                "user_id": "test_user",
                "channel_id": "test_channel",
            },
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200
        data = response.json()
        response_text = data.get("response_text", "")

        assert len(response_text) > 0, "Orchestrator should respond to questions"


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_command_input():
    """Test orchestrator handles command format transcripts."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": "Tell me about artificial intelligence",
                "user_id": "test_user",
                "channel_id": "test_channel",
            },
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200
        data = response.json()
        response_text = data.get("response_text", "")

        assert len(response_text) > 0, "Orchestrator should respond to commands"


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_greeting_input():
    """Test orchestrator handles greeting format transcripts."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": "Hi there, how are you?",
                "user_id": "test_user",
                "channel_id": "test_channel",
            },
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200
        data = response.json()
        response_text = data.get("response_text", "")

        assert len(response_text) > 0, "Orchestrator should respond to greetings"


# ============================================================================
# Response Structure Validation Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_response_structure():
    """Test orchestrator response contains all expected fields."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": "Test message",
                "user_id": "test_user",
                "channel_id": "test_channel",
                "correlation_id": "test-correlation-123",
            },
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200
        data = response.json()

        # Validate required fields
        assert "success" in data, "Response should contain success field"
        assert "response_text" in data, "Response should contain response_text field"

        # Validate optional fields exist (may be None)
        assert "audio_data" in data, "Response should contain audio_data field"
        assert "audio_format" in data, "Response should contain audio_format field"
        assert "tool_calls" in data, "Response should contain tool_calls field"
        assert "correlation_id" in data, "Response should contain correlation_id field"
        assert "error" in data, "Response should contain error field"


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_response_text_type():
    """Test orchestrator response_text is a non-empty string."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": "Return a text response",
                "user_id": "test_user",
                "channel_id": "test_channel",
            },
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200
        data = response.json()

        # Validate response_text type and content
        response_text = data.get("response_text")
        assert response_text is not None, "response_text should not be None"
        assert isinstance(response_text, str), "response_text should be a string"
        assert len(response_text.strip()) > 0, "response_text should not be empty"


# ============================================================================
# Correlation ID Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_correlation_id_propagation():
    """Test orchestrator propagates correlation ID in response."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    test_correlation_id = "test-correlation-abc123"

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": "Test message",
                "user_id": "test_user",
                "channel_id": "test_channel",
                "correlation_id": test_correlation_id,
            },
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200
        data = response.json()

        assert (
            data.get("correlation_id") == test_correlation_id
        ), "Correlation ID should be propagated in response"


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_correlation_id_optional():
    """Test orchestrator handles requests without correlation ID."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": "Test message",
                "user_id": "test_user",
                "channel_id": "test_channel",
                # correlation_id not provided
            },
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200
        data = response.json()

        # Should still process successfully
        assert data.get("success") is True
        assert "response_text" in data


# ============================================================================
# Metadata Handling Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_metadata_handling():
    """Test orchestrator accepts and processes metadata field."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    test_metadata = {"source": "test", "priority": "high"}

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": "Test with metadata",
                "user_id": "test_user",
                "channel_id": "test_channel",
                "metadata": test_metadata,
            },
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200
        data = response.json()

        # Should process successfully with metadata
        assert data.get("success") is True
        assert len(data.get("response_text", "")) > 0


# ============================================================================
# Response Time/Latency Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_response_time_short_text():
    """Test orchestrator responds quickly for short text inputs."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        start_time = time.time()
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": "Hi",
                "user_id": "test_user",
                "channel_id": "test_channel",
            },
            timeout=Timeouts.STANDARD,
        )
        elapsed = time.time() - start_time

        assert response.status_code == 200
        assert elapsed < 15.0, f"Short text should process quickly, took {elapsed:.2f}s"


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_response_time_medium_text():
    """Test orchestrator response time for medium-length text inputs."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    medium_text = " ".join(["This is a medium length transcript"] * 3)

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        start_time = time.time()
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": medium_text,
                "user_id": "test_user",
                "channel_id": "test_channel",
            },
            timeout=Timeouts.STANDARD,
        )
        elapsed = time.time() - start_time

        assert response.status_code == 200
        assert (
            elapsed < 20.0
        ), f"Medium text should process reasonably, took {elapsed:.2f}s"


# ============================================================================
# Transcript Length Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_short_transcript():
    """Test orchestrator handles very short transcripts."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": "Yes",
                "user_id": "test_user",
                "channel_id": "test_channel",
            },
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_long_transcript():
    """Test orchestrator handles longer transcripts."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    long_text = " ".join(["This is a longer transcript"] * 20)

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": long_text,
                "user_id": "test_user",
                "channel_id": "test_channel",
            },
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert len(data.get("response_text", "")) > 0


# ============================================================================
# Edge Case Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_whitespace_handling():
    """Test orchestrator handles transcripts with extra whitespace."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": "   This has   extra   whitespace   ",
                "user_id": "test_user",
                "channel_id": "test_channel",
            },
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_special_characters():
    """Test orchestrator handles special characters in transcripts."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": "Hello! How are you? I'm fine, thank you.",
                "user_id": "test_user",
                "channel_id": "test_channel",
            },
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert len(data.get("response_text", "")) > 0


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_consecutive_requests():
    """Test orchestrator handles multiple consecutive requests."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        transcripts = [
            "First message",
            "Second message",
            "Third message",
        ]

        for i, transcript in enumerate(transcripts):
            response = await client.post(
                f"{orchestrator_url}/api/v1/transcripts",
                json={
                    "transcript": transcript,
                    "user_id": f"test_user_{i}",
                    "channel_id": f"test_channel_{i}",
                },
                timeout=Timeouts.STANDARD,
            )

            assert response.status_code == 200, f"Request {i+1} failed: {response.text}"
            data = response.json()
            assert data.get("success") is True
            assert len(data.get("response_text", "")) > 0


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_different_users():
    """Test orchestrator handles requests from different users."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        users = ["user_001", "user_002", "user_003"]

        for user_id in users:
            response = await client.post(
                f"{orchestrator_url}/api/v1/transcripts",
                json={
                    "transcript": f"Hello from {user_id}",
                    "user_id": user_id,
                    "channel_id": "test_channel",
                },
                timeout=Timeouts.STANDARD,
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is True


@pytest.mark.integration
@pytest.mark.timeout(60)
async def test_orchestrator_different_channels():
    """Test orchestrator handles requests from different channels."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=60.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        channels = ["channel_001", "channel_002", "channel_003"]

        for channel_id in channels:
            response = await client.post(
                f"{orchestrator_url}/api/v1/transcripts",
                json={
                    "transcript": f"Hello from {channel_id}",
                    "user_id": "test_user",
                    "channel_id": channel_id,
                },
                timeout=Timeouts.STANDARD,
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is True
