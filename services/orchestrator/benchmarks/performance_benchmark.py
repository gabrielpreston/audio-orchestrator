"""Performance benchmarking script for audio orchestrator.

This script benchmarks the performance improvements made to the audio pipeline
and measures the impact of optimizations.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from services.common.logging import get_logger
from services.orchestrator.adapters.types import AudioChunk, AudioMetadata
from services.orchestrator.pipeline.audio_processor import AudioProcessor
from services.orchestrator.pipeline.optimized_audio_processor import (
    OptimizedAudioProcessor,
)
from services.orchestrator.pipeline.types import ProcessingConfig, ProcessingStatus

logger = get_logger(__name__)


class PerformanceBenchmark:
    """Performance benchmark for audio processing optimizations."""

    def __init__(self) -> None:
        """Initialize performance benchmark."""
        self._logger = get_logger(__name__)
        self._results: dict[str, Any] = {}

    async def run_benchmark(self, num_chunks: int = 100) -> dict[str, Any]:
        """Run comprehensive performance benchmark.

        Args:
            num_chunks: Number of audio chunks to process

        Returns:
            Benchmark results
        """
        self._logger.info("performance_benchmark.starting", num_chunks=num_chunks)

        # Test data
        test_chunks = self._generate_test_chunks(num_chunks)
        config = ProcessingConfig()

        # Benchmark original processor
        original_results = await self._benchmark_original_processor(test_chunks, config)

        # Benchmark optimized processor
        optimized_results = await self._benchmark_optimized_processor(
            test_chunks, config
        )

        # Calculate improvements
        improvements = self._calculate_improvements(original_results, optimized_results)

        self._results = {
            "original": original_results,
            "optimized": optimized_results,
            "improvements": improvements,
            "benchmark_config": {
                "num_chunks": num_chunks,
                "chunk_size_bytes": len(test_chunks[0].data),
            },
        }

        self._logger.info(
            "performance_benchmark.completed",
            improvements=improvements,
        )

        return self._results

    def _generate_test_chunks(self, num_chunks: int) -> list[AudioChunk]:
        """Generate test audio chunks.

        Args:
            num_chunks: Number of chunks to generate

        Returns:
            List of test audio chunks
        """
        chunks = []
        for i in range(num_chunks):
            # Generate realistic audio data (20ms of 16kHz mono PCM)
            chunk_size = 640  # 20ms * 16kHz * 2 bytes
            audio_data = bytes([(i + j) % 256 for j in range(chunk_size)])

            chunk = AudioChunk(
                data=audio_data,
                correlation_id=f"test-{i}",
                sequence_number=i,
                metadata=AudioMetadata(
                    sample_rate=16000,
                    channels=1,
                    sample_width=2,
                    duration=0.02,
                    frames=320,
                    format="pcm",
                    bit_depth=16,
                ),
            )
            chunks.append(chunk)

        return chunks

    async def _benchmark_original_processor(
        self, chunks: list[AudioChunk], config: ProcessingConfig
    ) -> dict[str, Any]:
        """Benchmark original audio processor.

        Args:
            chunks: Audio chunks to process
            config: Processing configuration

        Returns:
            Benchmark results
        """
        self._logger.info("performance_benchmark.benchmarking_original")

        processor = AudioProcessor(config)
        start_time = time.perf_counter()

        # Process all chunks
        results = []
        for chunk in chunks:
            result = await processor.process_audio_chunk(chunk, "benchmark-session")
            results.append(result)

        total_time = time.perf_counter() - start_time

        return {
            "total_time": total_time,
            "avg_time_per_chunk": total_time / len(chunks),
            "chunks_processed": len(chunks),
            "successful_chunks": sum(
                1 for r in results if r.status == ProcessingStatus.COMPLETED
            ),
            "failed_chunks": sum(
                1 for r in results if r.status == ProcessingStatus.FAILED
            ),
            "avg_processing_time": sum(r.processing_time for r in results)
            / len(results),
            "total_audio_data": sum(len(r.audio_data) for r in results),
        }

    async def _benchmark_optimized_processor(
        self, chunks: list[AudioChunk], config: ProcessingConfig
    ) -> dict[str, Any]:
        """Benchmark optimized audio processor.

        Args:
            chunks: Audio chunks to process
            config: Processing configuration

        Returns:
            Benchmark results
        """
        self._logger.info("performance_benchmark.benchmarking_optimized")

        processor = OptimizedAudioProcessor(config)
        start_time = time.perf_counter()

        # Process all chunks
        results = []
        for chunk in chunks:
            result = await processor.process_audio_chunk(chunk, "benchmark-session")
            results.append(result)

        total_time = time.perf_counter() - start_time

        # Get performance stats
        performance_stats = await processor.get_performance_stats()

        return {
            "total_time": total_time,
            "avg_time_per_chunk": total_time / len(chunks),
            "chunks_processed": len(chunks),
            "successful_chunks": sum(
                1 for r in results if r.status == ProcessingStatus.COMPLETED
            ),
            "failed_chunks": sum(
                1 for r in results if r.status == ProcessingStatus.FAILED
            ),
            "avg_processing_time": sum(r.processing_time for r in results)
            / len(results),
            "total_audio_data": sum(len(r.audio_data) for r in results),
            "performance_stats": performance_stats,
        }

    def _calculate_improvements(
        self, original: dict[str, Any], optimized: dict[str, Any]
    ) -> dict[str, Any]:
        """Calculate performance improvements.

        Args:
            original: Original processor results
            optimized: Optimized processor results

        Returns:
            Improvement metrics
        """
        # Safely calculate improvements with zero-division checks
        time_improvement = (
            (original["total_time"] - optimized["total_time"])
            / original["total_time"]
            * 100
            if original["total_time"] > 0
            else 0.0
        )
        avg_time_improvement = (
            (original["avg_time_per_chunk"] - optimized["avg_time_per_chunk"])
            / original["avg_time_per_chunk"]
            * 100
            if original["avg_time_per_chunk"] > 0
            else 0.0
        )
        processing_time_improvement = (
            (original["avg_processing_time"] - optimized["avg_processing_time"])
            / original["avg_processing_time"]
            * 100
            if original["avg_processing_time"] > 0
            else 0.0
        )

        return {
            "total_time_improvement_percent": time_improvement,
            "avg_time_per_chunk_improvement_percent": avg_time_improvement,
            "processing_time_improvement_percent": processing_time_improvement,
            "throughput_improvement": {
                "original_chunks_per_second": (
                    original["chunks_processed"] / original["total_time"]
                    if original["total_time"] > 0
                    else 0.0
                ),
                "optimized_chunks_per_second": (
                    optimized["chunks_processed"] / optimized["total_time"]
                    if optimized["total_time"] > 0
                    else 0.0
                ),
            },
            "reliability": {
                "original_success_rate": (
                    original["successful_chunks"] / original["chunks_processed"] * 100
                    if original["chunks_processed"] > 0
                    else 0.0
                ),
                "optimized_success_rate": (
                    optimized["successful_chunks"] / optimized["chunks_processed"] * 100
                    if optimized["chunks_processed"] > 0
                    else 0.0
                ),
            },
        }

    def print_results(self) -> None:
        """Print benchmark results in a formatted way."""
        if not self._results:
            self._logger.warning("performance_benchmark.no_results")
            return

        print("\n" + "=" * 80)
        print("AUDIO ORCHESTRATOR PERFORMANCE BENCHMARK RESULTS")
        print("=" * 80)

        # Original results
        original = self._results["original"]
        print("\n📊 ORIGINAL PROCESSOR:")
        print(f"   Total Time: {original['total_time']:.3f}s")
        print(f"   Avg Time per Chunk: {original['avg_time_per_chunk']:.3f}s")
        print(f"   Chunks Processed: {original['chunks_processed']}")
        success_rate_original = (
            original["successful_chunks"] / original["chunks_processed"] * 100
            if original["chunks_processed"] > 0
            else 0.0
        )
        print(f"   Success Rate: {success_rate_original:.1f}%")
        print(f"   Avg Processing Time: {original['avg_processing_time']:.3f}s")

        # Optimized results
        optimized = self._results["optimized"]
        print("\n🚀 OPTIMIZED PROCESSOR:")
        print(f"   Total Time: {optimized['total_time']:.3f}s")
        print(f"   Avg Time per Chunk: {optimized['avg_time_per_chunk']:.3f}s")
        print(f"   Chunks Processed: {optimized['chunks_processed']}")
        success_rate_optimized = (
            optimized["successful_chunks"] / optimized["chunks_processed"] * 100
            if optimized["chunks_processed"] > 0
            else 0.0
        )
        print(f"   Success Rate: {success_rate_optimized:.1f}%")
        print(f"   Avg Processing Time: {optimized['avg_processing_time']:.3f}s")

        # Improvements
        improvements = self._results["improvements"]
        print("\n📈 PERFORMANCE IMPROVEMENTS:")
        print(
            f"   Total Time Improvement: {improvements['total_time_improvement_percent']:.1f}%"
        )
        print(
            f"   Avg Time per Chunk Improvement: {improvements['avg_time_per_chunk_improvement_percent']:.1f}%"
        )
        print(
            f"   Processing Time Improvement: {improvements['processing_time_improvement_percent']:.1f}%"
        )

        throughput = improvements["throughput_improvement"]
        print("   Throughput Improvement:")
        print(
            f"     Original: {throughput['original_chunks_per_second']:.1f} chunks/sec"
        )
        print(
            f"     Optimized: {throughput['optimized_chunks_per_second']:.1f} chunks/sec"
        )

        reliability = improvements["reliability"]
        print("   Reliability:")
        print(
            f"     Original Success Rate: {reliability['original_success_rate']:.1f}%"
        )
        print(
            f"     Optimized Success Rate: {reliability['optimized_success_rate']:.1f}%"
        )

        print("\n" + "=" * 80)


async def main() -> dict[str, Any]:
    """Run performance benchmark."""
    benchmark = PerformanceBenchmark()
    results = await benchmark.run_benchmark(num_chunks=100)
    benchmark.print_results()
    return results


if __name__ == "__main__":
    asyncio.run(main())
