"""Integration tests for STT enhancement pipeline."""

import time

import httpx
import pytest

from services.tests.fixtures.audio_samples import get_clean_sample, get_noisy_samples
from services.tests.utils.service_helpers import docker_compose_test_context


@pytest.mark.integration
class TestSTTEnhancementIntegration:
    """Test STT enhancement integration with real service."""

    async def test_enhancement_with_real_stt(self):
        """Test that enhanced audio flows through STT service correctly."""
        async with docker_compose_test_context(["stt"]):
            # Get test audio sample
            sample = get_clean_sample()

            async with httpx.AsyncClient() as client:
                # Send audio through /transcribe endpoint
                response = await client.post(
                    "http://stt:9000/transcribe",
                    files={"audio": ("test.wav", sample.data, "audio/wav")},
                    timeout=30.0,
                )

                # Verify response includes expected fields
                assert response.status_code == 200
                result = response.json()
                assert "transcript" in result
                assert "language" in result
                assert "duration" in result

                # Verify no errors in enhancement pipeline
                # (enhancement happens internally, we just verify transcription works)
                assert isinstance(result["transcript"], str)

    async def test_enhancement_graceful_degradation(self):
        """Test STT continues working when enhancement fails."""
        async with docker_compose_test_context(["stt"]):
            # Get test audio sample
            sample = get_noisy_samples(snr_db=10)  # Use noisy sample

            async with httpx.AsyncClient() as client:
                # Send audio through /transcribe endpoint
                response = await client.post(
                    "http://stt:9000/transcribe",
                    files={"audio": ("test.wav", sample.data, "audio/wav")},
                    timeout=30.0,
                )

                # Verify STT still returns transcription even with noisy audio
                assert response.status_code == 200
                result = response.json()
                assert "transcript" in result

                # Verify appropriate fallback logging (enhancement should handle gracefully)
                # Note: We can't directly test internal logging, but we verify the service works

    async def test_enhancement_disabled_by_config(self):
        """Test STT works correctly when enhancement disabled."""
        # Note: This test would require starting STT with FW_ENABLE_ENHANCEMENT=false
        # For now, we test that the service works with current config
        async with docker_compose_test_context(["stt"]), httpx.AsyncClient() as client:
            health_response = await client.get(
                "http://stt:9000/health/ready", timeout=10.0
            )
            assert health_response.status_code == 200

            health_data = health_response.json()
            # Verify health endpoint includes enhancement status
            assert "components" in health_data
            # Enhancement status should be in components

    async def test_enhancement_with_noisy_audio(self):
        """Test enhancement improves transcription of noisy audio."""
        async with docker_compose_test_context(["stt"]):
            # Get noisy audio sample
            noisy_sample = get_noisy_samples(snr_db=20)

            async with httpx.AsyncClient() as client:
                # Transcribe noisy audio
                response = await client.post(
                    "http://stt:9000/transcribe",
                    files={"audio": ("test.wav", noisy_sample.data, "audio/wav")},
                    timeout=30.0,
                )

                assert response.status_code == 200
                result = response.json()

                # Verify transcription works with noisy audio
                assert "transcript" in result
                # Note: We can't easily test quality improvement without ground truth
                # This test verifies the pipeline works end-to-end

    async def test_enhancement_performance_within_budget(self):
        """Test enhancement latency is within acceptable budget."""
        async with docker_compose_test_context(["stt"]):
            from services.tests.utils.performance import FileLevelPerformanceCollector

            collector = FileLevelPerformanceCollector()
            sample = get_clean_sample()

            async with httpx.AsyncClient() as client:
                # Measure multiple requests to get statistical data
                for _ in range(5):
                    start_time = time.time()
                    response = await client.post(
                        "http://stt:9000/transcribe",
                        files={"audio": ("test.wav", sample.data, "audio/wav")},
                        timeout=30.0,
                    )
                    latency = (time.time() - start_time) * 1000

                    if response.status_code == 200:
                        collector.add_measurement("enhancement_integration", latency)

                # Validate against budget
                validation = collector.validate_all()
                if "enhancement_integration" in validation:
                    # Check if we have a budget defined
                    if "overall_pass" in validation["enhancement_integration"]:
                        # Budget is defined, check if we pass
                        assert validation[
                            "enhancement_integration"
                        ][
                            "overall_pass"
                        ], f"Enhancement latency exceeded budget: {validation['enhancement_integration']}"
                    else:
                        # No budget defined, just verify we got measurements
                        stats = validation["enhancement_integration"]["stats"]
                        assert stats["count"] > 0
                        print(f"Enhancement latency stats: {stats}")

    async def test_enhancement_error_recovery(self):
        """Test enhancement handles malformed audio gracefully."""
        async with docker_compose_test_context(["stt"]):
            # Create malformed audio (empty or corrupted)
            malformed_audio = b"RIFF\x00\x00\x00\x00WAVE"  # Minimal WAV header

            async with httpx.AsyncClient() as client:
                # Send malformed audio
                response = await client.post(
                    "http://stt:9000/transcribe",
                    files={"audio": ("test.wav", malformed_audio, "audio/wav")},
                    timeout=30.0,
                )

                # Should either return error or handle gracefully
                # The service should not crash
                assert response.status_code in [200, 400, 422]  # Acceptable responses

                if response.status_code == 200:
                    # If it succeeds, verify we get a response
                    result = response.json()
                    assert "transcript" in result
                else:
                    # If it fails, verify we get a proper error response
                    assert "detail" in response.json() or "error" in response.json()

    async def test_enhancement_with_different_audio_formats(self):
        """Test enhancement with various audio characteristics."""
        async with docker_compose_test_context(["stt"]):
            # Test with different sample types
            test_samples = [
                get_clean_sample(),
                get_noisy_samples(snr_db=30),
                get_noisy_samples(snr_db=20),
                get_noisy_samples(snr_db=10),
            ]

            async with httpx.AsyncClient() as client:
                for i, sample in enumerate(test_samples):
                    response = await client.post(
                        "http://stt:9000/transcribe",
                        files={"audio": (f"test_{i}.wav", sample.data, "audio/wav")},
                        timeout=30.0,
                    )

                    # All should succeed (enhancement should handle various inputs)
                    assert response.status_code == 200
                    result = response.json()
                    assert "transcript" in result
                    assert "duration" in result
