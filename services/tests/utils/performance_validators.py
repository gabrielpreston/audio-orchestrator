"""
Performance validation utilities for interface-first testing.

This module provides utilities for validating performance requirements,
including latency, throughput, memory usage, and CPU constraints.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import statistics
import time

import psutil


@dataclass
class PerformanceMetrics:
    """Performance metrics for validation."""

    latency_ms: float
    throughput_rps: float
    memory_usage_mb: float
    cpu_usage_percent: float
    error_rate: float
    success_rate: float
    total_requests: int
    failed_requests: int
    validation_time_ms: float


@dataclass
class PerformanceResult:
    """Result of performance validation."""

    test_name: str
    passed: bool
    metrics: PerformanceMetrics
    errors: list[str]
    warnings: list[str]
    recommendations: list[str]

    def add_error(self, error: str):
        """Add an error to the performance result."""
        self.errors.append(error)
        self.passed = False

    def add_warning(self, warning: str):
        """Add a warning to the performance result."""
        self.warnings.append(warning)

    def add_recommendation(self, recommendation: str):
        """Add a recommendation to the performance result."""
        self.recommendations.append(recommendation)


class PerformanceValidator:
    """Validator for performance requirements."""

    def __init__(
        self,
        max_latency_ms: int = 1000,
        min_throughput_rps: int = 1,
        max_memory_mb: int = 1024,
        max_cpu_percent: int = 80,
    ):
        self.max_latency_ms = max_latency_ms
        self.min_throughput_rps = min_throughput_rps
        self.max_memory_mb = max_memory_mb
        self.max_cpu_percent = max_cpu_percent

    async def validate_latency(
        self, test_function: Callable, iterations: int = 10
    ) -> PerformanceResult:
        """Test latency requirements."""
        result = PerformanceResult(
            test_name="latency_validation",
            passed=True,
            metrics=PerformanceMetrics(
                latency_ms=0.0,
                throughput_rps=0.0,
                memory_usage_mb=0.0,
                cpu_usage_percent=0.0,
                error_rate=0.0,
                success_rate=0.0,
                total_requests=0,
                failed_requests=0,
                validation_time_ms=0.0,
            ),
            errors=[],
            warnings=[],
            recommendations=[],
        )

        start_time = time.time()
        latencies = []
        successful_requests = 0
        failed_requests = 0

        try:
            for i in range(iterations):
                try:
                    request_start = time.time()
                    await test_function()
                    request_end = time.time()

                    latency_ms = (request_end - request_start) * 1000
                    latencies.append(latency_ms)
                    successful_requests += 1

                except Exception as e:
                    failed_requests += 1
                    result.add_warning(f"Request {i + 1} failed: {str(e)}")

            # Calculate metrics
            if latencies:
                avg_latency = statistics.mean(latencies)
                max_latency = max(latencies)
                _min_latency = min(latencies)

                result.metrics.latency_ms = avg_latency
                result.metrics.total_requests = iterations
                result.metrics.failed_requests = failed_requests
                result.metrics.success_rate = (successful_requests / iterations) * 100
                result.metrics.error_rate = (failed_requests / iterations) * 100

                # Validate latency requirements
                if avg_latency > self.max_latency_ms:
                    result.add_error(
                        f"Average latency {avg_latency:.1f}ms exceeds maximum {self.max_latency_ms}ms"
                    )

                if max_latency > self.max_latency_ms * 2:
                    result.add_warning(
                        f"Maximum latency {max_latency:.1f}ms is significantly higher than average"
                    )

                # Add recommendations
                if avg_latency > self.max_latency_ms * 0.8:
                    result.add_recommendation(
                        "Consider optimizing for better latency performance"
                    )

                if max_latency > avg_latency * 3:
                    result.add_recommendation(
                        "High latency variance detected - consider load balancing"
                    )

            else:
                result.add_error("No successful requests to measure latency")

        except Exception as e:
            result.add_error(f"Latency validation failed: {str(e)}")

        result.metrics.validation_time_ms = (time.time() - start_time) * 1000
        return result

    async def validate_throughput(
        self, test_function: Callable, duration_seconds: int = 10
    ) -> PerformanceResult:
        """Test throughput requirements."""
        result = PerformanceResult(
            test_name="throughput_validation",
            passed=True,
            metrics=PerformanceMetrics(
                latency_ms=0.0,
                throughput_rps=0.0,
                memory_usage_mb=0.0,
                cpu_usage_percent=0.0,
                error_rate=0.0,
                success_rate=0.0,
                total_requests=0,
                failed_requests=0,
                validation_time_ms=0.0,
            ),
            errors=[],
            warnings=[],
            recommendations=[],
        )

        start_time = time.time()
        successful_requests = 0
        failed_requests = 0

        try:
            # Run concurrent requests for the specified duration
            async def run_request():
                nonlocal successful_requests, failed_requests
                try:
                    await test_function()
                    successful_requests += 1
                except Exception:
                    failed_requests += 1

            # Create tasks for concurrent execution
            tasks = []
            end_time = start_time + duration_seconds

            while time.time() < end_time:
                task = asyncio.create_task(run_request())
                tasks.append(task)

                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.001)

            # Wait for all tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)

            # Calculate throughput
            actual_duration = time.time() - start_time
            throughput_rps = successful_requests / actual_duration

            result.metrics.throughput_rps = throughput_rps
            result.metrics.total_requests = successful_requests + failed_requests
            result.metrics.failed_requests = failed_requests
            result.metrics.success_rate = (
                (successful_requests / (successful_requests + failed_requests)) * 100
                if (successful_requests + failed_requests) > 0
                else 0
            )
            result.metrics.error_rate = (
                (failed_requests / (successful_requests + failed_requests)) * 100
                if (successful_requests + failed_requests) > 0
                else 0
            )

            # Validate throughput requirements
            if throughput_rps < self.min_throughput_rps:
                result.add_error(
                    f"Throughput {throughput_rps:.1f} RPS below minimum {self.min_throughput_rps} RPS"
                )

            # Add recommendations
            if throughput_rps < self.min_throughput_rps * 1.5:
                result.add_recommendation(
                    "Consider optimizing for better throughput performance"
                )

            if result.metrics.error_rate > 5:
                result.add_recommendation(
                    "High error rate detected - investigate stability issues"
                )

        except Exception as e:
            result.add_error(f"Throughput validation failed: {str(e)}")

        result.metrics.validation_time_ms = (time.time() - start_time) * 1000
        return result

    async def validate_memory_usage(
        self, test_function: Callable, iterations: int = 10
    ) -> PerformanceResult:
        """Test memory usage requirements."""
        result = PerformanceResult(
            test_name="memory_validation",
            passed=True,
            metrics=PerformanceMetrics(
                latency_ms=0.0,
                throughput_rps=0.0,
                memory_usage_mb=0.0,
                cpu_usage_percent=0.0,
                error_rate=0.0,
                success_rate=0.0,
                total_requests=0,
                failed_requests=0,
                validation_time_ms=0.0,
            ),
            errors=[],
            warnings=[],
            recommendations=[],
        )

        start_time = time.time()
        memory_samples = []

        try:
            # Get initial memory usage
            _initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB

            for i in range(iterations):
                try:
                    # Get memory before request
                    memory_before = psutil.Process().memory_info().rss / 1024 / 1024

                    await test_function()

                    # Get memory after request
                    memory_after = psutil.Process().memory_info().rss / 1024 / 1024

                    memory_usage = memory_after - memory_before
                    memory_samples.append(memory_usage)

                except Exception as e:
                    result.add_warning(
                        f"Request {i + 1} failed during memory validation: {str(e)}"
                    )

            # Calculate memory metrics
            if memory_samples:
                avg_memory = statistics.mean(memory_samples)
                max_memory = max(memory_samples)
                total_memory = psutil.Process().memory_info().rss / 1024 / 1024

                result.metrics.memory_usage_mb = avg_memory
                result.metrics.total_requests = iterations

                # Validate memory requirements
                if total_memory > self.max_memory_mb:
                    result.add_error(
                        f"Total memory usage {total_memory:.1f}MB exceeds maximum {self.max_memory_mb}MB"
                    )

                if avg_memory > self.max_memory_mb * 0.1:
                    result.add_warning(
                        f"High per-request memory usage {avg_memory:.1f}MB detected"
                    )

                # Add recommendations
                if total_memory > self.max_memory_mb * 0.8:
                    result.add_recommendation("Consider optimizing memory usage")

                if max_memory > avg_memory * 3:
                    result.add_recommendation(
                        "High memory variance detected - consider memory pooling"
                    )

            else:
                result.add_error("No successful requests to measure memory usage")

        except Exception as e:
            result.add_error(f"Memory validation failed: {str(e)}")

        result.metrics.validation_time_ms = (time.time() - start_time) * 1000
        return result

    async def validate_cpu_usage(
        self, test_function: Callable, duration_seconds: int = 10
    ) -> PerformanceResult:
        """Test CPU usage requirements."""
        result = PerformanceResult(
            test_name="cpu_validation",
            passed=True,
            metrics=PerformanceMetrics(
                latency_ms=0.0,
                throughput_rps=0.0,
                memory_usage_mb=0.0,
                cpu_usage_percent=0.0,
                error_rate=0.0,
                success_rate=0.0,
                total_requests=0,
                failed_requests=0,
                validation_time_ms=0.0,
            ),
            errors=[],
            warnings=[],
            recommendations=[],
        )

        start_time = time.time()
        cpu_samples = []

        try:
            # Monitor CPU usage during test execution
            async def monitor_cpu():
                while time.time() < start_time + duration_seconds:
                    cpu_percent = psutil.cpu_percent(interval=0.1)
                    cpu_samples.append(cpu_percent)
                    await asyncio.sleep(0.1)

            # Run test function and CPU monitoring concurrently
            test_task = asyncio.create_task(test_function())
            monitor_task = asyncio.create_task(monitor_cpu())

            await asyncio.gather(test_task, monitor_task, return_exceptions=True)

            # Calculate CPU metrics
            if cpu_samples:
                avg_cpu = statistics.mean(cpu_samples)
                max_cpu = max(cpu_samples)

                result.metrics.cpu_usage_percent = avg_cpu
                result.metrics.total_requests = 1

                # Validate CPU requirements
                if avg_cpu > self.max_cpu_percent:
                    result.add_error(
                        f"Average CPU usage {avg_cpu:.1f}% exceeds maximum {self.max_cpu_percent}%"
                    )

                if max_cpu > self.max_cpu_percent * 1.5:
                    result.add_warning(
                        f"Peak CPU usage {max_cpu:.1f}% significantly higher than average"
                    )

                # Add recommendations
                if avg_cpu > self.max_cpu_percent * 0.8:
                    result.add_recommendation("Consider optimizing CPU usage")

                if max_cpu > avg_cpu * 3:
                    result.add_recommendation(
                        "High CPU variance detected - consider load balancing"
                    )

            else:
                result.add_error("No CPU samples collected")

        except Exception as e:
            result.add_error(f"CPU validation failed: {str(e)}")

        result.metrics.validation_time_ms = (time.time() - start_time) * 1000
        return result

    async def validate_comprehensive_performance(
        self, test_function: Callable, iterations: int = 10, duration_seconds: int = 10
    ) -> PerformanceResult:
        """Comprehensive performance validation."""
        result = PerformanceResult(
            test_name="comprehensive_performance_validation",
            passed=True,
            metrics=PerformanceMetrics(
                latency_ms=0.0,
                throughput_rps=0.0,
                memory_usage_mb=0.0,
                cpu_usage_percent=0.0,
                error_rate=0.0,
                success_rate=0.0,
                total_requests=0,
                failed_requests=0,
                validation_time_ms=0.0,
            ),
            errors=[],
            warnings=[],
            recommendations=[],
        )

        start_time = time.time()

        try:
            # Run all performance validations
            latency_result = await self.validate_latency(test_function, iterations)
            throughput_result = await self.validate_throughput(
                test_function, duration_seconds
            )
            memory_result = await self.validate_memory_usage(test_function, iterations)
            cpu_result = await self.validate_cpu_usage(test_function, duration_seconds)

            # Aggregate results
            result.metrics.latency_ms = latency_result.metrics.latency_ms
            result.metrics.throughput_rps = throughput_result.metrics.throughput_rps
            result.metrics.memory_usage_mb = memory_result.metrics.memory_usage_mb
            result.metrics.cpu_usage_percent = cpu_result.metrics.cpu_usage_percent
            result.metrics.error_rate = max(
                latency_result.metrics.error_rate,
                throughput_result.metrics.error_rate,
                memory_result.metrics.error_rate,
                cpu_result.metrics.error_rate,
            )
            result.metrics.success_rate = min(
                latency_result.metrics.success_rate,
                throughput_result.metrics.success_rate,
                memory_result.metrics.success_rate,
                cpu_result.metrics.success_rate,
            )

            # Aggregate errors and warnings
            result.errors.extend(latency_result.errors)
            result.errors.extend(throughput_result.errors)
            result.errors.extend(memory_result.errors)
            result.errors.extend(cpu_result.errors)

            result.warnings.extend(latency_result.warnings)
            result.warnings.extend(throughput_result.warnings)
            result.warnings.extend(memory_result.warnings)
            result.warnings.extend(cpu_result.warnings)

            result.recommendations.extend(latency_result.recommendations)
            result.recommendations.extend(throughput_result.recommendations)
            result.recommendations.extend(memory_result.recommendations)
            result.recommendations.extend(cpu_result.recommendations)

            # Overall performance assessment
            if result.metrics.latency_ms > self.max_latency_ms:
                result.add_error("Latency requirements not met")

            if result.metrics.throughput_rps < self.min_throughput_rps:
                result.add_error("Throughput requirements not met")

            if result.metrics.memory_usage_mb > self.max_memory_mb:
                result.add_error("Memory requirements not met")

            if result.metrics.cpu_usage_percent > self.max_cpu_percent:
                result.add_error("CPU requirements not met")

            # Add overall recommendations
            if result.metrics.error_rate > 10:
                result.add_recommendation(
                    "High error rate detected - investigate system stability"
                )

            if result.metrics.success_rate < 90:
                result.add_recommendation(
                    "Low success rate detected - investigate reliability issues"
                )

        except Exception as e:
            result.add_error(f"Comprehensive performance validation failed: {str(e)}")

        result.metrics.validation_time_ms = (time.time() - start_time) * 1000
        return result
