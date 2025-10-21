"""
Cross-surface parity test suite.

This module provides comprehensive parity testing across different surface
implementations to ensure consistent performance and behavior.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from services.common.surfaces.events import WakeDetectedEvent
from services.common.surfaces.types import PCMFrame


logger = logging.getLogger(__name__)


class LatencyTarget(Enum):
    """Latency targets for different operations."""

    AUDIO_CAPTURE = 50.0  # ms
    AUDIO_PLAYBACK = 50.0  # ms
    EVENT_PROCESSING = 10.0  # ms
    CONNECTION_ESTABLISHMENT = 1000.0  # ms
    HEALTH_CHECK = 100.0  # ms


@dataclass
class ParityTestResult:
    """Result of a parity test."""

    test_name: str
    surface_id: str
    success: bool
    latency_ms: float
    target_latency_ms: float
    meets_target: bool
    error_message: str | None = None
    timestamp: datetime | None = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_name": self.test_name,
            "surface_id": self.surface_id,
            "success": self.success,
            "latency_ms": self.latency_ms,
            "target_latency_ms": self.target_latency_ms,
            "meets_target": self.meets_target,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class ParityTestSuite:
    """Configuration for parity test suite."""

    # Latency targets
    audio_capture_target_ms: float = 50.0
    audio_playback_target_ms: float = 50.0
    event_processing_target_ms: float = 10.0
    connection_target_ms: float = 1000.0
    health_check_target_ms: float = 100.0

    # Test configuration
    test_duration_seconds: float = 10.0
    sample_count: int = 100
    warmup_samples: int = 10

    # Tolerance settings
    latency_tolerance_percent: float = 20.0  # 20% tolerance
    max_failure_rate: float = 5.0  # 5% max failure rate


class CrossSurfaceParityTester:
    """
    Cross-surface parity tester.

    This class provides comprehensive parity testing across different surface
    implementations to ensure consistent performance and behavior.
    """

    def __init__(self, config: ParityTestSuite | None = None):
        """
        Initialize parity tester.

        Args:
            config: Test suite configuration
        """
        self.config = config or ParityTestSuite()
        self.test_results: list[ParityTestResult] = []
        self.surface_adapters: dict[str, dict[str, Any]] = {}

    def register_surface(self, surface_id: str, adapters: dict[str, Any]) -> None:
        """
        Register a surface with its adapters.

        Args:
            surface_id: Unique identifier for the surface
            adapters: Dictionary of adapters (audio_source, audio_sink, control_channel, surface_lifecycle)
        """
        self.surface_adapters[surface_id] = adapters
        logger.info("Registered surface %s with adapters: %s", surface_id, list(adapters.keys()))

    async def run_audio_capture_parity_tests(self) -> list[ParityTestResult]:
        """
        Run audio capture parity tests across all surfaces.

        Returns:
            List of test results
        """
        logger.info("Starting audio capture parity tests")
        results = []

        for surface_id, adapters in self.surface_adapters.items():
            audio_source = adapters.get("audio_source")
            if not audio_source:
                logger.warning("No audio source adapter for surface %s", surface_id)
                continue

            try:
                # Initialize and connect
                await audio_source.initialize()
                await audio_source.connect()

                # Warmup
                for _ in range(self.config.warmup_samples):
                    await audio_source.read_audio_frame()

                # Run latency tests
                latencies = []
                for _ in range(self.config.sample_count):
                    start_time = time.time()
                    await audio_source.read_audio_frame()
                    end_time = time.time()

                    latency_ms = (end_time - start_time) * 1000
                    latencies.append(latency_ms)

                # Calculate statistics
                avg_latency = sum(latencies) / len(latencies)
                meets_target = avg_latency <= self.config.audio_capture_target_ms

                result = ParityTestResult(
                    test_name="audio_capture",
                    surface_id=surface_id,
                    success=True,
                    latency_ms=avg_latency,
                    target_latency_ms=self.config.audio_capture_target_ms,
                    meets_target=meets_target,
                )
                results.append(result)

                logger.info(
                    "Audio capture test for %s: %.2fms (target: %.2fms, meets: %s)",
                    surface_id,
                    avg_latency,
                    self.config.audio_capture_target_ms,
                    meets_target,
                )

                await audio_source.disconnect()

            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                result = ParityTestResult(
                    test_name="audio_capture",
                    surface_id=surface_id,
                    success=False,
                    latency_ms=0.0,
                    target_latency_ms=self.config.audio_capture_target_ms,
                    meets_target=False,
                    error_message=str(e),
                )
                results.append(result)
                logger.error("Audio capture test failed for %s: %s", surface_id, e)

        self.test_results.extend(results)
        return results

    async def run_audio_playback_parity_tests(self) -> list[ParityTestResult]:
        """
        Run audio playback parity tests across all surfaces.

        Returns:
            List of test results
        """
        logger.info("Starting audio playback parity tests")
        results = []

        for surface_id, adapters in self.surface_adapters.items():
            audio_sink = adapters.get("audio_sink")
            if not audio_sink:
                logger.warning("No audio sink adapter for surface %s", surface_id)
                continue

            try:
                # Initialize and connect
                await audio_sink.initialize()
                await audio_sink.connect()

                # Create dummy audio frame
                dummy_frame = PCMFrame(
                    pcm=b"\x00" * 1024,
                    timestamp=time.time(),
                    rms=0.0,
                    duration=0.1,
                    sequence=1,
                    sample_rate=16000,
                )

                # Warmup
                for _ in range(self.config.warmup_samples):
                    await audio_sink.play_audio_chunk(dummy_frame)

                # Run latency tests
                latencies = []
                for _ in range(self.config.sample_count):
                    start_time = time.time()
                    await audio_sink.play_audio_chunk(dummy_frame)
                    end_time = time.time()

                    latency_ms = (end_time - start_time) * 1000
                    latencies.append(latency_ms)

                # Calculate statistics
                avg_latency = sum(latencies) / len(latencies)
                meets_target = avg_latency <= self.config.audio_playback_target_ms

                result = ParityTestResult(
                    test_name="audio_playback",
                    surface_id=surface_id,
                    success=True,
                    latency_ms=avg_latency,
                    target_latency_ms=self.config.audio_playback_target_ms,
                    meets_target=meets_target,
                )
                results.append(result)

                logger.info(
                    "Audio playback test for %s: %.2fms (target: %.2fms, meets: %s)",
                    surface_id,
                    avg_latency,
                    self.config.audio_playback_target_ms,
                    meets_target,
                )

                await audio_sink.disconnect()

            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                result = ParityTestResult(
                    test_name="audio_playback",
                    surface_id=surface_id,
                    success=False,
                    latency_ms=0.0,
                    target_latency_ms=self.config.audio_playback_target_ms,
                    meets_target=False,
                    error_message=str(e),
                )
                results.append(result)
                logger.error("Audio playback test failed for %s: %s", surface_id, e)

        self.test_results.extend(results)
        return results

    async def run_event_processing_parity_tests(self) -> list[ParityTestResult]:
        """
        Run event processing parity tests across all surfaces.

        Returns:
            List of test results
        """
        logger.info("Starting event processing parity tests")
        results = []

        for surface_id, adapters in self.surface_adapters.items():
            control_channel = adapters.get("control_channel")
            if not control_channel:
                logger.warning("No control channel adapter for surface %s", surface_id)
                continue

            try:
                # Initialize and connect
                await control_channel.initialize()
                await control_channel.connect()

                # Create dummy event
                dummy_event = WakeDetectedEvent(
                    timestamp=time.time(), confidence=0.9, ts_device=time.time()
                )

                # Warmup
                for _ in range(self.config.warmup_samples):
                    await control_channel.send_event(dummy_event)

                # Run latency tests
                latencies = []
                for _ in range(self.config.sample_count):
                    start_time = time.time()
                    await control_channel.send_event(dummy_event)
                    end_time = time.time()

                    latency_ms = (end_time - start_time) * 1000
                    latencies.append(latency_ms)

                # Calculate statistics
                avg_latency = sum(latencies) / len(latencies)
                meets_target = avg_latency <= self.config.event_processing_target_ms

                result = ParityTestResult(
                    test_name="event_processing",
                    surface_id=surface_id,
                    success=True,
                    latency_ms=avg_latency,
                    target_latency_ms=self.config.event_processing_target_ms,
                    meets_target=meets_target,
                )
                results.append(result)

                logger.info(
                    "Event processing test for %s: %.2fms (target: %.2fms, meets: %s)",
                    surface_id,
                    avg_latency,
                    self.config.event_processing_target_ms,
                    meets_target,
                )

                await control_channel.disconnect()

            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                result = ParityTestResult(
                    test_name="event_processing",
                    surface_id=surface_id,
                    success=False,
                    latency_ms=0.0,
                    target_latency_ms=self.config.event_processing_target_ms,
                    meets_target=False,
                    error_message=str(e),
                )
                results.append(result)
                logger.error("Event processing test failed for %s: %s", surface_id, e)

        self.test_results.extend(results)
        return results

    async def run_connection_parity_tests(self) -> list[ParityTestResult]:
        """
        Run connection establishment parity tests across all surfaces.

        Returns:
            List of test results
        """
        logger.info("Starting connection parity tests")
        results = []

        for surface_id, adapters in self.surface_adapters.items():
            surface_lifecycle = adapters.get("surface_lifecycle")
            if not surface_lifecycle:
                logger.warning("No surface lifecycle adapter for surface %s", surface_id)
                continue

            try:
                # Initialize
                await surface_lifecycle.initialize()

                # Run connection tests
                latencies = []
                for _ in range(self.config.sample_count):
                    start_time = time.time()
                    success = await surface_lifecycle.connect()
                    end_time = time.time()

                    if success:
                        latency_ms = (end_time - start_time) * 1000
                        latencies.append(latency_ms)
                        await surface_lifecycle.disconnect()
                    else:
                        logger.warning("Connection failed for surface %s", surface_id)

                if latencies:
                    # Calculate statistics
                    avg_latency = sum(latencies) / len(latencies)
                    meets_target = avg_latency <= self.config.connection_target_ms

                    result = ParityTestResult(
                        test_name="connection",
                        surface_id=surface_id,
                        success=True,
                        latency_ms=avg_latency,
                        target_latency_ms=self.config.connection_target_ms,
                        meets_target=meets_target,
                    )
                    results.append(result)

                    logger.info(
                        "Connection test for %s: %.2fms (target: %.2fms, meets: %s)",
                        surface_id,
                        avg_latency,
                        self.config.connection_target_ms,
                        meets_target,
                    )
                else:
                    result = ParityTestResult(
                        test_name="connection",
                        surface_id=surface_id,
                        success=False,
                        latency_ms=0.0,
                        target_latency_ms=self.config.connection_target_ms,
                        meets_target=False,
                        error_message="All connection attempts failed",
                    )
                    results.append(result)

            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                result = ParityTestResult(
                    test_name="connection",
                    surface_id=surface_id,
                    success=False,
                    latency_ms=0.0,
                    target_latency_ms=self.config.connection_target_ms,
                    meets_target=False,
                    error_message=str(e),
                )
                results.append(result)
                logger.error("Connection test failed for %s: %s", surface_id, e)

        self.test_results.extend(results)
        return results

    async def run_health_check_parity_tests(self) -> list[ParityTestResult]:
        """
        Run health check parity tests across all surfaces.

        Returns:
            List of test results
        """
        logger.info("Starting health check parity tests")
        results = []

        for surface_id, adapters in self.surface_adapters.items():
            surface_lifecycle = adapters.get("surface_lifecycle")
            if not surface_lifecycle:
                logger.warning("No surface lifecycle adapter for surface %s", surface_id)
                continue

            try:
                # Initialize and connect
                await surface_lifecycle.initialize()
                await surface_lifecycle.connect()

                # Run health check tests
                latencies = []
                for _ in range(self.config.sample_count):
                    start_time = time.time()
                    surface_lifecycle.is_connected()
                    end_time = time.time()

                    latency_ms = (end_time - start_time) * 1000
                    latencies.append(latency_ms)

                # Calculate statistics
                avg_latency = sum(latencies) / len(latencies)
                meets_target = avg_latency <= self.config.health_check_target_ms

                result = ParityTestResult(
                    test_name="health_check",
                    surface_id=surface_id,
                    success=True,
                    latency_ms=avg_latency,
                    target_latency_ms=self.config.health_check_target_ms,
                    meets_target=meets_target,
                )
                results.append(result)

                logger.info(
                    "Health check test for %s: %.2fms (target: %.2fms, meets: %s)",
                    surface_id,
                    avg_latency,
                    self.config.health_check_target_ms,
                    meets_target,
                )

                await surface_lifecycle.disconnect()

            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                result = ParityTestResult(
                    test_name="health_check",
                    surface_id=surface_id,
                    success=False,
                    latency_ms=0.0,
                    target_latency_ms=self.config.health_check_target_ms,
                    meets_target=False,
                    error_message=str(e),
                )
                results.append(result)
                logger.error("Health check test failed for %s: %s", surface_id, e)

        self.test_results.extend(results)
        return results

    async def run_comprehensive_parity_tests(self) -> dict[str, Any]:
        """
        Run comprehensive parity tests across all surfaces.

        Returns:
            Comprehensive test results
        """
        logger.info("Starting comprehensive parity tests")

        # Run all test types
        audio_capture_results = await self.run_audio_capture_parity_tests()
        audio_playback_results = await self.run_audio_playback_parity_tests()
        event_processing_results = await self.run_event_processing_parity_tests()
        connection_results = await self.run_connection_parity_tests()
        health_check_results = await self.run_health_check_parity_tests()

        # Aggregate results
        all_results = (
            audio_capture_results
            + audio_playback_results
            + event_processing_results
            + connection_results
            + health_check_results
        )

        # Calculate summary statistics
        total_tests = len(all_results)
        successful_tests = sum(1 for r in all_results if r.success)
        tests_meeting_targets = sum(1 for r in all_results if r.meets_target)

        # Group results by test type
        results_by_type: dict[str, list[ParityTestResult]] = {}
        for result in all_results:
            test_type = result.test_name
            if test_type not in results_by_type:
                results_by_type[test_type] = []
            results_by_type[test_type].append(result)

        # Calculate latency statistics by test type
        latency_stats = {}
        for test_type, results in results_by_type.items():
            if results:
                latencies = [r.latency_ms for r in results if r.success]
                if latencies:
                    latency_stats[test_type] = {
                        "avg_latency_ms": sum(latencies) / len(latencies),
                        "min_latency_ms": min(latencies),
                        "max_latency_ms": max(latencies),
                        "success_rate": sum(1 for r in results if r.success) / len(results),
                        "target_meeting_rate": sum(1 for r in results if r.meets_target)
                        / len(results),
                    }

        # Generate summary
        summary = {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": successful_tests / max(total_tests, 1),
            "tests_meeting_targets": tests_meeting_targets,
            "target_meeting_rate": tests_meeting_targets / max(total_tests, 1),
            "latency_statistics": latency_stats,
            "test_results": [result.to_dict() for result in all_results],
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            "Comprehensive parity tests completed: %d/%d successful, %d/%d meeting targets",
            successful_tests,
            total_tests,
            tests_meeting_targets,
            total_tests,
        )

        return summary

    def get_parity_report(self) -> dict[str, Any]:
        """
        Generate a parity report.

        Returns:
            Parity report
        """
        if not self.test_results:
            return {"error": "No test results available"}

        # Group results by surface
        results_by_surface: dict[str, list[ParityTestResult]] = {}
        for result in self.test_results:
            surface_id = result.surface_id
            if surface_id not in results_by_surface:
                results_by_surface[surface_id] = []
            results_by_surface[surface_id].append(result)

        # Calculate surface-level statistics
        surface_stats = {}
        for surface_id, results in results_by_surface.items():
            successful = sum(1 for r in results if r.success)
            meeting_targets = sum(1 for r in results if r.meets_target)

            surface_stats[surface_id] = {
                "total_tests": len(results),
                "successful_tests": successful,
                "success_rate": successful / max(len(results), 1),
                "tests_meeting_targets": meeting_targets,
                "target_meeting_rate": meeting_targets / max(len(results), 1),
            }

        # Calculate overall statistics
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r.success)
        tests_meeting_targets = sum(1 for r in self.test_results if r.meets_target)

        return {
            "overall_statistics": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": successful_tests / max(total_tests, 1),
                "tests_meeting_targets": tests_meeting_targets,
                "target_meeting_rate": tests_meeting_targets / max(total_tests, 1),
            },
            "surface_statistics": surface_stats,
            "test_results": [result.to_dict() for result in self.test_results],
            "timestamp": datetime.now().isoformat(),
        }
