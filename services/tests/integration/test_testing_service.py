"""Integration tests for the Testing service (Gradio UI).

Tests validate that the Testing service can access all dependencies
and that the underlying pipeline components work correctly.

Note: Full Gradio UI testing would require Selenium - we focus on
underlying pipeline and dependency connectivity.
"""

import io

import httpx
import pytest

from services.tests.fixtures.integration_fixtures import Timeouts
from services.tests.integration.conftest import get_service_url
from services.tests.utils.service_helpers import docker_compose_test_context


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_testing_service_dependencies():
    """Validate all dependencies are accessible from Testing service perspective."""
    # Get service URLs
    stt_url = get_service_url("STT")
    orchestrator_url = get_service_url("ORCHESTRATOR")
    tts_url = get_service_url("TTS")

    # Services required for this test
    required_services = [
        "testing",
        "stt",
        "orchestrator",
        "flan",
        "tts",
        "guardrails",
    ]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        # Check that Testing service dependencies are accessible
        # (Testing service uses these URLs internally)
        # Note: Audio processing is now handled via libraries in STT and Discord services

        # 1. STT service should be accessible
        stt_health = await client.get(
            f"{stt_url}/health/ready", timeout=Timeouts.HEALTH_CHECK
        )
        assert stt_health.status_code == 200, "STT service should be accessible"

        # 3. Orchestrator service should be accessible
        orchestrator_health = await client.get(
            f"{orchestrator_url}/health/ready", timeout=Timeouts.HEALTH_CHECK
        )
        assert (
            orchestrator_health.status_code == 200
        ), "Orchestrator service should be accessible"

        # 4. TTS service should be accessible
        tts_health = await client.get(
            f"{tts_url}/health/ready", timeout=Timeouts.HEALTH_CHECK
        )
        assert tts_health.status_code == 200, "TTS service should be accessible"

        # Note: Testing service itself may or may not have a health endpoint
        # depending on implementation - we validate dependencies instead


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_testing_service_pipeline_components():
    """Test individual components that Testing service uses in its pipeline."""
    # Get service URLs
    stt_url = get_service_url("STT")
    orchestrator_url = get_service_url("ORCHESTRATOR")
    tts_url = get_service_url("TTS")

    required_services = ["stt", "orchestrator", "flan", "tts", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        # 1. Audio preprocessing is now handled internally by Testing service
        # (uses AudioEnhancer library directly)
        from services.tests.utils.audio_quality_helpers import (
            create_wav_file,
            generate_test_audio,
        )

        test_audio = create_wav_file(
            generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5),
            sample_rate=16000,
            channels=1,
        )

        # 2. STT transcription component - use multipart form
        files = {"file": ("test.wav", io.BytesIO(test_audio), "audio/wav")}
        stt_response = await client.post(
            f"{stt_url}/transcribe",
            files=files,
            timeout=Timeouts.STANDARD,
        )
        assert stt_response.status_code == 200, "STT should transcribe audio"
        transcript = stt_response.json().get("text", "").strip()
        assert len(transcript) > 0, "STT should produce transcript"

        # 3. Orchestrator processing component
        orchestrator_response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": transcript,
                "user_id": "test_user",
                "channel_id": "test_channel",
            },
            timeout=Timeouts.STANDARD,
        )
        assert (
            orchestrator_response.status_code == 200
        ), "Orchestrator should process transcript"
        response_text = orchestrator_response.json().get("response_text", "")
        assert len(response_text) > 0, "Orchestrator should produce response"

        # 4. TTS synthesis component
        tts_response = await client.post(
            f"{tts_url}/synthesize",
            json={"text": response_text[:100], "voice": "v2/en_speaker_1"},
            headers={"Authorization": "Bearer test-token"},
            timeout=Timeouts.STANDARD,
        )
        assert tts_response.status_code == 200, "TTS should synthesize audio"
        tts_data = tts_response.json()
        assert "audio" in tts_data, "TTS should return audio"
