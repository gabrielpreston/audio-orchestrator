"""Integration tests for service failure scenarios and graceful degradation.

Tests validate that services handle dependency failures gracefully and continue
operating with degraded functionality when optional services are unavailable.
"""

import os

import httpx
import pytest

from services.tests.fixtures.integration_fixtures import Timeouts
from services.tests.integration.conftest import get_service_url
from services.tests.utils.service_helpers import docker_compose_test_context


# ============================================================================
# Service Failure Scenario Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.failure
@pytest.mark.timeout(120)
async def test_orchestrator_guardrails_failure():
    """Test orchestrator graceful degradation when Guardrails unavailable."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan"]

    # Temporarily override GUARDRAILS_BASE_URL with invalid URL
    original_url = os.environ.get("GUARDRAILS_BASE_URL")
    os.environ["GUARDRAILS_BASE_URL"] = "http://invalid-service:9999"

    try:
        async with (
            docker_compose_test_context(required_services, timeout=120.0),
            httpx.AsyncClient(timeout=Timeouts.LONG_RUNNING) as client,
        ):
            # Test orchestrator handles Guardrails failure gracefully
            response = await client.post(
                f"{orchestrator_url}/api/v1/transcripts",
                json={
                    "transcript": "Hello, this is a test message.",
                    "user_id": "test_user",
                    "channel_id": "test_channel",
                    "correlation_id": "test-guardrails-failure",
                },
                timeout=Timeouts.LONG_RUNNING,
            )

            # Should still return successful response (graceful degradation)
            assert response.status_code == 200, (
                f"Orchestrator should handle Guardrails failure gracefully, "
                f"got status {response.status_code}: {response.text}"
            )

            data = response.json()
            assert "response_text" in data
            assert len(data.get("response_text", "")) > 0

            # Validate graceful degradation - response should still be returned
            assert data.get("success") is True

    finally:
        # Restore original URL
        if original_url:
            os.environ["GUARDRAILS_BASE_URL"] = original_url
        elif "GUARDRAILS_BASE_URL" in os.environ:
            del os.environ["GUARDRAILS_BASE_URL"]


@pytest.mark.integration
@pytest.mark.failure
@pytest.mark.timeout(120)
async def test_orchestrator_llm_failure():
    """Test orchestrator behavior when LLM unavailable."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "guardrails"]

    # Temporarily override LLM_BASE_URL with invalid URL
    original_url = os.environ.get("LLM_BASE_URL")
    os.environ["LLM_BASE_URL"] = "http://invalid-llm-service:9999"

    try:
        async with (
            docker_compose_test_context(required_services, timeout=120.0),
            httpx.AsyncClient(timeout=Timeouts.LONG_RUNNING) as client,
        ):
            # Test orchestrator handles LLM failure
            response = await client.post(
                f"{orchestrator_url}/api/v1/transcripts",
                json={
                    "transcript": "Hello, this is a test message.",
                    "user_id": "test_user",
                    "channel_id": "test_channel",
                    "correlation_id": "test-llm-failure",
                },
                timeout=Timeouts.LONG_RUNNING,
            )

            # Orchestrator may return error or fallback response
            # Both are acceptable - important is it doesn't crash
            assert response.status_code in [200, 500, 503], (
                f"Orchestrator should handle LLM failure gracefully, "
                f"got status {response.status_code}: {response.text}"
            )

            # If successful, validate fallback response
            if response.status_code == 200:
                data = response.json()
                assert "response_text" in data or "error" in data

    finally:
        # Restore original URL
        if original_url:
            os.environ["LLM_BASE_URL"] = original_url
        elif "LLM_BASE_URL" in os.environ:
            del os.environ["LLM_BASE_URL"]


@pytest.mark.integration
@pytest.mark.failure
@pytest.mark.timeout(120)
async def test_orchestrator_tts_failure():
    """Test orchestrator graceful degradation when TTS unavailable."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    # Temporarily override TTS_BASE_URL with invalid URL
    original_url = os.environ.get("TTS_BASE_URL")
    os.environ["TTS_BASE_URL"] = "http://invalid-tts-service:9999"

    try:
        async with (
            docker_compose_test_context(required_services, timeout=120.0),
            httpx.AsyncClient(timeout=Timeouts.LONG_RUNNING) as client,
        ):
            # Test orchestrator continues without audio (graceful degradation)
            response = await client.post(
                f"{orchestrator_url}/api/v1/transcripts",
                json={
                    "transcript": "Hello, this is a test message.",
                    "user_id": "test_user",
                    "channel_id": "test_channel",
                    "correlation_id": "test-tts-failure",
                },
                timeout=Timeouts.LONG_RUNNING,
            )

            # Should still return successful response without audio
            assert response.status_code == 200, (
                f"Orchestrator should handle TTS failure gracefully, "
                f"got status {response.status_code}: {response.text}"
            )

            data = response.json()
            assert "response_text" in data
            assert len(data.get("response_text", "")) > 0

            # Validate graceful degradation - audio_data should be None
            assert (
                data.get("audio_data") is None
            ), "Audio data should be None when TTS is unavailable"

    finally:
        # Restore original URL
        if original_url:
            os.environ["TTS_BASE_URL"] = original_url
        elif "TTS_BASE_URL" in os.environ:
            del os.environ["TTS_BASE_URL"]


@pytest.mark.integration
@pytest.mark.failure
@pytest.mark.timeout(120)
async def test_stt_audio_processor_failure():
    """Test STT graceful degradation when Audio service unavailable."""
    stt_url = get_service_url("STT")
    required_services = ["stt"]

    # Temporarily override AUDIO_BASE_URL with invalid URL
    original_url = os.environ.get("AUDIO_BASE_URL")
    os.environ["AUDIO_BASE_URL"] = "http://invalid-audio-service:9999"

    try:
        async with (
            docker_compose_test_context(required_services, timeout=120.0),
            httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
        ):
            # Import audio generation helpers
            from services.tests.utils.audio_quality_helpers import (
                create_wav_file,
                generate_test_audio,
            )
            import io

            test_audio = create_wav_file(
                generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5),
                sample_rate=16000,
                channels=1,
            )

            # STT should still process requests (audio preprocessing is optional)
            files = {"file": ("test.wav", io.BytesIO(test_audio), "audio/wav")}
            response = await client.post(
                f"{stt_url}/transcribe",
                files=files,
                timeout=Timeouts.STANDARD,
            )

            # Should still succeed (audio preprocessing failure should not block STT)
            assert response.status_code == 200, (
                f"STT should handle Audio service failure gracefully, "
                f"got status {response.status_code}: {response.text}"
            )

            data = response.json()
            assert "text" in data
            # Transcript may be empty for synthetic audio, but structure should be valid

    finally:
        # Restore original URL
        if original_url:
            os.environ["AUDIO_BASE_URL"] = original_url
        elif "AUDIO_BASE_URL" in os.environ:
            del os.environ["AUDIO_BASE_URL"]
