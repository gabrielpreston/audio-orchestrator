"""
Chaos test suite for surface adapters.

This module provides chaos testing capabilities for surface adapters,
including network fault injection, reliability testing, and failure recovery.
"""

import asyncio
import logging
import random
import time
from collections.abc import Callable
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
class ChaosTestResult:
    """Result of a chaos test."""

    test_name: str
    success: bool
    failure_count: int
    recovery_count: int
    test_duration_seconds: float
    error_messages: list[str]
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "test_name": self.test_name,
            "success": self.success,
            "failure_count": self.failure_count,
            "recovery_count": self.recovery_count,
            "test_duration_seconds": self.test_duration_seconds,
            "error_messages": self.error_messages,
            "timestamp": self.timestamp.isoformat(),
        }


class SurfaceAdapterChaosTester:
    """
    Chaos tester for surface adapters.

    This class provides comprehensive chaos testing of surface adapters,
    including network fault injection, reliability testing, and failure recovery.
    """

    def __init__(self):
        """Initialize the chaos tester."""
        self.test_results: dict[str, list[ChaosTestResult]] = {}
        self.fault_injectors: list[Callable[..., Any]] = []

    async def test_network_fault_injection(
        self,
        adapter: Any,
        duration_seconds: float = 30.0,
        fault_probability: float = 0.1,
    ) -> ChaosTestResult:
        """
        Test adapter resilience to network faults.

        Args:
            adapter: Adapter to test
            duration_seconds: Test duration in seconds
            fault_probability: Probability of injecting faults (0.0 to 1.0)

        Returns:
            Chaos test result
        """
        logger.info(
            "Starting network fault injection test for %s seconds", duration_seconds
        )

        test_name = "network_fault_injection"
        failure_count = 0
        recovery_count = 0
        error_messages = []
        start_time = datetime.now()

        try:
            # Initialize and connect adapter
            await adapter.initialize()
            await adapter.connect()

            # Run test with fault injection
            while (datetime.now() - start_time).total_seconds() < duration_seconds:
                try:
                    # Inject fault with probability
                    if random.random() < fault_probability:
                        await self._inject_network_fault()
                        failure_count += 1

                    # Test adapter operation
                    await self._test_adapter_operation(adapter)

                    # Check for recovery
                    if failure_count > 0 and await self._check_adapter_recovery(
                        adapter
                    ):
                        recovery_count += 1
                        failure_count = 0  # Reset failure count on recovery

                    await asyncio.sleep(0.1)  # 100ms loop

                except (ValueError, TypeError, KeyError, RuntimeError) as e:
                    error_messages.append(f"Operation failed: {e}")
                    failure_count += 1
                    await asyncio.sleep(0.5)  # Longer delay on error

        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            error_messages.append(f"Test setup failed: {e}")
            failure_count += 1

        finally:
            try:
                await adapter.disconnect()
            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                error_messages.append(f"Cleanup failed: {e}")

        test_duration = (datetime.now() - start_time).total_seconds()
        success = failure_count == 0 or recovery_count > 0

        result = ChaosTestResult(
            test_name=test_name,
            success=success,
            failure_count=failure_count,
            recovery_count=recovery_count,
            test_duration_seconds=test_duration,
            error_messages=error_messages,
            timestamp=datetime.now(),
        )

        logger.info(
            "Network fault injection test completed: %s failures, %s recoveries",
            failure_count,
            recovery_count,
        )

        return result

    async def test_memory_pressure(
        self,
        adapter: Any,
        duration_seconds: float = 30.0,
        memory_pressure_level: float = 0.5,
    ) -> ChaosTestResult:
        """
        Test adapter resilience to memory pressure.

        Args:
            adapter: Adapter to test
            duration_seconds: Test duration in seconds
            memory_pressure_level: Level of memory pressure (0.0 to 1.0)

        Returns:
            Chaos test result
        """
        logger.info("Starting memory pressure test for %s seconds", duration_seconds)

        test_name = "memory_pressure"
        failure_count = 0
        recovery_count = 0
        error_messages = []
        start_time = datetime.now()

        try:
            # Initialize and connect adapter
            await adapter.initialize()
            await adapter.connect()

            # Create memory pressure
            memory_blocks: list[bytes] = []
            target_memory = int(
                memory_pressure_level * 100 * 1024 * 1024
            )  # MB to bytes

            # Run test with memory pressure
            while (datetime.now() - start_time).total_seconds() < duration_seconds:
                try:
                    # Apply memory pressure
                    if len(memory_blocks) * 1024 * 1024 < target_memory:
                        memory_blocks.append(b"\x00" * 1024 * 1024)  # 1MB block

                    # Test adapter operation
                    await self._test_adapter_operation(adapter)

                    # Check for recovery
                    if failure_count > 0 and await self._check_adapter_recovery(
                        adapter
                    ):
                        recovery_count += 1
                        failure_count = 0

                    await asyncio.sleep(0.1)  # 100ms loop

                except (ValueError, TypeError, KeyError, RuntimeError) as e:
                    error_messages.append(
                        f"Operation failed under memory pressure: {e}"
                    )
                    failure_count += 1
                    await asyncio.sleep(0.5)

        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            error_messages.append(f"Test setup failed: {e}")
            failure_count += 1

        finally:
            # Clean up memory blocks
            memory_blocks.clear()
            try:
                await adapter.disconnect()
            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                error_messages.append(f"Cleanup failed: {e}")

        test_duration = (datetime.now() - start_time).total_seconds()
        success = failure_count == 0 or recovery_count > 0

        result = ChaosTestResult(
            test_name=test_name,
            success=success,
            failure_count=failure_count,
            recovery_count=recovery_count,
            test_duration_seconds=test_duration,
            error_messages=error_messages,
            timestamp=datetime.now(),
        )

        logger.info(
            "Memory pressure test completed: %s failures, %s recoveries",
            failure_count,
            recovery_count,
        )

        return result

    async def test_rapid_connect_disconnect(
        self, adapter: Any, cycles: int = 10, cycle_delay_seconds: float = 0.1
    ) -> ChaosTestResult:
        """
        Test adapter resilience to rapid connect/disconnect cycles.

        Args:
            adapter: Adapter to test
            cycles: Number of connect/disconnect cycles
            cycle_delay_seconds: Delay between cycles

        Returns:
            Chaos test result
        """
        logger.info("Starting rapid connect/disconnect test with %s cycles", cycles)

        test_name = "rapid_connect_disconnect"
        failure_count = 0
        recovery_count = 0
        error_messages = []
        start_time = datetime.now()

        try:
            for cycle in range(cycles):
                try:
                    # Connect
                    await adapter.initialize()
                    await adapter.connect()

                    # Test operation
                    await self._test_adapter_operation(adapter)

                    # Disconnect
                    await adapter.disconnect()

                    # Short delay
                    await asyncio.sleep(cycle_delay_seconds)

                except (ValueError, TypeError, KeyError, RuntimeError) as e:
                    error_messages.append(f"Cycle {cycle} failed: {e}")
                    failure_count += 1

                    # Attempt recovery
                    try:
                        await adapter.disconnect()
                    except Exception as e:
                        logger.warning("Cleanup error during chaos test: %s", e)

        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            error_messages.append(f"Test setup failed: {e}")
            failure_count += 1

        test_duration = (datetime.now() - start_time).total_seconds()
        success = failure_count == 0 or recovery_count > 0

        result = ChaosTestResult(
            test_name=test_name,
            success=success,
            failure_count=failure_count,
            recovery_count=recovery_count,
            test_duration_seconds=test_duration,
            error_messages=error_messages,
            timestamp=datetime.now(),
        )

        logger.info(
            "Rapid connect/disconnect test completed: %s failures, %s recoveries",
            failure_count,
            recovery_count,
        )

        return result

    async def test_concurrent_operations(
        self, adapter: Any, concurrent_tasks: int = 5, duration_seconds: float = 10.0
    ) -> ChaosTestResult:
        """
        Test adapter resilience to concurrent operations.

        Args:
            adapter: Adapter to test
            concurrent_tasks: Number of concurrent tasks
            duration_seconds: Test duration in seconds

        Returns:
            Chaos test result
        """
        logger.info(
            "Starting concurrent operations test with %s tasks", concurrent_tasks
        )

        test_name = "concurrent_operations"
        failure_count = 0
        recovery_count = 0
        error_messages = []
        start_time = datetime.now()

        try:
            # Initialize and connect adapter
            await adapter.initialize()
            await adapter.connect()

            # Create concurrent tasks
            tasks = []
            for i in range(concurrent_tasks):
                task = asyncio.create_task(
                    self._concurrent_operation_worker(adapter, i, duration_seconds)
                )
                tasks.append(task)

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Count failures
            for task_result in results:
                if isinstance(task_result, Exception):
                    error_messages.append(f"Concurrent task failed: {task_result}")
                    failure_count += 1
                elif (
                    isinstance(task_result, dict) and task_result.get("failures", 0) > 0
                ):
                    failure_count += task_result["failures"]
                    error_messages.extend(task_result.get("errors", []))

        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            error_messages.append(f"Test setup failed: {e}")
            failure_count += 1

        finally:
            try:
                await adapter.disconnect()
            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                error_messages.append(f"Cleanup failed: {e}")

        test_duration = (datetime.now() - start_time).total_seconds()
        success = failure_count == 0 or recovery_count > 0

        result: ChaosTestResult = ChaosTestResult(
            test_name=test_name,
            success=success,
            failure_count=failure_count,
            recovery_count=recovery_count,
            test_duration_seconds=test_duration,
            error_messages=error_messages,
            timestamp=datetime.now(),
        )

        logger.info(
            "Concurrent operations test completed: %s failures, %s recoveries",
            failure_count,
            recovery_count,
        )

        return result

    async def run_comprehensive_chaos_tests(
        self, adapters: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Run comprehensive chaos tests on all adapters.

        Args:
            adapters: Dictionary of adapters to test

        Returns:
            Comprehensive chaos test results
        """
        results: dict[str, Any] = {
            "total_adapters": len(adapters),
            "adapter_results": {},
            "summary": {},
        }

        for adapter_name, adapter in adapters.items():
            adapter_results = []

            try:
                # Run different chaos tests
                chaos_tests = [
                    (
                        "network_fault_injection",
                        self.test_network_fault_injection(adapter),
                    ),
                    ("memory_pressure", self.test_memory_pressure(adapter)),
                    (
                        "rapid_connect_disconnect",
                        self.test_rapid_connect_disconnect(adapter),
                    ),
                    ("concurrent_operations", self.test_concurrent_operations(adapter)),
                ]

                for test_name, test_coro in chaos_tests:
                    try:
                        result = await test_coro
                        adapter_results.append(result)
                    except (ValueError, TypeError, KeyError, RuntimeError) as e:
                        error_result = ChaosTestResult(
                            test_name=test_name,
                            success=False,
                            failure_count=1,
                            recovery_count=0,
                            test_duration_seconds=0.0,
                            error_messages=[f"Test failed: {e}"],
                            timestamp=datetime.now(),
                        )
                        adapter_results.append(error_result)

                results["adapter_results"][adapter_name] = adapter_results

            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                logger.error("Chaos tests failed for adapter %s: %s", adapter_name, e)
                results["adapter_results"][adapter_name] = []

        # Generate summary
        results["summary"] = self._generate_chaos_summary(results["adapter_results"])

        return results

    async def _inject_network_fault(self) -> None:
        """Inject a network fault."""
        # Simulate network delay
        delay = random.uniform(0.1, 1.0)
        await asyncio.sleep(delay)

        # Simulate network error with probability
        if random.random() < 0.3:
            raise ConnectionError("Simulated network error")

    async def _test_adapter_operation(self, adapter: Any) -> None:
        """Test adapter operation."""
        if isinstance(adapter, AudioCaptureProtocol):
            await adapter.read_audio_frame()
        elif isinstance(adapter, AudioPlaybackProtocol):
            dummy_frame = PCMFrame(
                pcm=b"\x00" * 1024,
                timestamp=time.time(),
                rms=0.0,
                duration=0.1,
                sequence=1,
                sample_rate=16000,
            )
            await adapter.play_audio_chunk(dummy_frame)
        elif isinstance(adapter, SurfaceControlProtocol):
            dummy_event = WakeDetectedEvent(
                timestamp=time.time(), confidence=0.9, ts_device=time.time()
            )
            await adapter.send_event(dummy_event)
        elif isinstance(adapter, SurfaceTelemetryProtocol):
            _ = adapter.is_connected

    async def _check_adapter_recovery(self, adapter: Any) -> bool:
        """Check if adapter has recovered."""
        try:
            if isinstance(adapter, SurfaceTelemetryProtocol):
                return adapter.is_connected
            else:
                # For other adapters, try a simple operation
                await self._test_adapter_operation(adapter)
                return True
        except (ValueError, TypeError, KeyError, RuntimeError):
            return False

    async def _concurrent_operation_worker(
        self, adapter: Any, worker_id: int, duration_seconds: float
    ) -> dict[str, Any]:
        """Worker for concurrent operations test."""
        failures = 0
        errors = []
        start_time = datetime.now()

        try:
            while (datetime.now() - start_time).total_seconds() < duration_seconds:
                try:
                    await self._test_adapter_operation(adapter)
                    await asyncio.sleep(0.01)  # 10ms loop
                except (ValueError, TypeError, KeyError, RuntimeError) as e:
                    failures += 1
                    errors.append(f"Worker {worker_id}: {e}")
                    await asyncio.sleep(0.1)  # Longer delay on error

        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            failures += 1
            errors.append(f"Worker {worker_id} setup failed: {e}")

        return {"worker_id": worker_id, "failures": failures, "errors": errors}

    def _generate_chaos_summary(
        self, adapter_results: dict[str, list[ChaosTestResult]]
    ) -> dict[str, Any]:
        """Generate chaos test summary."""
        if not adapter_results:
            return {"error": "No adapter results available"}

        total_tests = 0
        successful_tests = 0
        total_failures = 0
        total_recoveries = 0

        for results in adapter_results.values():
            for result in results:
                total_tests += 1
                if result.success:
                    successful_tests += 1
                total_failures += result.failure_count
                total_recoveries += result.recovery_count

        return {
            "total_adapters": len(adapter_results),
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": successful_tests / max(total_tests, 1),
            "total_failures": total_failures,
            "total_recoveries": total_recoveries,
            "recovery_rate": (
                total_recoveries / max(total_failures, 1) if total_failures > 0 else 1.0
            ),
        }
