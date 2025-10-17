"""Health check management for service resilience."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .logging import get_logger


class HealthStatus(Enum):
    """Service health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
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
        self._logger = get_logger(__name__, service_name=service_name)

    def register_dependency(self, name: str, check: Callable[[], Any]) -> None:
        """Register a dependency health check."""
        self._dependencies[name] = check
        self._logger.debug("health.dependency_registered", dependency=name)

    async def check_ready(self) -> bool:
        """Check if service is ready (all critical deps available)."""
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
        """Mark that startup initialization is complete."""
        self._startup_complete = True
        self._logger.info("health.startup_complete", service=self._service_name)

    async def get_health_status(self) -> HealthCheck:
        """Get current health status."""
        if not self._startup_complete:
            return HealthCheck(
                status=HealthStatus.UNHEALTHY,
                ready=False,
                details={"reason": "startup_not_complete"},
            )

        ready = True
        dependency_status = {}

        for name, check in self._dependencies.items():
            try:
                if asyncio.iscoroutinefunction(check):
                    is_healthy = await check()
                else:
                    is_healthy = check()

                dependency_status[name] = is_healthy
                if not is_healthy:
                    ready = False
            except Exception as exc:
                dependency_status[name] = False
                ready = False
                self._logger.warning(
                    "health.dependency_error", dependency=name, error=str(exc)
                )

        status = HealthStatus.HEALTHY if ready else HealthStatus.DEGRADED

        return HealthCheck(
            status=status,
            ready=ready,
            details={
                "startup_complete": self._startup_complete,
                "dependencies": dependency_status,
            },
        )


__all__ = ["HealthStatus", "HealthCheck", "HealthManager"]
