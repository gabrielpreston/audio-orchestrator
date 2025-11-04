"""Integration tests for Bark TTS service endpoints.

Tests focus on direct Bark TTS service endpoints, validating text-to-speech
synthesis, voice listing, and health checks.
"""

import base64
import httpx
import pytest

from services.tests.fixtures.integration_fixtures import Timeouts
from services.tests.integration.conftest import get_service_url
from services.tests.utils.service_helpers import docker_compose_test_context


# ============================================================================
# Bark TTS Service Endpoint Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_bark_synthesize():
    """Test Bark TTS service /synthesize endpoint with various text inputs."""
    tts_url = get_service_url("TTS")
    required_services = ["bark"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.LONG_RUNNING) as client,
    ):
        # Test 1: Short text with default voice
        request_data = {
            "text": "Hello, this is a test.",
            "voice": "v2/en_speaker_1",
            "speed": 1.0,
        }

        response = await client.post(
            f"{tts_url}/synthesize",
            json=request_data,
            timeout=Timeouts.LONG_RUNNING,
        )

        assert response.status_code == 200, f"Synthesis failed: {response.text}"
        data = response.json()

        # Validate response structure
        assert "audio" in data, "Response should contain audio field"
        assert "engine" in data, "Response should contain engine field"
        assert (
            "processing_time_ms" in data
        ), "Response should contain processing_time_ms"
        assert "voice_used" in data, "Response should contain voice_used"

        # Validate audio is base64-encoded
        audio_data = data["audio"]
        assert isinstance(audio_data, str), "Audio should be a base64-encoded string"
        assert len(audio_data) > 0, "Audio should not be empty"

        # Validate audio can be decoded (basic format check)
        try:
            decoded_audio = base64.b64decode(audio_data)
            assert len(decoded_audio) > 0, "Decoded audio should not be empty"
        except Exception as e:
            pytest.fail(f"Audio should be valid base64: {e}")

        # Validate engine is "bark"
        assert data["engine"] == "bark", "Engine should be 'bark'"

        # Validate processing time is reasonable
        assert data["processing_time_ms"] > 0, "Processing time should be positive"
        assert (
            data["processing_time_ms"] < 30000
        ), "Processing time should be reasonable (< 30s)"

        # Test 2: Longer text with different voice
        request_data2 = {
            "text": "This is a longer text to test synthesis with more content. "
            "It should still produce valid audio output.",
            "voice": "v2/en_speaker_1",
            "speed": 1.0,
        }

        response2 = await client.post(
            f"{tts_url}/synthesize",
            json=request_data2,
            timeout=Timeouts.LONG_RUNNING,
        )

        assert (
            response2.status_code == 200
        ), f"Long text synthesis failed: {response2.text}"
        data2 = response2.json()
        assert "audio" in data2, "Long text response should contain audio"
        assert len(data2["audio"]) > len(
            audio_data
        ), "Longer text should produce more audio"


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_bark_list_voices():
    """Test Bark TTS service /voices endpoint."""
    tts_url = get_service_url("TTS")
    required_services = ["bark"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.get(
            f"{tts_url}/voices",
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200, f"Voices endpoint failed: {response.text}"
        data = response.json()

        # Validate response structure
        assert "bark" in data, "Response should contain bark voices"
        assert "piper" in data, "Response should contain piper voices"

        # Validate bark voices
        assert isinstance(data["bark"], list), "Bark voices should be a list"
        assert len(data["bark"]) > 0, "Should return at least one Bark voice"

        # Validate voice format
        voice = data["bark"][0]
        assert isinstance(voice, str), "Voice should be a string"
        assert len(voice) > 0, "Voice should not be empty"

        # Validate piper voices (may be minimal)
        assert isinstance(data["piper"], list), "Piper voices should be a list"
        # Piper may have minimal voices (e.g., ["default"])


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_bark_synthesize_error_handling():
    """Test Bark TTS service error handling for invalid requests."""
    tts_url = get_service_url("TTS")
    required_services = ["bark"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        # Test with missing text field
        response = await client.post(
            f"{tts_url}/synthesize",
            json={"voice": "v2/en_speaker_1", "speed": 1.0},
            timeout=Timeouts.STANDARD,
        )
        assert response.status_code in [
            400,
            422,
        ], "Missing text should return error"

        # Test with empty text
        response = await client.post(
            f"{tts_url}/synthesize",
            json={"text": "", "voice": "v2/en_speaker_1", "speed": 1.0},
            timeout=Timeouts.STANDARD,
        )
        assert response.status_code in [
            400,
            422,
        ], "Empty text should return error"

        # Test with invalid JSON
        response = await client.post(
            f"{tts_url}/synthesize",
            content=b"invalid json",
            headers={"Content-Type": "application/json"},
            timeout=Timeouts.STANDARD,
        )
        assert response.status_code in [400, 422], "Invalid JSON should return error"


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_bark_health_live():
    """Test Bark TTS service /health/live endpoint."""
    tts_url = get_service_url("TTS")
    required_services = ["bark"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.get(
            f"{tts_url}/health/live",
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200, f"Health live failed: {response.text}"
        data = response.json()

        # Validate response structure
        assert "status" in data, "Response should contain status field"
        assert data["status"] == "alive", "Status should be 'alive'"
        assert "service" in data, "Response should contain service field"
        assert data["service"] == "bark", "Service should be 'bark'"


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_bark_health_ready():
    """Test Bark TTS service /health/ready endpoint."""
    tts_url = get_service_url("TTS")
    required_services = ["bark"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.get(
            f"{tts_url}/health/ready",
            timeout=Timeouts.STANDARD,
        )

        # Service may be ready (200) or not ready (503) depending on model loading
        assert response.status_code in [
            200,
            503,
        ], f"Health ready returned unexpected status: {response.status_code}"

        data = response.json()

        # Validate response structure
        assert "status" in data, "Response should contain status field"
        assert "service" in data, "Response should contain service field"
        assert data["service"] == "bark", "Service should be 'bark'"

        if response.status_code == 200:
            assert (
                data["status"] == "ready"
            ), "Status should be 'ready' when service is ready"
        else:
            assert (
                data["status"] == "not_ready"
            ), "Status should be 'not_ready' when service is not ready"
