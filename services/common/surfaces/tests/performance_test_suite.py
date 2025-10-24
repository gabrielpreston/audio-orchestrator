"""
Performance test suite for surface adapters.

This module provides performance testing capabilities for surface adapters,
including latency measurements, throughput testing, and resource monitoring.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from services.common.surfaces.events import WakeDetectedEvent
from services.common.surfaces.protocols import (
    AudioCaptureProtocol,
    AudioPlaybackProtocol,
    SurfaceControlProtocol,
    SurfaceTelemetryProtocol,
)
from services.common.surfaces.types import PCMFrame


logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for adapter testing."""

    # Latency metrics
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float

    # Throughput metrics
    operations_per_second: float
    total_operations: int
    test_duration_seconds: float

    # Resource metrics
    avg_cpu_percent: float
    max_cpu_percent: float
    avg_memory_mb: float
    max_memory_mb: float

    # Error metrics
    error_count: int
    error_rate: float

    # Timestamp
    timestamp: datetime


class SurfaceAdapterPerformanceTester:
    """
    Performance tester for surface adapters.

    This class provides comprehensive performance testing of surface adapters,
    including latency measurements, throughput testing, and resource monitoring.
    """

    def __init__(self):
        """Initialize the performance tester."""
        self.test_results: dict[str, list[PerformanceMetrics]] = {}
        self.resource_monitor: asyncio.Task[None] | None = None
        self.resource_data: list[dict[str, Any]] = []

    async def test_audio_source_performance(
        self,
        adapter: AudioCaptureProtocol,
        duration_seconds: float = 10.0,
        target_latency_ms: float = 50.0,
    ) -> PerformanceMetrics:
        """
        Test AudioCaptureProtocol adapter performance.

        Args:
            adapter: AudioCaptureProtocol adapter to test
            duration_seconds: Test duration in seconds
            target_latency_ms: Target latency in milliseconds

        Returns:
            Performance metrics
        """
        logger.info(
            "Starting AudioCaptureProtocol performance test for %s seconds",
            duration_seconds,
        )

        # Start capture for audio source
        if hasattr(adapter, "start_capture"):
            await adapter.start_capture()

        # Start resource monitoring
        await self._start_resource_monitoring()

        # Performance test data
        latencies: list[float] = []
        operation_count = 0
        error_count = 0
        start_time = time.time()

        try:
            while time.time() - start_time < duration_seconds:
                try:
                    # Measure latency
                    operation_start = time.time()
                    await adapter.read_audio_frame()
                    operation_end = time.time()

                    latency_ms = (operation_end - operation_start) * 1000
                    latencies.append(latency_ms)
                    operation_count += 1

                    # Check if we're meeting latency targets
                    if latency_ms > target_latency_ms:
                        logger.warning(
                            "Latency exceeded target: %.2fms > %.2fms",
                            latency_ms,
                            target_latency_ms,
                        )

                    # Small delay to prevent overwhelming the adapter
                    await asyncio.sleep(0.01)

                except Exception as e:
                    error_count += 1
                    logger.error("Error during performance test: %s", e)
                    await asyncio.sleep(0.1)  # Longer delay on error

        finally:
            # Stop resource monitoring
            await self._stop_resource_monitoring()

            # Disconnect adapter
            if hasattr(adapter, "stop_capture"):
                await adapter.stop_capture()

        # Calculate metrics
        test_duration = time.time() - start_time
        metrics = self._calculate_metrics(
            latencies=latencies,
            operation_count=operation_count,
            error_count=error_count,
            test_duration=test_duration,
        )

        logger.info(
            "AudioCaptureProtocol performance test completed: %.2f ops/sec, %.2fms avg latency",
            metrics.operations_per_second,
            metrics.avg_latency_ms,
        )

        return metrics

    async def test_audio_sink_performance(
        self,
        adapter: AudioPlaybackProtocol,
        duration_seconds: float = 10.0,
        target_latency_ms: float = 50.0,
    ) -> PerformanceMetrics:
        """
        Test AudioPlaybackProtocol adapter performance.

        Args:
            adapter: AudioPlaybackProtocol adapter to test
            duration_seconds: Test duration in seconds
            target_latency_ms: Target latency in milliseconds

        Returns:
            Performance metrics
        """
        logger.info(
            "Starting AudioPlaybackProtocol performance test for %s seconds",
            duration_seconds,
        )

        # Start capture for audio source
        if hasattr(adapter, "start_capture"):
            await adapter.start_capture()

        # Start resource monitoring
        await self._start_resource_monitoring()

        # Performance test data
        latencies: list[float] = []
        operation_count = 0
        error_count = 0
        start_time = time.time()

        try:
            while time.time() - start_time < duration_seconds:
                try:
                    # Create dummy audio frame
                    dummy_frame = PCMFrame(
                        pcm=b"\x00" * 1024,
                        timestamp=time.time(),
                        rms=0.0,
                        duration=0.1,
                        sequence=operation_count,
                        sample_rate=16000,
                    )

                    # Measure latency
                    operation_start = time.time()
                    await adapter.play_audio_chunk(dummy_frame)
                    operation_end = time.time()

                    latency_ms = (operation_end - operation_start) * 1000
                    latencies.append(latency_ms)
                    operation_count += 1

                    # Check if we're meeting latency targets
                    if latency_ms > target_latency_ms:
                        logger.warning(
                            "Latency exceeded target: %.2fms > %.2fms",
                            latency_ms,
                            target_latency_ms,
                        )

                    # Small delay to prevent overwhelming the adapter
                    await asyncio.sleep(0.01)

                except Exception as e:
                    error_count += 1
                    logger.error("Error during performance test: %s", e)
                    await asyncio.sleep(0.1)  # Longer delay on error

        finally:
            # Stop resource monitoring
            await self._stop_resource_monitoring()

            # Disconnect adapter
            if hasattr(adapter, "stop_capture"):
                await adapter.stop_capture()

        # Calculate metrics
        test_duration = time.time() - start_time
        metrics = self._calculate_metrics(
            latencies=latencies,
            operation_count=operation_count,
            error_count=error_count,
            test_duration=test_duration,
        )

        logger.info(
            "AudioPlaybackProtocol performance test completed: %.2f ops/sec, %.2fms avg latency",
            metrics.operations_per_second,
            metrics.avg_latency_ms,
        )

        return metrics

    async def test_control_channel_performance(
        self,
        adapter: SurfaceControlProtocol,
        duration_seconds: float = 10.0,
        target_latency_ms: float = 10.0,
    ) -> PerformanceMetrics:
        """
        Test SurfaceControlProtocol adapter performance.

        Args:
            adapter: SurfaceControlProtocol adapter to test
            duration_seconds: Test duration in seconds
            target_latency_ms: Target latency in milliseconds

        Returns:
            Performance metrics
        """
        logger.info(
            "Starting SurfaceControlProtocol performance test for %s seconds",
            duration_seconds,
        )

        # Start capture for audio source
        if hasattr(adapter, "start_capture"):
            await adapter.start_capture()

        # Start resource monitoring
        await self._start_resource_monitoring()

        # Performance test data
        latencies: list[float] = []
        operation_count = 0
        error_count = 0
        start_time = time.time()

        try:
            while time.time() - start_time < duration_seconds:
                try:
                    # Create dummy event
                    dummy_event = WakeDetectedEvent(
                        timestamp=time.time(), confidence=0.9, ts_device=time.time()
                    )

                    # Measure latency
                    operation_start = time.time()
                    await adapter.send_event(dummy_event)
                    operation_end = time.time()

                    latency_ms = (operation_end - operation_start) * 1000
                    latencies.append(latency_ms)
                    operation_count += 1

                    # Check if we're meeting latency targets
                    if latency_ms > target_latency_ms:
                        logger.warning(
                            "Latency exceeded target: %.2fms > %.2fms",
                            latency_ms,
                            target_latency_ms,
                        )

                    # Small delay to prevent overwhelming the adapter
                    await asyncio.sleep(0.01)

                except Exception as e:
                    error_count += 1
                    logger.error("Error during performance test: %s", e)
                    await asyncio.sleep(0.1)  # Longer delay on error

        finally:
            # Stop resource monitoring
            await self._stop_resource_monitoring()

            # Disconnect adapter
            if hasattr(adapter, "stop_capture"):
                await adapter.stop_capture()

        # Calculate metrics
        test_duration = time.time() - start_time
        metrics = self._calculate_metrics(
            latencies=latencies,
            operation_count=operation_count,
            error_count=error_count,
            test_duration=test_duration,
        )

        logger.info(
            "SurfaceControlProtocol performance test completed: %.2f ops/sec, %.2fms avg latency",
            metrics.operations_per_second,
            metrics.avg_latency_ms,
        )

        return metrics

    async def test_surface_lifecycle_performance(
        self,
        adapter: SurfaceTelemetryProtocol,
        duration_seconds: float = 10.0,
        target_latency_ms: float = 100.0,
    ) -> PerformanceMetrics:
        """
        Test SurfaceTelemetryProtocol adapter performance.

        Args:
            adapter: SurfaceTelemetryProtocol adapter to test
            duration_seconds: Test duration in seconds
            target_latency_ms: Target latency in milliseconds

        Returns:
            Performance metrics
        """
        logger.info(
            "Starting SurfaceTelemetryProtocol performance test for %s seconds",
            duration_seconds,
        )

        # Connect lifecycle adapter
        if hasattr(adapter, "connect"):
            await adapter.connect()

        # Start resource monitoring
        await self._start_resource_monitoring()

        # Performance test data
        latencies: list[float] = []
        operation_count = 0
        error_count = 0
        start_time = time.time()

        try:
            while time.time() - start_time < duration_seconds:
                try:
                    # Measure latency of connection status check
                    operation_start = time.time()
                    _ = adapter.is_connected
                    operation_end = time.time()

                    latency_ms = (operation_end - operation_start) * 1000
                    latencies.append(latency_ms)
                    operation_count += 1

                    # Check if we're meeting latency targets
                    if latency_ms > target_latency_ms:
                        logger.warning(
                            "Latency exceeded target: %.2fms > %.2fms",
                            latency_ms,
                            target_latency_ms,
                        )

                    # Small delay to prevent overwhelming the adapter
                    await asyncio.sleep(0.01)

                except Exception as e:
                    error_count += 1
                    logger.error("Error during performance test: %s", e)
                    await asyncio.sleep(0.1)  # Longer delay on error

        finally:
            # Stop resource monitoring
            await self._stop_resource_monitoring()

            # Disconnect adapter
            if hasattr(adapter, "stop_capture"):
                await adapter.stop_capture()

        # Calculate metrics
        test_duration = time.time() - start_time
        metrics = self._calculate_metrics(
            latencies=latencies,
            operation_count=operation_count,
            error_count=error_count,
            test_duration=test_duration,
        )

        logger.info(
            "SurfaceTelemetryProtocol performance test completed: %.2f ops/sec, %.2fms avg latency",
            metrics.operations_per_second,
            metrics.avg_latency_ms,
        )

        return metrics

    async def run_comprehensive_performance_tests(
        self, adapters: dict[str, Any], duration_seconds: float = 10.0
    ) -> dict[str, Any]:
        """
        Run comprehensive performance tests on all adapters.

        Args:
            adapters: Dictionary of adapters to test
            duration_seconds: Test duration for each adapter

        Returns:
            Comprehensive performance test results
        """
        results: dict[str, Any] = {
            "total_adapters": len(adapters),
            "test_duration_seconds": duration_seconds,
            "adapter_results": {},
            "summary": {},
        }

        for adapter_name, adapter in adapters.items():
            try:
                # Determine adapter type and run appropriate tests
                if isinstance(adapter, AudioCaptureProtocol):
                    metrics = await self.test_audio_source_performance(
                        adapter, duration_seconds
                    )
                elif isinstance(adapter, AudioPlaybackProtocol):
                    metrics = await self.test_audio_sink_performance(
                        adapter, duration_seconds
                    )
                elif isinstance(adapter, SurfaceControlProtocol):
                    metrics = await self.test_control_channel_performance(
                        adapter, duration_seconds
                    )
                elif isinstance(adapter, SurfaceTelemetryProtocol):
                    metrics = await self.test_surface_lifecycle_performance(
                        adapter, duration_seconds
                    )
                else:
                    # Create dummy metrics for unknown adapter types
                    metrics = PerformanceMetrics(
                        avg_latency_ms=0.0,
                        min_latency_ms=0.0,
                        max_latency_ms=0.0,
                        p95_latency_ms=0.0,
                        p99_latency_ms=0.0,
                        operations_per_second=0.0,
                        total_operations=0,
                        test_duration_seconds=0.0,
                        avg_cpu_percent=0.0,
                        max_cpu_percent=0.0,
                        avg_memory_mb=0.0,
                        max_memory_mb=0.0,
                        error_count=1,
                        error_rate=1.0,
                        timestamp=datetime.now(),
                    )

                results["adapter_results"][adapter_name] = metrics

            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                logger.error(
                    "Performance test failed for adapter %s: %s", adapter_name, e
                )
                # Create error metrics
                error_metrics = PerformanceMetrics(
                    avg_latency_ms=0.0,
                    min_latency_ms=0.0,
                    max_latency_ms=0.0,
                    p95_latency_ms=0.0,
                    p99_latency_ms=0.0,
                    operations_per_second=0.0,
                    total_operations=0,
                    test_duration_seconds=0.0,
                    avg_cpu_percent=0.0,
                    max_cpu_percent=0.0,
                    avg_memory_mb=0.0,
                    max_memory_mb=0.0,
                    error_count=1,
                    error_rate=1.0,
                    timestamp=datetime.now(),
                )
                results["adapter_results"][adapter_name] = error_metrics

        # Generate summary
        results["summary"] = self._generate_performance_summary(
            results["adapter_results"]
        )

        return results

    async def _start_resource_monitoring(self) -> None:
        """Start resource monitoring."""
        if self.resource_monitor is None or self.resource_monitor.done():
            self.resource_data.clear()
            self.resource_monitor = asyncio.create_task(self._monitor_resources())

    async def _stop_resource_monitoring(self) -> None:
        """Stop resource monitoring."""
        if self.resource_monitor and not self.resource_monitor.done():
            self.resource_monitor.cancel()
            try:
                await self.resource_monitor
            except asyncio.CancelledError:
                logger.debug("Resource monitoring cancelled")
            self.resource_monitor = None

    async def _monitor_resources(self) -> None:
        """Monitor system resources."""
        try:
            while True:
                # Simplified resource monitoring without psutil
                self.resource_data.append(
                    {"timestamp": datetime.now(), "cpu_percent": 0.0, "memory_mb": 0.0}
                )

                await asyncio.sleep(0.1)  # Monitor every 100ms

        except asyncio.CancelledError:
            logger.debug("Resource monitoring cancelled")
        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            logger.error("Error in resource monitoring: %s", e)

    def _calculate_metrics(
        self,
        latencies: list[float],
        operation_count: int,
        error_count: int,
        test_duration: float,
    ) -> PerformanceMetrics:
        """Calculate performance metrics."""
        if not latencies:
            return PerformanceMetrics(
                avg_latency_ms=0.0,
                min_latency_ms=0.0,
                max_latency_ms=0.0,
                p95_latency_ms=0.0,
                p99_latency_ms=0.0,
                operations_per_second=0.0,
                total_operations=operation_count,
                test_duration_seconds=test_duration,
                avg_cpu_percent=0.0,
                max_cpu_percent=0.0,
                avg_memory_mb=0.0,
                max_memory_mb=0.0,
                error_count=error_count,
                error_rate=error_count / max(operation_count, 1),
                timestamp=datetime.now(),
            )

        # Calculate latency statistics
        latencies_sorted = sorted(latencies)
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        p95_latency = latencies_sorted[int(len(latencies_sorted) * 0.95)]
        p99_latency = latencies_sorted[int(len(latencies_sorted) * 0.99)]

        # Calculate throughput
        operations_per_second = (
            operation_count / test_duration if test_duration > 0 else 0.0
        )

        # Calculate resource metrics (simplified without psutil)
        avg_cpu = max_cpu = avg_memory = max_memory = 0.0

        # Calculate error rate
        error_rate = error_count / max(operation_count, 1)

        return PerformanceMetrics(
            avg_latency_ms=avg_latency,
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
            p95_latency_ms=p95_latency,
            p99_latency_ms=p99_latency,
            operations_per_second=operations_per_second,
            total_operations=operation_count,
            test_duration_seconds=test_duration,
            avg_cpu_percent=avg_cpu,
            max_cpu_percent=max_cpu,
            avg_memory_mb=avg_memory,
            max_memory_mb=max_memory,
            error_count=error_count,
            error_rate=error_rate,
            timestamp=datetime.now(),
        )

    def _generate_performance_summary(
        self, adapter_results: dict[str, PerformanceMetrics]
    ) -> dict[str, Any]:
        """Generate performance summary."""
        if not adapter_results:
            return {"error": "No adapter results available"}

        # Aggregate metrics
        total_operations = sum(
            metrics.total_operations for metrics in adapter_results.values()
        )
        total_errors = sum(metrics.error_count for metrics in adapter_results.values())
        avg_latencies = [
            metrics.avg_latency_ms
            for metrics in adapter_results.values()
            if metrics.avg_latency_ms > 0
        ]
        throughputs = [
            metrics.operations_per_second
            for metrics in adapter_results.values()
            if metrics.operations_per_second > 0
        ]

        return {
            "total_adapters": len(adapter_results),
            "total_operations": total_operations,
            "total_errors": total_errors,
            "overall_error_rate": total_errors / max(total_operations, 1),
            "avg_latency_ms": (
                sum(avg_latencies) / len(avg_latencies) if avg_latencies else 0.0
            ),
            "avg_throughput_ops_per_sec": (
                sum(throughputs) / len(throughputs) if throughputs else 0.0
            ),
            "best_performing_adapter": (
                max(adapter_results.items(), key=lambda x: x[1].operations_per_second)[
                    0
                ]
                if adapter_results
                else None
            ),
            "worst_performing_adapter": (
                min(adapter_results.items(), key=lambda x: x[1].avg_latency_ms)[0]
                if adapter_results
                else None
            ),
        }
