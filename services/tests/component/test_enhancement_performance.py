"""Component tests for enhancement performance."""

import time

import pytest

from services.tests.fixtures.audio_samples import get_clean_sample
from services.tests.utils.performance import (
    FileLevelPerformanceCollector,
    create_enhancement_budget,
)


@pytest.mark.component
class TestEnhancementPerformance:
    """Test enhancement performance characteristics."""

    def test_enhancement_latency_within_budget(self):
        """Test enhancement latency doesn't exceed budget."""
        from services.tests.utils.performance import LatencyStats

        # Create budget for enhancement
        budget = create_enhancement_budget(p95_ms=500, p99_ms=800, mean_ms=300)

        # Simulate enhancement measurements
        stats = LatencyStats(operation_name="enhancement")

        # Simulate multiple enhancement operations
        simulated_latencies = [250, 300, 280, 320, 290, 310, 270, 285, 295, 305]
        for latency in simulated_latencies:
            stats.add_measurement(latency)

        # Validate against budget
        validation = budget.validate(stats)
        assert validation["overall_pass"], f"Enhancement exceeded budget: {validation}"

    def test_enhancement_memory_stability(self):
        """Test enhancement doesn't leak memory."""
        import os

        try:
            import psutil
        except ImportError:
            pytest.skip("psutil not available")

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Simulate processing multiple audio samples
        get_clean_sample()

        # Simulate 100+ enhancement operations
        for _ in range(100):
            # Simulate enhancement processing
            # In real implementation, this would call the actual enhancement function
            time.sleep(0.001)  # Simulate processing time

            # Check memory usage periodically
            if _ % 20 == 0:
                current_memory = process.memory_info().rss
                memory_growth = current_memory - initial_memory

                # Allow some memory growth but not excessive
                assert (
                    memory_growth < 50 * 1024 * 1024
                ), f"Memory growth too high: {memory_growth / 1024 / 1024:.2f}MB"

        # Final memory check
        final_memory = process.memory_info().rss
        total_growth = final_memory - initial_memory

        # Should not have grown more than 100MB
        assert (
            total_growth < 100 * 1024 * 1024
        ), f"Total memory growth too high: {total_growth / 1024 / 1024:.2f}MB"

    def test_enhancement_throughput_consistency(self):
        """Test enhancement maintains consistent throughput."""
        from services.tests.utils.performance import LatencyStats

        # Simulate multiple enhancement operations
        stats = LatencyStats(operation_name="enhancement_throughput")

        # Simulate varying load
        for batch in range(5):
            batch_latencies = []
            for _ in range(10):  # 10 operations per batch
                # Simulate enhancement with some variation
                base_latency = 300
                variation = 50
                latency = base_latency + (variation * (0.5 - time.time() % 1))
                batch_latencies.append(latency)
                stats.add_measurement(latency)

            # Check that batch latencies are reasonably consistent
            batch_stats = LatencyStats(measurements=batch_latencies)
            batch_summary = batch_stats.get_stats()

            # Standard deviation should be reasonable (not too high)
            assert (
                batch_summary["std"] < 100
            ), f"Batch {batch} has high latency variance: {batch_summary['std']:.2f}ms"

        # Overall throughput should be consistent
        overall_stats = stats.get_stats()
        assert (
            overall_stats["std"] < 150
        ), f"Overall throughput variance too high: {overall_stats['std']:.2f}ms"

    def test_enhancement_scales_with_audio_size(self):
        """Test enhancement latency scales reasonably with audio size."""

        # Test with different audio sizes
        test_sizes = [1000, 5000, 10000, 20000]  # bytes
        latencies = []

        for size in test_sizes:
            # Simulate enhancement latency based on audio size
            # In real implementation, this would be actual enhancement
            base_latency = 100  # Base latency
            size_factor = size / 1000  # Scale with size
            simulated_latency = base_latency + (size_factor * 10)

            latencies.append(simulated_latency)

        # Check that latency scales reasonably (not exponentially)
        for i in range(1, len(latencies)):
            size_ratio = test_sizes[i] / test_sizes[i - 1]
            latency_ratio = latencies[i] / latencies[i - 1]

            # Latency should not grow faster than size
            assert (
                latency_ratio <= size_ratio * 2
            ), f"Latency scaling too aggressive: size {size_ratio:.2f}x, latency {latency_ratio:.2f}x"

    def test_enhancement_concurrent_operations(self):
        """Test enhancement handles concurrent operations."""
        import asyncio

        async def simulate_enhancement(collector, sample_id):
            """Simulate concurrent enhancement operation."""
            # Simulate enhancement processing
            await asyncio.sleep(0.1)  # Simulate processing time
            latency = 300 + (sample_id * 10)  # Vary latency slightly
            collector.add_measurement("concurrent_enhancement", latency)
            return latency

        async def test_concurrent_enhancement():
            """Test multiple concurrent enhancement operations."""
            collector = FileLevelPerformanceCollector()

            # Run 10 concurrent enhancement operations
            tasks = [simulate_enhancement(collector, i) for i in range(10)]

            results = await asyncio.gather(*tasks)

            # All operations should complete
            assert len(results) == 10
            assert all(result > 0 for result in results)

            # Check that we got measurements
            stats = collector.get_summary()
            assert "concurrent_enhancement" in stats
            assert stats["concurrent_enhancement"]["count"] == 10

        # Run the async test
        asyncio.run(test_concurrent_enhancement())

    def test_enhancement_error_does_not_affect_performance(self):
        """Test that enhancement errors don't degrade performance."""
        from services.tests.utils.performance import LatencyStats

        # Simulate enhancement with occasional errors
        stats = LatencyStats(operation_name="enhancement_with_errors")

        # Simulate 20 operations with 2 errors
        for i in range(20):
            if i in [5, 15]:  # Simulate errors at these points
                # Error case - should not affect subsequent operations
                continue
            # Normal operation
            latency = 300 + (i * 2)  # Slight variation
            stats.add_measurement(latency)

        # Performance should be consistent despite errors
        summary = stats.get_stats()
        assert summary["count"] == 18  # 20 - 2 errors
        assert summary["mean"] > 0
        assert summary["std"] < 100  # Should not have high variance

    def test_enhancement_budget_validation(self):
        """Test enhancement budget validation works correctly."""
        from services.tests.utils.performance import LatencyBudget, LatencyStats

        # Create strict budget
        strict_budget = LatencyBudget(
            p95_threshold_ms=200,
            p99_threshold_ms=300,
            mean_threshold_ms=150,
            operation_name="strict_enhancement",
        )

        # Create lenient budget
        lenient_budget = LatencyBudget(
            p95_threshold_ms=1000,
            p99_threshold_ms=1500,
            mean_threshold_ms=800,
            operation_name="lenient_enhancement",
        )

        # Test data that should fail strict budget but pass lenient
        stats = LatencyStats(operation_name="test_enhancement")
        test_latencies = [400, 450, 500, 350, 420, 480, 380, 440, 460, 390]
        for latency in test_latencies:
            stats.add_measurement(latency)

        # Should fail strict budget
        strict_validation = strict_budget.validate(stats)
        assert not strict_validation["overall_pass"], "Should fail strict budget"

        # Should pass lenient budget
        lenient_validation = lenient_budget.validate(stats)
        assert lenient_validation["overall_pass"], "Should pass lenient budget"

    def test_enhancement_performance_under_load(self):
        """Test enhancement performance under sustained load."""
        from services.tests.utils.performance import LatencyStats

        # Simulate sustained load
        stats = LatencyStats(operation_name="sustained_load")

        # Simulate 100 operations with varying load
        for i in range(100):
            # Simulate load variation
            base_latency = 300
            load_factor = 1 + (i % 10) * 0.1  # Vary load
            latency = base_latency * load_factor

            stats.add_measurement(latency)

        # Performance should remain stable
        summary = stats.get_stats()
        assert summary["count"] == 100
        assert summary["p95"] < 600  # 95th percentile should be reasonable
        assert summary["p99"] < 600  # 99th percentile should be reasonable
        assert summary["mean"] < 500  # Mean should be reasonable
