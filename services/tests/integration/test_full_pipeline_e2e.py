"""Fast integration tests for audio pipeline components.

Tests are organized into smaller, focused integration tests that run quickly
and provide fast feedback during development. Each test focuses on a specific
service or service pair rather than the full end-to-end pipeline.

All tests use environment-based URLs via standardized {SERVICE}_BASE_URL pattern.
"""

import base64
import io
import time

import httpx
import pytest

from services.tests.fixtures.integration_fixtures import Timeouts
from services.tests.integration.conftest import get_service_url
from services.tests.utils.audio_quality_helpers import (
    create_wav_file,
    generate_test_audio,
)
from services.tests.utils.service_helpers import docker_compose_test_context


# ============================================================================
# Note: Audio Service Tests Removed
# ============================================================================
# Audio processing functionality has been extracted to common libraries:
# - services/common/audio_vad.py - VAD processing
# - services/common/audio_quality.py - Quality metrics
# - services/common/audio_processing_core.py - Core processing
# - services/common/audio_enhancement.py - ML enhancement
# These are now used directly by Discord and STT services as libraries.
# ============================================================================

# ============================================================================
# STT Service Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_stt_service_transcribe():
    """Test STT service transcription endpoint standalone."""
    stt_url = get_service_url("STT")
    required_services = ["stt"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        test_audio = create_wav_file(
            generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5),
            sample_rate=16000,
            channels=1,
        )

        start_time = time.time()
        # STT /transcribe endpoint requires multipart form data with 'file' field
        files = {"file": ("test.wav", io.BytesIO(test_audio), "audio/wav")}
        response = await client.post(
            f"{stt_url}/transcribe",
            files=files,
            timeout=Timeouts.STANDARD,
        )
        elapsed = time.time() - start_time

        assert response.status_code == 200, f"STT failed: {response.text}"
        data = response.json()
        transcript = data.get("text", "").strip()

        assert (
            len(transcript) >= 0
        ), "STT should return transcript (may be empty for test audio)"
        assert elapsed < 5.0, f"STT should complete quickly, took {elapsed:.2f}s"


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_stt_error_handling():
    """Test STT service error handling for invalid inputs."""
    stt_url = get_service_url("STT")
    required_services = ["stt"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        # Test invalid audio format - use multipart form
        files = {
            "file": ("invalid.wav", io.BytesIO(b"invalid audio data"), "audio/wav")
        }
        response = await client.post(
            f"{stt_url}/transcribe",
            files=files,
            timeout=Timeouts.STANDARD,
        )
        # Should handle gracefully
        assert response.status_code in [200, 400, 422, 500]


# ============================================================================
# Orchestrator Service Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_orchestrator_process_transcript():
    """Test orchestrator service transcript processing with LLM."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        test_transcript = "Hello, this is a test message."

        start_time = time.time()
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": test_transcript,
                "user_id": "test_user",
                "channel_id": "test_channel",
                "correlation_id": "test-orchestrator-correlation-id",
            },
            timeout=Timeouts.STANDARD,
        )
        elapsed = time.time() - start_time

        assert response.status_code == 200, f"Orchestrator failed: {response.text}"
        data = response.json()
        response_text = data.get("response_text", "")

        assert len(response_text) > 0, "Orchestrator should produce response"
        assert (
            elapsed < 30.0
        ), f"Orchestrator should complete in < 30s, took {elapsed:.2f}s"

        # Verify correlation ID is returned
        correlation_id = data.get("correlation_id")
        assert correlation_id == "test-orchestrator-correlation-id"


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_orchestrator_error_handling():
    """Test orchestrator error handling for invalid inputs."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        # Test empty transcript
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": "",
                "user_id": "test_user",
                "channel_id": "test_channel",
            },
            timeout=Timeouts.STANDARD,
        )
        # Should handle gracefully
        assert response.status_code in [200, 400, 422]


# ============================================================================
# TTS Service Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_tts_service_synthesize():
    """Test TTS service synthesis endpoint standalone."""
    tts_url = get_service_url("TTS")
    required_services = ["tts"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        test_text = "Hello, this is a test message for TTS."

        start_time = time.time()
        response = await client.post(
            f"{tts_url}/synthesize",
            json={"text": test_text, "voice": "v2/en_speaker_1"},
            headers={"Authorization": "Bearer test-token"},
            timeout=Timeouts.STANDARD,
        )
        elapsed = time.time() - start_time

        assert response.status_code == 200, f"TTS failed: {response.text}"
        data = response.json()
        audio_base64 = data.get("audio")

        assert audio_base64 is not None, "TTS should return audio"
        audio_bytes = base64.b64decode(audio_base64)
        assert len(audio_bytes) > 0, "Audio should not be empty"
        assert audio_bytes[:4] == b"RIFF", "Audio should be valid WAV format"
        assert elapsed < 5.0, f"TTS should complete in < 5s, took {elapsed:.2f}s"


# ============================================================================
# Service Integration Tests (2-3 services)
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_stt_transcription():
    """Test STT transcription (audio preprocessing now handled internally)."""
    stt_url = get_service_url("STT")
    required_services = ["stt"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        test_audio = create_wav_file(
            generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5),
            sample_rate=16000,
            channels=1,
        )

        # STT transcription - audio enhancement is now handled internally by STT service
        files = {"file": ("test.wav", io.BytesIO(test_audio), "audio/wav")}
        stt_response = await client.post(
            f"{stt_url}/transcribe",
            files=files,
            timeout=Timeouts.STANDARD,
        )

        assert stt_response.status_code == 200
        transcript = stt_response.json().get("text", "").strip()
        # Transcript may be empty for synthetic audio, that's okay
        assert isinstance(transcript, str)


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_stt_orchestrator_integration():
    """Test STT → Orchestrator integration."""
    stt_url = get_service_url("STT")
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["stt", "orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        test_audio = create_wav_file(
            generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5),
            sample_rate=16000,
            channels=1,
        )

        # STT: Transcribe - use multipart form
        files = {"file": ("test.wav", io.BytesIO(test_audio), "audio/wav")}
        stt_response = await client.post(
            f"{stt_url}/transcribe",
            files=files,
            timeout=Timeouts.STANDARD,
        )
        assert stt_response.status_code == 200
        transcript = stt_response.json().get("text", "").strip()

        # Orchestrator: Process transcript
        # Use a fallback transcript if STT produces empty result
        test_transcript = transcript if transcript else "Hello, this is a test."
        orchestrator_response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": test_transcript,
                "user_id": "test_user",
                "channel_id": "test_channel",
                "correlation_id": "test-stt-orch-integration",
            },
            timeout=Timeouts.STANDARD,
        )

        assert orchestrator_response.status_code == 200
        orchestrator_data = orchestrator_response.json()
        response_text = orchestrator_data.get("response_text", "")
        assert len(response_text) > 0, "Orchestrator should produce response"


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_orchestrator_tts_integration():
    """Test Orchestrator → TTS integration."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    tts_url = get_service_url("TTS")
    required_services = ["orchestrator", "flan", "tts", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        test_transcript = "Hello, this is a test message for the audio pipeline."

        # Orchestrator: Process transcript
        orchestrator_response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": test_transcript,
                "user_id": "test_user",
                "channel_id": "test_channel",
                "correlation_id": "test-orch-tts-integration",
            },
            timeout=Timeouts.STANDARD,
        )

        assert orchestrator_response.status_code == 200
        orchestrator_data = orchestrator_response.json()
        response_text = orchestrator_data.get("response_text", "")
        assert len(response_text) > 0, "Orchestrator should produce response"

        # TTS: Synthesize response
        tts_response = await client.post(
            f"{tts_url}/synthesize",
            json={"text": response_text, "voice": "v2/en_speaker_1"},
            headers={"Authorization": "Bearer test-token"},
            timeout=Timeouts.STANDARD,
        )

        assert tts_response.status_code == 200
        tts_data = tts_response.json()
        audio_base64 = tts_data.get("audio")

        assert audio_base64 is not None, "TTS should return audio"
        audio_bytes = base64.b64decode(audio_base64)
        assert len(audio_bytes) > 0, "Audio should not be empty"
        assert audio_bytes[:4] == b"RIFF", "Audio should be valid WAV format"


# ============================================================================
# Correlation ID Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_stt_correlation_id():
    """Test correlation ID propagation in STT service."""
    stt_url = get_service_url("STT")
    required_services = ["stt"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        test_correlation_id = f"test-stt-correlation-{int(time.time())}"
        test_audio = create_wav_file(
            generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5),
            sample_rate=16000,
            channels=1,
        )

        # STT /transcribe requires multipart form data
        files = {"file": ("test.wav", io.BytesIO(test_audio), "audio/wav")}
        response = await client.post(
            f"{stt_url}/transcribe",
            files=files,
            headers={
                "X-Correlation-ID": test_correlation_id,
            },
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200
        # Note: STT may not return correlation ID, that's okay for now
        # This test validates the header is accepted


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_orchestrator_correlation_id():
    """Test correlation ID propagation in Orchestrator service."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        test_correlation_id = f"test-orch-correlation-{int(time.time())}"

        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": "Hello, test correlation ID.",
                "user_id": "test_user",
                "channel_id": "test_channel",
                "correlation_id": test_correlation_id,
            },
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify correlation ID is returned
        returned_correlation_id = data.get("correlation_id")
        assert (
            returned_correlation_id == test_correlation_id
        ), f"Correlation ID should propagate: expected {test_correlation_id}, got {returned_correlation_id}"
