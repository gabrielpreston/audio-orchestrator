"""Integration tests for complete voice pipeline."""

import time
from io import BytesIO

import httpx
import pytest


@pytest.mark.integration
class TestVoicePipelineIntegration:
    """Test complete voice pipeline integration."""

    async def test_complete_voice_feedback_loop(
        self,
        realistic_voice_audio_multipart,
        test_voice_context,
        test_voice_correlation_id,
        test_auth_token,
    ):
        """Test complete: Audio → STT → Orchestrator → LLM → TTS → Audio"""
        start_time = time.time()

        async with httpx.AsyncClient() as client:
            # Step 1: STT transcription (using multipart form data)
            stt_start = time.time()
            stt_response = await client.post(
                "http://stt:9000/transcribe",
                files=realistic_voice_audio_multipart,
                timeout=30.0,
            )
            stt_latency = time.time() - stt_start
            assert stt_response.status_code == 200
            stt_data = stt_response.json()
            assert "text" in stt_data
            transcript = stt_data["text"]
            assert len(transcript) > 0

            # Step 2: Orchestrator processing (CORRECTED endpoint)
            orch_start = time.time()
            orch_response = await client.post(
                "http://orchestrator:8200/api/v1/transcripts",  # CORRECTED
                json={
                    "guild_id": test_voice_context["guild_id"],
                    "channel_id": test_voice_context["channel_id"],
                    "user_id": test_voice_context["user_id"],
                    "transcript": transcript,
                    "correlation_id": test_voice_correlation_id,
                },
                timeout=60.0,
            )
            _ = time.time() - orch_start
            assert orch_response.status_code == 200
            orch_data = orch_response.json()
            assert "status" in orch_data

            # Step 3: TTS synthesis
            tts_start = time.time()
            tts_response = await client.post(
                "http://bark:7100/synthesize",
                json={
                    "text": "Test response from voice pipeline",
                    "voice": "en_US-lessac-medium",
                    "correlation_id": test_voice_correlation_id,
                },
                headers={"Authorization": f"Bearer {test_auth_token}"},
                timeout=30.0,
            )
            tts_latency = time.time() - tts_start
            assert tts_response.status_code == 200

            # Step 4: Validate audio output format
            assert tts_response.headers["content-type"] == "audio/wav"
            audio_data = tts_response.content
            assert len(audio_data) > 0

            # Step 5: Verify correlation ID propagation
            assert stt_data.get("correlation_id") is not None
            assert orch_data.get("correlation_id") == test_voice_correlation_id

            # Step 6: Validate end-to-end latency < 2s
            total_latency = time.time() - start_time
            assert (
                total_latency < 2.0
            ), f"Total latency {total_latency:.2f}s exceeds 2s threshold"

            # Validate individual service latencies
            assert (
                stt_latency < 0.3
            ), f"STT latency {stt_latency:.2f}s exceeds 0.3s threshold"
            assert (
                tts_latency < 1.0
            ), f"TTS latency {tts_latency:.2f}s exceeds 1.0s threshold"

    async def test_voice_pipeline_with_real_audio_file(
        self,
        realistic_voice_audio,
        test_voice_context,
        test_voice_correlation_id,
        test_auth_token,
    ):
        """Test voice pipeline with real audio file data."""
        # Create multipart form data from real audio
        files = {
            "file": ("test_voice.wav", BytesIO(realistic_voice_audio), "audio/wav")
        }

        async with httpx.AsyncClient() as client:
            # Complete pipeline test
            stt_response = await client.post(
                "http://stt:9000/transcribe",
                files=files,
                timeout=30.0,
            )
            assert stt_response.status_code == 200
            stt_data = stt_response.json()
            transcript = stt_data["text"]

            # Test orchestrator processing
            orch_response = await client.post(
                "http://orchestrator:8200/api/v1/transcripts",
                json={
                    "guild_id": test_voice_context["guild_id"],
                    "channel_id": test_voice_context["channel_id"],
                    "user_id": test_voice_context["user_id"],
                    "transcript": transcript,
                    "correlation_id": test_voice_correlation_id,
                },
                timeout=60.0,
            )
            assert orch_response.status_code == 200

            # Test TTS synthesis
            tts_response = await client.post(
                "http://bark:7100/synthesize",
                json={
                    "text": f"Response to: {transcript}",
                    "voice": "en_US-lessac-medium",
                    "correlation_id": test_voice_correlation_id,
                },
                headers={"Authorization": f"Bearer {test_auth_token}"},
                timeout=30.0,
            )
            assert tts_response.status_code == 200
            assert tts_response.headers["content-type"] == "audio/wav"

    async def test_voice_pipeline_error_recovery(
        self,
        test_voice_context,
        test_voice_correlation_id,
        test_auth_token,
    ):
        """Test voice pipeline error recovery."""
        async with httpx.AsyncClient() as client:
            # Test with invalid audio data
            invalid_files = {"file": ("invalid.wav", b"not audio data", "audio/wav")}
            stt_response = await client.post(
                "http://stt:9000/transcribe",
                files=invalid_files,
                timeout=30.0,
            )
            # Should handle gracefully - either return error or process anyway
            assert stt_response.status_code in [200, 400, 422]

            # Test with empty transcript
            orch_response = await client.post(
                "http://orchestrator:8200/api/v1/transcripts",
                json={
                    "guild_id": test_voice_context["guild_id"],
                    "channel_id": test_voice_context["channel_id"],
                    "user_id": test_voice_context["user_id"],
                    "transcript": "",  # Empty transcript
                    "correlation_id": test_voice_correlation_id,
                },
                timeout=60.0,
            )
            # Should handle empty transcript gracefully
            assert orch_response.status_code in [200, 400, 422]

    async def test_voice_pipeline_concurrent_requests(
        self,
        realistic_voice_audio_multipart,
        test_voice_context,
        test_auth_token,
    ):
        """Test concurrent voice pipeline requests."""
        import asyncio

        async def process_voice_request(correlation_id: str):
            async with httpx.AsyncClient() as client:
                # STT
                stt_response = await client.post(
                    "http://stt:9000/transcribe",
                    files=realistic_voice_audio_multipart,
                    timeout=30.0,
                )
                if stt_response.status_code != 200:
                    return None

                transcript = stt_response.json()["text"]

                # Orchestrator
                orch_response = await client.post(
                    "http://orchestrator:8200/api/v1/transcripts",
                    json={
                        "guild_id": test_voice_context["guild_id"],
                        "channel_id": test_voice_context["channel_id"],
                        "user_id": test_voice_context["user_id"],
                        "transcript": transcript,
                        "correlation_id": correlation_id,
                    },
                    timeout=60.0,
                )
                if orch_response.status_code != 200:
                    return None

                # TTS
                tts_response = await client.post(
                    "http://bark:7100/synthesize",
                    json={
                        "text": f"Response {correlation_id}",
                        "voice": "en_US-lessac-medium",
                        "correlation_id": correlation_id,
                    },
                    headers={"Authorization": f"Bearer {test_auth_token}"},
                    timeout=30.0,
                )
                return tts_response.status_code == 200

        # Process 3 concurrent requests
        tasks = [process_voice_request(f"concurrent-{i}") for i in range(3)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # At least some should succeed
        success_count = sum(1 for result in results if result is True)
        assert success_count > 0, "No concurrent requests succeeded"

    async def test_voice_pipeline_correlation_id_consistency(
        self,
        realistic_voice_audio_multipart,
        test_voice_context,
        test_voice_correlation_id,
        test_auth_token,
    ):
        """Test correlation ID consistency through entire pipeline."""
        async with httpx.AsyncClient() as client:
            # Process complete pipeline
            stt_response = await client.post(
                "http://stt:9000/transcribe",
                files=realistic_voice_audio_multipart,
                timeout=30.0,
            )
            assert stt_response.status_code == 200
            stt_data = stt_response.json()

            # Verify STT returns correlation ID
            assert "correlation_id" in stt_data

            # Use STT correlation ID for orchestrator
            orch_response = await client.post(
                "http://orchestrator:8200/api/v1/transcripts",
                json={
                    "guild_id": test_voice_context["guild_id"],
                    "channel_id": test_voice_context["channel_id"],
                    "user_id": test_voice_context["user_id"],
                    "transcript": stt_data["text"],
                    "correlation_id": stt_data["correlation_id"],
                },
                timeout=60.0,
            )
            assert orch_response.status_code == 200
            orch_data = orch_response.json()

            # Verify orchestrator preserves correlation ID
            assert orch_data.get("correlation_id") == stt_data["correlation_id"]

            # Use same correlation ID for TTS
            tts_response = await client.post(
                "http://bark:7100/synthesize",
                json={
                    "text": "Test response",
                    "voice": "en_US-lessac-medium",
                    "correlation_id": stt_data["correlation_id"],
                },
                headers={"Authorization": f"Bearer {test_auth_token}"},
                timeout=30.0,
            )
            assert tts_response.status_code == 200

    async def test_voice_pipeline_performance_benchmarks(
        self,
        realistic_voice_audio_multipart,
        test_voice_context,
        test_voice_correlation_id,
        test_auth_token,
    ):
        """Benchmark voice pipeline performance."""
        async with httpx.AsyncClient() as client:
            start_time = time.time()

            # Measure STT performance
            stt_start = time.time()
            stt_response = await client.post(
                "http://stt:9000/transcribe",
                files=realistic_voice_audio_multipart,
                timeout=30.0,
            )
            stt_latency = time.time() - stt_start
            assert stt_response.status_code == 200

            # Measure Orchestrator performance
            orch_start = time.time()
            orch_response = await client.post(
                "http://orchestrator:8200/api/v1/transcripts",
                json={
                    "guild_id": test_voice_context["guild_id"],
                    "channel_id": test_voice_context["channel_id"],
                    "user_id": test_voice_context["user_id"],
                    "transcript": stt_response.json()["text"],
                    "correlation_id": test_voice_correlation_id,
                },
                timeout=60.0,
            )
            _ = time.time() - orch_start
            assert orch_response.status_code == 200

            # Measure TTS performance
            tts_start = time.time()
            tts_response = await client.post(
                "http://bark:7100/synthesize",
                json={
                    "text": "Performance test response",
                    "voice": "en_US-lessac-medium",
                    "correlation_id": test_voice_correlation_id,
                },
                headers={"Authorization": f"Bearer {test_auth_token}"},
                timeout=30.0,
            )
            tts_latency = time.time() - tts_start
            assert tts_response.status_code == 200

            total_latency = time.time() - start_time

            # Log performance metrics
            print(f"STT Latency: {stt_latency:.3f}s")
            print(f"TTS Latency: {tts_latency:.3f}s")
            print(f"Total Latency: {total_latency:.3f}s")

            # Validate performance thresholds
            assert (
                stt_latency < 0.3
            ), f"STT latency {stt_latency:.3f}s exceeds 0.3s threshold"
            assert (
                tts_latency < 1.0
            ), f"TTS latency {tts_latency:.3f}s exceeds 1.0s threshold"
            assert (
                total_latency < 2.0
            ), f"Total latency {total_latency:.3f}s exceeds 2.0s threshold"
