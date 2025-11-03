"""Health check management for service resilience."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

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

    def __init__(self, service_name: str):
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

    async def check_ready(self) -> bool:
        """Check if service is ready (all critical deps available).

        Returns False if:
        - Startup is not complete (startup_complete=False)
        - Any registered dependency check returns False (e.g., models still loading)

        This allows services to return 503 during model downloads and cache warmup.
        """
        if not self._startup_complete:
            return False

        for name, check in self._dependencies.items():
            try:
                if asyncio.iscoroutinefunction(check):
                    is_healthy = await check()
                else:
                    is_healthy = check()

                if not is_healthy:
                    self._logger.debug("health.dependency_unhealthy", dependency=name)
                    return False
            except Exception as exc:
                self._logger.warning(
                    "health.dependency_check_failed", dependency=name, error=str(exc)
                )
                return False

        return True

    async def check_live(self) -> bool:
        """Check if service process is alive."""
        return True  # If we can execute this, process is alive

    def mark_startup_complete(self) -> None:
        """Mark that startup initialization is complete.

        IMPORTANT: Services should call this AFTER initiating background model loading,
        NOT after models finish loading. This allows the service to:
        1. Start accepting HTTP requests immediately (uvicorn can respond)
        2. Return 503 from /health/ready until dependencies (models) are ready
        3. Allow orchestrators to detect initialization status

        Dependencies should be registered before calling this method so health checks
        can properly detect when models are still downloading or caches are warming up.
        """
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

        try:
            if not self._startup_complete:
                return HealthCheck(
                    status=HealthStatus.UNHEALTHY,
                    ready=False,
                    details={"reason": "startup_not_complete"},
                )

            ready = True
            dependency_status = {}
            failing_dependencies = []

            for name, check in self._dependencies.items():
                try:
                    if asyncio.iscoroutinefunction(check):
                        is_healthy = await check()
                    else:
                        is_healthy = check()

                    dependency_status[name] = {
                        "available": is_healthy,
                        "checked_at": time.time(),
                    }

                    # Update dependency metric using OpenTelemetry
                    if self._dependency_status_gauge:
                        self._dependency_status_gauge.add(
                            1 if is_healthy else 0,
                            attributes={
                                "service": self._service_name,
                                "dependency": name,
                            },
                        )

                    if not is_healthy:
                        failing_dependencies.append(name)
                        ready = False
                except Exception as exc:
                    elapsed_since_startup = time.time() - self._startup_time
                    dependency_status[name] = {
                        "available": False,
                        "error": f"{type(exc).__name__}: {str(exc)}",
                        "error_type": type(exc).__name__,
                        "checked_at": time.time(),
                    }
                    failing_dependencies.append(name)
                    ready = False
                    if self._dependency_status_gauge:
                        self._dependency_status_gauge.add(
                            0,
                            attributes={
                                "service": self._service_name,
                                "dependency": name,
                            },
                        )
                    # Determine log level based on startup phase
                    # Errors during first 60 seconds might be expected (services starting)
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

            # Only log dependency warnings when status changes
            current_failing = set(failing_dependencies)
            previous_failing = {
                name
                for name, status in self._last_dependency_states.items()
                if not status
            }

            if current_failing != previous_failing:
                if failing_dependencies:
                    self._logger.warning(
                        "health.dependency_unhealthy",
                        service=self._service_name,
                        failing_dependencies=failing_dependencies,
                    )
                elif previous_failing:
                    # All dependencies became healthy
                    self._logger.info(
                        "health.all_dependencies_healthy",
                        service=self._service_name,
                    )

            # Update last known states - extract available bool for state tracking
            current_states = {
                name: status.get("available", False)
                for name, status in dependency_status.items()
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
