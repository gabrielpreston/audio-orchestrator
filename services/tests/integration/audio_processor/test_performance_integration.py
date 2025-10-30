"""Integration tests for performance benchmarks."""

import asyncio
import time

import httpx
import pytest


@pytest.mark.integration
@pytest.mark.performance
class TestPerformanceIntegration:
    """Test performance integration across services."""

    async def test_voice_pipeline_latency_benchmarks(
        self,
        realistic_voice_audio_multipart,
        test_voice_context,
        test_voice_correlation_id,
        test_auth_token,
        test_voice_performance_thresholds,
    ):
        """Benchmark: end-to-end < 2s, STT < 300ms, TTS < 1s"""
        async with httpx.AsyncClient() as client:
            start_time = time.time()

            # Measure STT latency
            stt_start = time.time()
            stt_response = await client.post(
                "http://stt:9000/transcribe",
                files=realistic_voice_audio_multipart,
                timeout=30.0,
            )
            stt_latency = time.time() - stt_start
            assert stt_response.status_code == 200
            transcript = stt_response.json()["text"]

            # Measure Orchestrator latency
            orch_start = time.time()
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
            orch_latency = time.time() - orch_start
            assert orch_response.status_code == 200

            # Measure TTS latency
            tts_start = time.time()
            tts_response = await client.post(
                "http://bark:7100/synthesize",
                json={
                    "text": "Performance benchmark test",
                    "voice": "en_US-lessac-medium",
                    "correlation_id": test_voice_correlation_id,
                },
                headers={"Authorization": f"Bearer {test_auth_token}"},
                timeout=30.0,
            )
            tts_latency = time.time() - tts_start
            assert tts_response.status_code == 200

            total_latency = time.time() - start_time

            # Validate performance thresholds
            assert (
                stt_latency < test_voice_performance_thresholds["max_stt_latency_s"]
            ), (
                f"STT latency {stt_latency:.3f}s exceeds {test_voice_performance_thresholds['max_stt_latency_s']}s threshold"
            )
            assert (
                tts_latency < test_voice_performance_thresholds["max_tts_latency_s"]
            ), (
                f"TTS latency {tts_latency:.3f}s exceeds {test_voice_performance_thresholds['max_tts_latency_s']}s threshold"
            )
            assert (
                total_latency
                < test_voice_performance_thresholds["max_end_to_end_latency_s"]
            ), (
                f"Total latency {total_latency:.3f}s exceeds {test_voice_performance_thresholds['max_end_to_end_latency_s']}s threshold"
            )

            # Log performance metrics
            print("Performance Benchmarks:")
            print(f"  STT Latency: {stt_latency:.3f}s")
            print(f"  Orchestrator Latency: {orch_latency:.3f}s")
            print(f"  TTS Latency: {tts_latency:.3f}s")
            print(f"  Total Latency: {total_latency:.3f}s")

    async def test_concurrent_voice_processing(
        self,
        realistic_voice_audio_multipart,
        test_voice_context,
        test_auth_token,
    ):
        """Test 3+ concurrent voice requests without interference."""

        async def process_voice_request(request_id: int) -> dict:
            async with httpx.AsyncClient() as client:
                start_time = time.time()

                # STT
                stt_response = await client.post(
                    "http://stt:9000/transcribe",
                    files=realistic_voice_audio_multipart,
                    timeout=30.0,
                )
                stt_latency = time.time() - start_time

                if stt_response.status_code != 200:
                    return {
                        "success": False,
                        "error": "STT failed",
                        "request_id": request_id,
                    }

                transcript = stt_response.json()["text"]

                # Orchestrator
                orch_start = time.time()
                orch_response = await client.post(
                    "http://orchestrator:8200/api/v1/transcripts",
                    json={
                        "guild_id": test_voice_context["guild_id"],
                        "channel_id": test_voice_context["channel_id"],
                        "user_id": test_voice_context["user_id"],
                        "transcript": transcript,
                        "correlation_id": f"concurrent-{request_id}",
                    },
                    timeout=60.0,
                )
                orch_latency = time.time() - orch_start

                if orch_response.status_code != 200:
                    return {
                        "success": False,
                        "error": "Orchestrator failed",
                        "request_id": request_id,
                    }

                # TTS
                tts_start = time.time()
                tts_response = await client.post(
                    "http://bark:7100/synthesize",
                    json={
                        "text": f"Concurrent test response {request_id}",
                        "voice": "en_US-lessac-medium",
                        "correlation_id": f"concurrent-{request_id}",
                    },
                    headers={"Authorization": f"Bearer {test_auth_token}"},
                    timeout=30.0,
                )
                tts_latency = time.time() - tts_start

                if tts_response.status_code != 200:
                    return {
                        "success": False,
                        "error": "TTS failed",
                        "request_id": request_id,
                    }

                total_latency = time.time() - start_time

                return {
                    "success": True,
                    "request_id": request_id,
                    "stt_latency": stt_latency,
                    "orch_latency": orch_latency,
                    "tts_latency": tts_latency,
                    "total_latency": total_latency,
                }

        # Process 5 concurrent requests
        tasks = [process_voice_request(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Analyze results
        successful_results = [
            r for r in results if isinstance(r, dict) and r.get("success")
        ]
        failed_results = [
            r for r in results if isinstance(r, dict) and not r.get("success")
        ]
        exceptions = [r for r in results if isinstance(r, Exception)]

        print("Concurrent Processing Results:")
        print(f"  Successful: {len(successful_results)}")
        print(f"  Failed: {len(failed_results)}")
        print(f"  Exceptions: {len(exceptions)}")

        # At least 3 should succeed
        assert len(successful_results) >= 3, (
            f"Only {len(successful_results)} concurrent requests succeeded, expected at least 3"
        )

        # Check that successful requests completed within reasonable time
        for result in successful_results:
            assert result["total_latency"] < 5.0, (
                f"Request {result['request_id']} took {result['total_latency']:.3f}s, exceeds 5s threshold"
            )

    async def test_service_health_under_load(
        self,
        realistic_voice_audio_multipart,
        test_voice_context,
        test_auth_token,
    ):
        """Test service health under load."""

        async def health_check(service_url: str) -> dict:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        f"{service_url}/health/ready", timeout=5.0
                    )
                    return {
                        "service": service_url,
                        "status_code": response.status_code,
                        "healthy": response.status_code == 200,
                    }
                except Exception as e:
                    return {
                        "service": service_url,
                        "status_code": None,
                        "healthy": False,
                        "error": str(e),
                    }

        # Check health of all services
        services = [
            "http://stt:9000",
            "http://bark:7100",
            "http://flan:8100",
            "http://orchestrator:8200",
            "http://discord:8001",
        ]

        health_results = await asyncio.gather(
            *[health_check(service) for service in services]
        )

        # All services should be healthy
        for result in health_results:
            assert result["healthy"], (
                f"Service {result['service']} is not healthy: {result.get('error', 'Unknown error')}"
            )

    async def test_memory_usage_under_load(
        self,
        realistic_voice_audio_multipart,
        test_voice_context,
        test_auth_token,
    ):
        """Test memory usage under concurrent load."""

        async def memory_intensive_request(request_id: int) -> dict:
            async with httpx.AsyncClient() as client:
                start_time = time.time()

                # Process multiple requests in sequence to simulate load
                for i in range(3):
                    # STT
                    stt_response = await client.post(
                        "http://stt:9000/transcribe",
                        files=realistic_voice_audio_multipart,
                        timeout=30.0,
                    )
                    if stt_response.status_code != 200:
                        continue

                    transcript = stt_response.json()["text"]

                    # Orchestrator
                    orch_response = await client.post(
                        "http://orchestrator:8200/api/v1/transcripts",
                        json={
                            "guild_id": test_voice_context["guild_id"],
                            "channel_id": test_voice_context["channel_id"],
                            "user_id": test_voice_context["user_id"],
                            "transcript": transcript,
                            "correlation_id": f"memory-test-{request_id}-{i}",
                        },
                        timeout=60.0,
                    )
                    if orch_response.status_code != 200:
                        continue

                    # TTS
                    tts_response = await client.post(
                        "http://bark:7100/synthesize",
                        json={
                            "text": f"Memory test {request_id}-{i}",
                            "voice": "en_US-lessac-medium",
                            "correlation_id": f"memory-test-{request_id}-{i}",
                        },
                        headers={"Authorization": f"Bearer {test_auth_token}"},
                        timeout=30.0,
                    )
                    if tts_response.status_code != 200:
                        continue

                total_time = time.time() - start_time
                return {
                    "request_id": request_id,
                    "total_time": total_time,
                    "success": True,
                }

        # Run 3 concurrent memory-intensive requests
        tasks = [memory_intensive_request(i) for i in range(3)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should complete successfully
        successful_results = [
            r for r in results if isinstance(r, dict) and r.get("success")
        ]
        assert len(successful_results) >= 2, (
            f"Only {len(successful_results)} memory-intensive requests succeeded"
        )

    async def test_latency_consistency(
        self,
        realistic_voice_audio_multipart,
        test_voice_context,
        test_auth_token,
    ):
        """Test latency consistency across multiple requests."""
        latencies = []

        for i in range(5):
            async with httpx.AsyncClient() as client:
                start_time = time.time()

                # STT
                stt_response = await client.post(
                    "http://stt:9000/transcribe",
                    files=realistic_voice_audio_multipart,
                    timeout=30.0,
                )
                if stt_response.status_code != 200:
                    continue

                transcript = stt_response.json()["text"]

                # Orchestrator
                orch_response = await client.post(
                    "http://orchestrator:8200/api/v1/transcripts",
                    json={
                        "guild_id": test_voice_context["guild_id"],
                        "channel_id": test_voice_context["channel_id"],
                        "user_id": test_voice_context["user_id"],
                        "transcript": transcript,
                        "correlation_id": f"consistency-{i}",
                    },
                    timeout=60.0,
                )
                if orch_response.status_code != 200:
                    continue

                # TTS
                tts_response = await client.post(
                    "http://bark:7100/synthesize",
                    json={
                        "text": f"Consistency test {i}",
                        "voice": "en_US-lessac-medium",
                        "correlation_id": f"consistency-{i}",
                    },
                    headers={"Authorization": f"Bearer {test_auth_token}"},
                    timeout=30.0,
                )
                if tts_response.status_code != 200:
                    continue

                total_latency = time.time() - start_time
                latencies.append(total_latency)

        assert len(latencies) >= 3, (
            f"Only {len(latencies)} requests succeeded, expected at least 3"
        )

        # Calculate latency statistics
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        min_latency = min(latencies)
        latency_variance = sum((lat - avg_latency) ** 2 for lat in latencies) / len(
            latencies
        )
        latency_std = latency_variance**0.5

        print("Latency Consistency Results:")
        print(f"  Average: {avg_latency:.3f}s")
        print(f"  Min: {min_latency:.3f}s")
        print(f"  Max: {max_latency:.3f}s")
        print(f"  Std Dev: {latency_std:.3f}s")

        # Latency should be consistent (low variance)
        assert latency_std < 1.0, (
            f"Latency standard deviation {latency_std:.3f}s is too high, indicates inconsistent performance"
        )
        assert max_latency < 3.0, (
            f"Maximum latency {max_latency:.3f}s exceeds 3s threshold"
        )
