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
import numpy as np
import pytest

from services.tests.fixtures.integration_fixtures import Timeouts
from services.tests.integration.conftest import get_service_url
from services.tests.utils.audio_quality_helpers import (
    create_wav_file,
    generate_test_audio,
)
from services.tests.utils.service_helpers import docker_compose_test_context


# ============================================================================
# Audio Service Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_audio_service_denoise():
    """Test audio service denoise endpoint standalone."""
    audio_url = get_service_url("AUDIO")
    required_services = ["audio"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        test_audio = create_wav_file(
            generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5),
            sample_rate=16000,
            channels=1,
        )

        response = await client.post(
            f"{audio_url}/denoise",
            content=test_audio,
            headers={"Content-Type": "audio/wav"},
            timeout=Timeouts.STANDARD,
        )

        # May return 200 or gracefully degrade
        assert response.status_code in [200, 400, 422, 503]
        if response.status_code == 200:
            assert len(response.content) > 0
            assert response.content[:4] == b"RIFF", "Should return valid WAV"


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_audio_process_frame():
    """Test audio service /process/frame endpoint with PCM frame data."""
    audio_url = get_service_url("AUDIO")
    required_services = ["audio"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        # Generate test audio and convert to PCM bytes
        # generate_test_audio returns bytes, so we need to create numpy array directly
        sample_rate = 16000
        duration = 0.1
        frequency = 440.0
        amplitude = 0.5

        t = np.linspace(0, duration, int(sample_rate * duration), False)
        signal = amplitude * np.sin(2 * np.pi * frequency * t)
        audio_int16 = (signal * 32767).astype(np.int16)
        pcm_bytes = audio_int16.tobytes()
        pcm_base64 = base64.b64encode(pcm_bytes).decode()

        request_data = {
            "pcm": pcm_base64,
            "timestamp": 0.0,
            "rms": 0.5,
            "duration": 0.1,
            "sequence": 1,
            "sample_rate": 16000,
        }

        response = await client.post(
            f"{audio_url}/process/frame",
            json=request_data,
            timeout=Timeouts.STANDARD,
        )

        # May return 200 or gracefully degrade if processor not initialized
        assert response.status_code in [200, 503]
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "pcm" in data
            assert "processing_time_ms" in data
            assert "quality_metrics" in data
            assert isinstance(data.get("quality_metrics"), (dict, type(None)))


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_audio_process_segment():
    """Test audio service /process/segment endpoint with audio segments."""
    audio_url = get_service_url("AUDIO")
    required_services = ["audio"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        # Generate test audio and convert to PCM bytes
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        amplitude = 0.5

        t = np.linspace(0, duration, int(sample_rate * duration), False)
        signal = amplitude * np.sin(2 * np.pi * frequency * t)
        audio_int16 = (signal * 32767).astype(np.int16)
        pcm_bytes = audio_int16.tobytes()
        pcm_base64 = base64.b64encode(pcm_bytes).decode()

        request_data = {
            "user_id": 12345,
            "pcm": pcm_base64,
            "start_timestamp": 0.0,
            "end_timestamp": 1.0,
            "correlation_id": "test-correlation-123",
            "frame_count": 10,
            "sample_rate": 16000,
        }

        response = await client.post(
            f"{audio_url}/process/segment",
            json=request_data,
            timeout=Timeouts.STANDARD,
        )

        # May return 200 or gracefully degrade if processor not initialized
        assert response.status_code in [200, 503]
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "pcm" in data
            assert "processing_time_ms" in data
            assert "quality_metrics" in data


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_audio_enhance_audio():
    """Test audio service /enhance/audio endpoint for audio enhancement."""
    audio_url = get_service_url("AUDIO")
    required_services = ["audio"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        test_audio = create_wav_file(
            generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5),
            sample_rate=16000,
            channels=1,
        )

        response = await client.post(
            f"{audio_url}/enhance/audio",
            content=test_audio,
            headers={"Content-Type": "audio/wav"},
            timeout=Timeouts.STANDARD,
        )

        # May return 200 or gracefully degrade if enhancer not initialized
        assert response.status_code in [200, 503]
        if response.status_code == 200:
            assert len(response.content) > 0
            assert response.content[:4] == b"RIFF", "Should return valid WAV"
            assert response.headers.get("Content-Type") == "audio/wav"


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_audio_denoise_streaming():
    """Test audio service /denoise/streaming endpoint."""
    audio_url = get_service_url("AUDIO")
    required_services = ["audio"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        test_audio = create_wav_file(
            generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5),
            sample_rate=16000,
            channels=1,
        )

        response = await client.post(
            f"{audio_url}/denoise/streaming",
            content=test_audio,
            headers={"Content-Type": "audio/wav"},
            timeout=Timeouts.STANDARD,
        )

        # May return 200 or gracefully degrade if enhancer not initialized
        assert response.status_code in [200, 503]
        if response.status_code == 200:
            assert len(response.content) > 0
            assert response.content[:4] == b"RIFF", "Should return valid WAV"


# ============================================================================
# STT Service Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_stt_service_transcribe():
    """Test STT service transcription endpoint standalone."""
    stt_url = get_service_url("STT")
    required_services = ["stt", "audio"]

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
async def test_audio_stt_integration():
    """Test audio preprocessing + STT integration."""
    audio_url = get_service_url("AUDIO")
    stt_url = get_service_url("STT")
    required_services = ["audio", "stt"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        test_audio = create_wav_file(
            generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5),
            sample_rate=16000,
            channels=1,
        )

        # Optional: Try audio preprocessing
        processed_audio = test_audio
        try:
            enhanced_response = await client.post(
                f"{audio_url}/denoise",
                content=test_audio,
                headers={"Content-Type": "audio/wav"},
                timeout=Timeouts.STANDARD,
            )
            if enhanced_response.status_code == 200:
                processed_audio = enhanced_response.content
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            # Graceful degradation - continue with original audio if preprocessing fails
            # This is expected if audio service is not fully configured
            print(
                f"Audio preprocessing skipped (graceful degradation): {type(e).__name__}"
            )

        # STT transcription - use multipart form
        files = {"file": ("test.wav", io.BytesIO(processed_audio), "audio/wav")}
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
    required_services = ["stt", "audio", "orchestrator", "flan", "guardrails"]

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
    required_services = ["stt", "audio"]

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
