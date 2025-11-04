"""Health check management for service resilience."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

from .structured_logging import get_logger


class HealthStatus(Enum):
    """Service health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(slots=True)
class HealthCheck:
    """Health check result."""

    status: HealthStatus
    ready: bool  # Can serve requests
    details: dict[str, Any]


class HealthManager:
    """Manages service health state and dependency checks."""

    def __init__(
        self,
        service_name: str,
        dependency_cache_ttl_seconds: float = 10.0,
    ):
        self._service_name = service_name
        self._dependencies: dict[str, Callable[[], Any]] = {}
        self._startup_complete = False
        self._startup_time = time.time()
        self._logger = get_logger(__name__, service_name=service_name)

        # Initialize observability manager for metrics (will be set later)
        self._observability_manager: Any | None = None
        self._health_check_duration: Any | None = None
        self._health_status_gauge: Any | None = None
        self._dependency_status_gauge: Any | None = None
        self._last_dependency_states: dict[str, bool] = {}

        # Dependency check caching to prevent excessive health check calls
        self._dep_cache_ttl = max(0.0, dependency_cache_ttl_seconds)
        self._dep_cache: dict[
            str, dict[str, Any]
        ] = {}  # name -> {"result": bool, "ts": float}
        self._dep_locks: dict[
            str, asyncio.Lock
        ] = {}  # per-dependency locks to avoid stampede

        # Startup failure tracking
        self._startup_failure: dict[str, Any] | None = None

    def set_observability_manager(self, observability_manager: Any) -> None:
        """Set the observability manager for metrics."""
        self._observability_manager = observability_manager
        meter = observability_manager.get_meter()
        if meter:
            self._health_check_duration = meter.create_histogram(
                "health_check_duration_seconds",
                unit="s",
                description="Health check execution duration",
            )
            # Use gauge (observable gauge) for current health status
            # Note: OpenTelemetry Python SDK doesn't have a direct synchronous gauge,
            # so we use up_down_counter with reset semantics (add positive for healthy, add negative to reset)
            self._health_status_gauge = meter.create_up_down_counter(
                "service_health_status",
                unit="1",
                description="Current service health status (1=healthy, 0.5=degraded, 0=unhealthy)",
            )
            self._dependency_status_gauge = meter.create_up_down_counter(
                "service_dependency_health",
                unit="1",
                description="Dependency health status (1=healthy, 0=unhealthy)",
            )

    def register_dependency(self, name: str, check: Callable[[], Any]) -> None:
        """Register a dependency health check."""
        self._dependencies[name] = check
        self._logger.debug("health.dependency_registered", dependency=name)

    def _get_effective_cache_ttl(self) -> float:
        """Get cache TTL based on startup phase.

        Returns:
            - 1.0s during startup phase (first 60s)
            - 5.0s during early operation (60-300s)
            - 10.0s during steady state (300s+) - uses configured value
        """
        elapsed = time.time() - self._startup_time
        if elapsed < 60.0:
            return 1.0  # Startup: frequent checks
        elif elapsed < 300.0:
            return 5.0  # Early operation: moderate
        else:
            return self._dep_cache_ttl  # Steady state: configured value

    async def _check_dependency(
        self,
        name: str,
        check: Callable[[], Any],
        elapsed_since_startup: float,
        effective_cache_ttl: float,
    ) -> dict[str, Any]:
        """Check a single dependency with caching and locking.

        Returns dependency status dict with available, checked_at, cached, and optional error fields.
        """
        now_monotonic = time.monotonic()

        # Fast path: check cache first (outside lock for performance)
        cached = self._dep_cache.get(name)
        if (
            cached is not None
            and (now_monotonic - float(cached.get("ts", 0.0))) < effective_cache_ttl
        ):
            # Use cached result
            is_healthy = bool(cached.get("result"))
            return {
                "available": is_healthy,
                "checked_at": time.time(),
                "cached": True,
            }

        # Acquire per-dependency lock to prevent concurrent checks of same dependency
        lock = self._dep_locks.setdefault(name, asyncio.Lock())
        async with lock:
            # Re-check cache inside lock (another call may have updated it)
            cached = self._dep_cache.get(name)
            now_monotonic = time.monotonic()
            if (
                cached is not None
                and (now_monotonic - float(cached.get("ts", 0.0))) < effective_cache_ttl
            ):
                is_healthy = bool(cached.get("result"))
                return {
                    "available": is_healthy,
                    "checked_at": time.time(),
                    "cached": True,
                }

            # Perform actual dependency check with timeout
            try:
                if asyncio.iscoroutinefunction(check):
                    is_healthy = await asyncio.wait_for(check(), timeout=2.0)
                else:
                    # Offload sync work to thread if potentially blocking
                    loop = asyncio.get_running_loop()
                    is_healthy = await asyncio.wait_for(
                        loop.run_in_executor(None, check), timeout=2.0
                    )

                # Cache the result
                self._dep_cache[name] = {
                    "result": bool(is_healthy),
                    "ts": now_monotonic,
                }

                return {
                    "available": is_healthy,
                    "checked_at": time.time(),
                    "cached": False,
                }
            except TimeoutError:
                # Timeout treated as failure
                self._dep_cache[name] = {"result": False, "ts": now_monotonic}
                return {
                    "available": False,
                    "error": "Timeout",
                    "error_type": "TimeoutError",
                    "checked_at": time.time(),
                    "cached": False,
                }
            except Exception as exc:
                # Cache failure result
                self._dep_cache[name] = {"result": False, "ts": now_monotonic}
                # Determine log level based on startup phase
                is_startup_phase = elapsed_since_startup < 60.0
                log_level = "debug" if is_startup_phase else "warning"
                getattr(self._logger, log_level)(
                    "health.dependency_error",
                    dependency=name,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    elapsed_since_startup_seconds=round(elapsed_since_startup, 1),
                    is_startup_phase=is_startup_phase,
                )
                return {
                    "available": False,
                    "error": f"{type(exc).__name__}: {str(exc)}",
                    "error_type": type(exc).__name__,
                    "checked_at": time.time(),
                    "cached": False,
                }

    async def check_ready(self) -> bool:
        """Check if service is ready (all critical deps available).

        Returns False if:
        - Startup is not complete (startup_complete=False)
        - Any registered dependency check returns False (e.g., models still loading)

        This allows services to return 503 during model downloads and cache warmup.

        Checks all dependencies in parallel for better performance.
        """
        if not self._startup_complete:
            return False

        if not self._dependencies:
            return True

        # Check all dependencies in parallel
        effective_cache_ttl = self._get_effective_cache_ttl()
        elapsed_since_startup = time.time() - self._startup_time
        tasks = [
            self._check_dependency(
                name, check, elapsed_since_startup, effective_cache_ttl
            )
            for name, check in self._dependencies.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Return False if any dependency is unhealthy
        dependency_names = list(self._dependencies.keys())
        for i, result in enumerate(results):
            name = dependency_names[i]
            if isinstance(result, Exception):
                self._logger.warning(
                    "health.dependency_check_failed", dependency=name, error=str(result)
                )
                return False

            # Type narrowing: result is dict[str, Any] here (Exception was handled above)
            dep_status: dict[str, Any] = cast(dict[str, Any], result)
            if not dep_status.get("available", False):
                self._logger.debug("health.dependency_unhealthy", dependency=name)
                return False

        return True

    async def check_live(self) -> bool:
        """Check if service process is alive."""
        return True  # If we can execute this, process is alive

    def record_startup_failure(
        self,
        error: Exception,
        component: str | None = None,
        is_critical: bool = True,
    ) -> None:
        """Record a startup failure.

        Args:
            error: The exception that occurred during startup.
            component: Optional component name where the failure occurred.
            is_critical: If True, prevents mark_startup_complete() from succeeding.
                        If False, failure is recorded but doesn't block readiness.

        If is_critical=True, prevents startup_complete from being marked.
        """
        self._startup_failure = {
            "error": str(error),
            "error_type": type(error).__name__,
            "component": component,
            "is_critical": is_critical,
            "timestamp": time.time(),
        }
        if is_critical:
            self._logger.error(
                "health.startup_failure_recorded",
                component=component,
                error_type=type(error).__name__,
                error=str(error),
                is_critical=is_critical,
            )
        else:
            self._logger.warning(
                "health.startup_failure_recorded_non_critical",
                component=component,
                error_type=type(error).__name__,
                error=str(error),
            )

    def get_startup_failure(self) -> dict[str, Any] | None:
        """Get startup failure details if any.

        Returns:
            Dict with failure details (error, error_type, component, is_critical, timestamp)
            or None if no failure recorded.
        """
        return self._startup_failure

    def has_startup_failure(self) -> bool:
        """Check if critical startup failure occurred.

        Returns:
            True if a critical startup failure was recorded, False otherwise.
        """
        return self._startup_failure is not None and self._startup_failure.get(
            "is_critical", True
        )

    def mark_startup_complete(self) -> None:
        """Mark that startup initialization is complete.

        IMPORTANT: Services should call this AFTER initiating background model loading,
        NOT after models finish loading. This allows the service to:
        1. Start accepting HTTP requests immediately (uvicorn can respond)
        2. Return 503 from /health/ready until dependencies (models) are ready
        3. Allow orchestrators to detect initialization status

        Dependencies should be registered before calling this method so health checks
        can properly detect when models are still downloading or caches are warming up.

        If a critical startup failure was recorded, this method will not mark startup
        complete and will log a warning instead.
        """
        if self.has_startup_failure():
            self._logger.warning(
                "health.startup_complete_blocked",
                reason="critical_startup_failure",
                failure=self._startup_failure,
            )
            return  # Don't mark complete if critical failure occurred

        self._startup_complete = True
        self._logger.info("health.startup_complete", service=self._service_name)
        # Update startup metric using OpenTelemetry
        if self._health_status_gauge:
            self._health_status_gauge.add(
                1, attributes={"service": self._service_name, "component": "startup"}
            )

    async def get_health_status(self) -> HealthCheck:
        """Get current health status with metrics.

        Returns:
            HealthCheck with status, ready flag, and details dict.

        Dependency status format:
            dependencies: {
                "dependency_name": {
                    "available": bool,
                    "checked_at": float,  # Unix timestamp
                    "error": str,  # Optional, present if available=False
                    "error_type": str  # Optional, present if error exists
                }
            }
        """
        start_time = time.time()
        elapsed_since_startup = time.time() - self._startup_time

        try:
            # Check for startup failure first
            startup_failure = self.get_startup_failure()
            if startup_failure and startup_failure.get("is_critical", True):
                return HealthCheck(
                    status=HealthStatus.UNHEALTHY,
                    ready=False,
                    details={
                        "reason": "startup_failed",
                        "startup_failure": {
                            "component": startup_failure.get("component"),
                            "error_type": startup_failure.get("error_type"),
                            "error": startup_failure.get("error"),
                        },
                    },
                )

            if not self._startup_complete:
                return HealthCheck(
                    status=HealthStatus.UNHEALTHY,
                    ready=False,
                    details={"reason": "startup_not_complete"},
                )

            ready = True
            dependency_status: dict[str, dict[str, Any]] = {}
            failing_dependencies: list[str] = []

            # Check all dependencies in parallel
            effective_cache_ttl = self._get_effective_cache_ttl()
            tasks = [
                self._check_dependency(
                    name, check, elapsed_since_startup, effective_cache_ttl
                )
                for name, check in self._dependencies.items()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            dependency_names = list(self._dependencies.keys())
            for i, result in enumerate(results):
                name = dependency_names[i]
                if isinstance(result, Exception):
                    # Exception occurred during check
                    dependency_status[name] = {
                        "available": False,
                        "error": f"{type(result).__name__}: {str(result)}",
                        "error_type": type(result).__name__,
                        "checked_at": time.time(),
                    }
                    failing_dependencies.append(name)
                    ready = False
                else:
                    # Type narrowing: result is dict[str, Any] here (Exception was handled above)
                    dep_status: dict[str, Any] = cast(dict[str, Any], result)
                    dependency_status[name] = dep_status

                    # Update dependency metric using OpenTelemetry
                    if self._dependency_status_gauge:
                        self._dependency_status_gauge.add(
                            1 if dep_status.get("available", False) else 0,
                            attributes={
                                "service": self._service_name,
                                "dependency": name,
                            },
                        )

                    if not dep_status.get("available", False):
                        failing_dependencies.append(name)
                        ready = False

            # Only log dependency warnings when status changes
            current_failing = set(failing_dependencies)
            previous_failing = {
                name
                for name, status in self._last_dependency_states.items()
                if not status
            }
            is_startup_phase = elapsed_since_startup < 60.0

            if current_failing != previous_failing:
                if failing_dependencies:
                    # Use info level during startup phase, warning after
                    log_level = "info" if is_startup_phase else "warning"
                    getattr(self._logger, log_level)(
                        "health.dependency_unhealthy",
                        service=self._service_name,
                        failing_dependencies=failing_dependencies,
                        is_startup_phase=is_startup_phase,
                        elapsed_since_startup_seconds=round(elapsed_since_startup, 1),
                    )
                elif previous_failing:
                    # All dependencies became healthy
                    self._logger.info(
                        "health.all_dependencies_healthy",
                        service=self._service_name,
                        elapsed_since_startup_seconds=round(elapsed_since_startup, 1),
                    )

            # Update last known states - extract available bool for state tracking
            current_states: dict[str, bool] = {
                name: bool(dep_status.get("available", False))
                for name, dep_status in dependency_status.items()
            }
            self._last_dependency_states = current_states

            status = HealthStatus.HEALTHY if ready else HealthStatus.DEGRADED

            # Update overall health metric using OpenTelemetry
            if self._health_status_gauge:
                status_value = (
                    1
                    if status == HealthStatus.HEALTHY
                    else 0.5
                    if status == HealthStatus.DEGRADED
                    else 0
                )
                self._health_status_gauge.add(
                    status_value,
                    attributes={"service": self._service_name, "component": "overall"},
                )

            return HealthCheck(
                status=status,
                ready=ready,
                details={
                    "startup_complete": self._startup_complete,
                    "dependencies": dependency_status,
                },
            )
        finally:
            # Record health check duration
            duration = time.time() - start_time
            if self._health_check_duration:
                self._health_check_duration.record(
                    duration,
                    attributes={"service": self._service_name, "check_type": "ready"},
                )


__all__ = ["HealthCheck", "HealthManager", "HealthStatus"]
