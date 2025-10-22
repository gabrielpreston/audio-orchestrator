"""Baseline measurement script for audio pipeline performance."""

import asyncio
import json
from pathlib import Path
import sys
import time
from typing import Any

import httpx

from services.tests.fixtures.audio_samples import (
    get_clean_sample,
    get_test_audio_samples,
)
from services.tests.utils.performance import (
    ChunkLevelPerformanceCollector,
    FileLevelPerformanceCollector,
)


class BaselineMeasurement:
    """Measure baseline performance of audio pipeline."""

    def __init__(self, stt_url: str = "http://localhost:9000"):
        self.stt_url = stt_url
        self.results: dict[str, Any] = {}

    async def measure_transcription_baseline(self) -> dict[str, Any]:
        """Measure baseline transcription performance without enhancement."""
        print("Measuring transcription baseline (no enhancement)...")

        # Get clean sample for baseline
        clean_sample = get_clean_sample()

        # Measure transcription latency
        collector = FileLevelPerformanceCollector()

        async with httpx.AsyncClient() as client:
            # Test transcription endpoint
            start_time = time.time()
            try:
                response = await client.post(
                    f"{self.stt_url}/transcribe",
                    files={"audio": ("test.wav", clean_sample.data, "audio/wav")},
                    timeout=30.0,
                )
                transcription_latency = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    result = response.json()
                    collector.add_measurement(
                        "transcription_baseline", transcription_latency
                    )

                    return {
                        "status": "success",
                        "latency_ms": transcription_latency,
                        "transcript": result.get("transcript", ""),
                        "stats": collector.get_summary(),
                    }
                else:
                    return {
                        "status": "error",
                        "error": f"HTTP {response.status_code}: {response.text}",
                        "latency_ms": transcription_latency,
                    }
            except Exception as e:
                return {"status": "error", "error": str(e), "latency_ms": float("inf")}

    async def measure_enhancement_overhead(self) -> dict[str, Any]:
        """Measure enhancement overhead when enabled."""
        print("Measuring enhancement overhead...")

        # Get test samples
        samples = get_test_audio_samples()
        collector = FileLevelPerformanceCollector()

        results = []

        async with httpx.AsyncClient() as client:
            for sample in samples[:3]:  # Test first 3 samples
                start_time = time.time()
                try:
                    response = await client.post(
                        f"{self.stt_url}/transcribe",
                        files={"audio": ("test.wav", sample.data, "audio/wav")},
                        timeout=30.0,
                    )
                    latency = (time.time() - start_time) * 1000

                    if response.status_code == 200:
                        result = response.json()
                        collector.add_measurement("enhancement_overhead", latency)

                        results.append(
                            {
                                "sample_type": sample.noise_type,
                                "snr_db": sample.snr_db,
                                "latency_ms": latency,
                                "transcript": result.get("transcript", ""),
                                "status": "success",
                            }
                        )
                    else:
                        results.append(
                            {
                                "sample_type": sample.noise_type,
                                "snr_db": sample.snr_db,
                                "latency_ms": latency,
                                "status": "error",
                                "error": f"HTTP {response.status_code}",
                            }
                        )
                except Exception as e:
                    results.append(
                        {
                            "sample_type": sample.noise_type,
                            "snr_db": sample.snr_db,
                            "latency_ms": float("inf"),
                            "status": "error",
                            "error": str(e),
                        }
                    )

        return {"enhancement_results": results, "stats": collector.get_summary()}

    async def measure_chunk_level_performance(self) -> dict[str, Any]:
        """Measure chunk-level performance (simulated)."""
        print("Measuring chunk-level performance...")

        # Simulate chunk-level processing
        collector = ChunkLevelPerformanceCollector()

        # Get a sample and simulate chunking
        sample = get_clean_sample()
        chunk_size = 1024  # 1KB chunks
        chunks = [
            sample.data[i : i + chunk_size]
            for i in range(0, len(sample.data), chunk_size)
        ]

        chunk_results = []
        for i, chunk in enumerate(chunks[:10]):  # Process first 10 chunks
            start_time = time.time()

            # Simulate chunk processing (enhancement + transcription)
            await asyncio.sleep(0.01)  # Simulate processing time

            latency = (time.time() - start_time) * 1000
            collector.add_measurement("chunk_processing", latency)

            chunk_results.append(
                {"chunk_index": i, "chunk_size": len(chunk), "latency_ms": latency}
            )

        return {"chunk_results": chunk_results, "stats": collector.get_summary()}

    async def check_service_health(self) -> dict[str, Any]:
        """Check STT service health and configuration."""
        print("Checking service health...")

        async with httpx.AsyncClient() as client:
            try:
                # Check health endpoint
                health_response = await client.get(
                    f"{self.stt_url}/health/ready", timeout=10.0
                )

                if health_response.status_code == 200:
                    health_data = health_response.json()
                    return {
                        "status": "healthy",
                        "health_data": health_data,
                        "enhancement_enabled": health_data.get("components", {}).get(
                            "enhancer_loaded", False
                        ),
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "error": f"Health check failed: {health_response.status_code}",
                    }
            except Exception as e:
                return {"status": "error", "error": str(e)}

    async def run_full_baseline(self) -> dict[str, Any]:
        """Run complete baseline measurement."""
        print("=== Audio Pipeline Baseline Measurement ===")

        start_time = time.time()

        # Check service health first
        health_result = await self.check_service_health()
        if health_result["status"] != "healthy":
            return {
                "status": "error",
                "error": "Service not healthy",
                "health_result": health_result,
            }

        # Run measurements
        results = {
            "measurement_timestamp": time.time(),
            "service_health": health_result,
            "transcription_baseline": await self.measure_transcription_baseline(),
            "enhancement_overhead": await self.measure_enhancement_overhead(),
            "chunk_performance": await self.measure_chunk_level_performance(),
        }

        total_time = time.time() - start_time
        results["total_measurement_time_seconds"] = total_time

        print(f"Baseline measurement completed in {total_time:.2f} seconds")

        return results

    def save_results(
        self, results: dict[str, Any], output_file: str = "baseline_results.json"
    ) -> None:
        """Save results to JSON file."""
        output_path = Path(output_file)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {output_path.absolute()}")


async def main():
    """Run baseline measurement."""
    measurement = BaselineMeasurement()

    try:
        results = await measurement.run_full_baseline()
        measurement.save_results(results)

        # Print summary
        print("\n=== Baseline Measurement Summary ===")
        if "transcription_baseline" in results:
            baseline = results["transcription_baseline"]
            if baseline["status"] == "success":
                print(f"Transcription latency: {baseline['latency_ms']:.2f}ms")
            else:
                print(f"Transcription error: {baseline.get('error', 'Unknown')}")

        if "enhancement_overhead" in results:
            overhead = results["enhancement_overhead"]
            if "stats" in overhead:
                stats = overhead["stats"]
                if "enhancement_overhead" in stats:
                    enhancement_stats = stats["enhancement_overhead"]
                    print(
                        f"Enhancement p95 latency: {enhancement_stats.get('p95', 0):.2f}ms"
                    )
                    print(
                        f"Enhancement mean latency: {enhancement_stats.get('mean', 0):.2f}ms"
                    )

        if "chunk_performance" in results:
            chunk_perf = results["chunk_performance"]
            if "stats" in chunk_perf:
                stats = chunk_perf["stats"]
                if "chunk_processing" in stats:
                    chunk_stats = stats["chunk_processing"]
                    print(
                        f"Chunk processing p95 latency: {chunk_stats.get('p95', 0):.2f}ms"
                    )
                    print(
                        f"Chunk processing mean latency: {chunk_stats.get('mean', 0):.2f}ms"
                    )

    except Exception as e:
        print(f"Baseline measurement failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
