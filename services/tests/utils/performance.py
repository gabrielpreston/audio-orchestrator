"""Performance measurement utilities for audio pipeline testing."""

from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
import statistics
import time
from typing import Any


@dataclass
class LatencyStats:
    """Collect and analyze latency distributions."""

    measurements: list[float] = field(default_factory=list)
    operation_name: str = "unknown"

    def add_measurement(self, latency_ms: float) -> None:
        """Add a latency measurement."""
        self.measurements.append(latency_ms)

    def get_stats(self) -> dict[str, float]:
        """Get statistical summary of measurements."""
        if not self.measurements:
            return {
                "count": 0,
                "mean": 0.0,
                "median": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "min": 0.0,
                "max": 0.0,
                "std": 0.0,
            }

        sorted_measurements = sorted(self.measurements)
        count = len(sorted_measurements)

        return {
            "count": count,
            "mean": statistics.mean(sorted_measurements),
            "median": statistics.median(sorted_measurements),
            "p50": sorted_measurements[int(count * 0.5)],
            "p95": sorted_measurements[int(count * 0.95)],
            "p99": sorted_measurements[int(count * 0.99)],
            "min": min(sorted_measurements),
            "max": max(sorted_measurements),
            "std": statistics.stdev(sorted_measurements) if count > 1 else 0.0,
        }

    def reset(self) -> None:
        """Reset all measurements."""
        self.measurements.clear()


@dataclass
class LatencyBudget:
    """Validate operations meet latency thresholds."""

    p95_threshold_ms: float
    p99_threshold_ms: float
    mean_threshold_ms: float
    operation_name: str = "unknown"

    def validate(self, stats: LatencyStats) -> dict[str, Any]:
        """Validate latency stats against budget."""
        stats_dict = stats.get_stats()

        return {
            "operation": self.operation_name,
            "p95_pass": stats_dict["p95"] <= self.p95_threshold_ms,
            "p99_pass": stats_dict["p99"] <= self.p99_threshold_ms,
            "mean_pass": stats_dict["mean"] <= self.mean_threshold_ms,
            "p95_actual": stats_dict["p95"],
            "p99_actual": stats_dict["p99"],
            "mean_actual": stats_dict["mean"],
            "p95_threshold": self.p95_threshold_ms,
            "p99_threshold": self.p99_threshold_ms,
            "mean_threshold": self.mean_threshold_ms,
            "overall_pass": (
                stats_dict["p95"] <= self.p95_threshold_ms
                and stats_dict["p99"] <= self.p99_threshold_ms
                and stats_dict["mean"] <= self.mean_threshold_ms
            ),
        }


class PerformanceCollector:
    """Collect performance measurements across multiple operations."""

    def __init__(self):
        self.stats: dict[str, LatencyStats] = defaultdict(lambda: LatencyStats())
        self.budgets: dict[str, LatencyBudget] = {}

    def add_measurement(self, operation: str, latency_ms: float) -> None:
        """Add measurement for specific operation."""
        self.stats[operation].add_measurement(latency_ms)
        self.stats[operation].operation_name = operation

    def set_budget(
        self, operation: str, p95_ms: float, p99_ms: float, mean_ms: float
    ) -> None:
        """Set latency budget for operation."""
        self.budgets[operation] = LatencyBudget(
            p95_threshold_ms=p95_ms,
            p99_threshold_ms=p99_ms,
            mean_threshold_ms=mean_ms,
            operation_name=operation,
        )

    def validate_all(self) -> dict[str, dict[str, Any]]:
        """Validate all operations against their budgets."""
        results = {}
        for operation, stats in self.stats.items():
            if operation in self.budgets:
                results[operation] = self.budgets[operation].validate(stats)
            else:
                # No budget set, just return stats
                results[operation] = {
                    "operation": operation,
                    "budget_defined": False,
                    "stats": stats.get_stats(),
                }
        return results

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all measurements."""
        summary = {}
        for operation, stats in self.stats.items():
            summary[operation] = stats.get_stats()
        return summary

    def reset(self) -> None:
        """Reset all measurements."""
        for stats in self.stats.values():
            stats.reset()


@contextmanager
def measure_latency(operation: str, collector: PerformanceCollector | None = None):
    """Context manager for measuring operation latency."""
    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000

        if collector:
            collector.add_measurement(operation, latency_ms)


@contextmanager
async def measure_latency_async(
    operation: str, collector: PerformanceCollector | None = None
):
    """Async context manager for measuring operation latency."""
    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000

        if collector:
            collector.add_measurement(operation, latency_ms)


class FileLevelPerformanceCollector(PerformanceCollector):
    """Specialized collector for file-level audio processing."""

    def __init__(self):
        super().__init__()
        # Set default budgets for file-level operations
        self.set_budget("file_transcription", p95_ms=2000, p99_ms=3000, mean_ms=1500)
        self.set_budget("file_enhancement", p95_ms=500, p99_ms=800, mean_ms=300)
        self.set_budget("file_processing", p95_ms=2500, p99_ms=4000, mean_ms=1800)

    def measure_file_processing(self, file_size_bytes: int, processing_func):
        """Measure complete file processing pipeline."""
        with measure_latency("file_processing", self):
            result = processing_func()
            return result


class ChunkLevelPerformanceCollector(PerformanceCollector):
    """Specialized collector for chunk-level audio processing."""

    def __init__(self):
        super().__init__()
        # Set default budgets for chunk-level operations
        self.set_budget("chunk_enhancement", p95_ms=50, p99_ms=100, mean_ms=30)
        self.set_budget("chunk_transcription", p95_ms=200, p99_ms=400, mean_ms=150)
        self.set_budget("chunk_processing", p95_ms=250, p99_ms=500, mean_ms=180)

    def measure_chunk_processing(self, chunk_size_bytes: int, processing_func):
        """Measure chunk processing pipeline."""
        with measure_latency("chunk_processing", self):
            result = processing_func()
            return result


# Convenience functions for common scenarios
def create_file_performance_collector() -> FileLevelPerformanceCollector:
    """Create file-level performance collector with default budgets."""
    return FileLevelPerformanceCollector()


def create_chunk_performance_collector() -> ChunkLevelPerformanceCollector:
    """Create chunk-level performance collector with default budgets."""
    return ChunkLevelPerformanceCollector()


def measure_enhancement_latency(enhancement_func, audio_data: bytes) -> float:
    """Measure enhancement latency for specific audio data."""
    start_time = time.time()
    try:
        enhancement_func(audio_data)
        return (time.time() - start_time) * 1000
    except Exception:
        return float("inf")  # Failed operations get infinite latency


def measure_transcription_latency(transcription_func, audio_data: bytes) -> float:
    """Measure transcription latency for specific audio data."""
    start_time = time.time()
    try:
        transcription_func(audio_data)
        return (time.time() - start_time) * 1000
    except Exception:
        return float("inf")  # Failed operations get infinite latency


# Performance validation utilities
def validate_latency_budget(stats: LatencyStats, budget: LatencyBudget) -> bool:
    """Validate latency stats against budget."""
    validation = budget.validate(stats)
    return validation["overall_pass"]


def create_enhancement_budget(
    p95_ms: float = 500, p99_ms: float = 800, mean_ms: float = 300
) -> LatencyBudget:
    """Create latency budget for enhancement operations."""
    return LatencyBudget(
        p95_threshold_ms=p95_ms,
        p99_threshold_ms=p99_ms,
        mean_threshold_ms=mean_ms,
        operation_name="enhancement",
    )


def create_transcription_budget(
    p95_ms: float = 2000, p99_ms: float = 3000, mean_ms: float = 1500
) -> LatencyBudget:
    """Create latency budget for transcription operations."""
    return LatencyBudget(
        p95_threshold_ms=p95_ms,
        p99_threshold_ms=p99_ms,
        mean_threshold_ms=mean_ms,
        operation_name="transcription",
    )
