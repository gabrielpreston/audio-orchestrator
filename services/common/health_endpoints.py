"""
Common health endpoints module for standardized health checks across all services.

This module provides a standardized HealthEndpoints class that can be used by all services
to implement consistent health check endpoints (/health/live, /health/ready, /health/dependencies).
"""

import asyncio
import time
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, HTTPException

from services.common.health import HealthManager, HealthStatus


class HealthEndpoints:
    """Standardized health endpoints for all services."""

    def __init__(
        self,
        service_name: str,
        health_manager: HealthManager,
        custom_components: dict[str, Any] | None = None,
        custom_dependencies: dict[str, Callable[[], Any]] | None = None,
        # Optimization parameters (sane defaults)
        dependency_cache_ttl_seconds: float = 3.0,
        dependency_check_timeout_seconds: float = 2.0,
        dependency_retry_attempts: int = 1,
        dependency_retry_backoff_seconds: float = 0.2,
        dependency_circuit_fail_threshold: int = 3,
        dependency_circuit_open_seconds: float = 10.0,
        dependency_max_concurrency: int = 4,
    ) -> None:
        """
        Initialize health endpoints.

        Args:
            service_name: Name of the service (e.g., "discord", "stt")
            health_manager: HealthManager instance for the service
            custom_components: Optional dict of custom component checks
            custom_dependencies: Optional dict of custom dependency check functions
        """
        self.service_name = service_name
        self.health_manager = health_manager
        self.custom_components = custom_components or {}
        self.custom_dependencies = custom_dependencies or {}
        self.router = APIRouter()

        # Dependency optimization state
        self._dep_cache_ttl = max(0.0, dependency_cache_ttl_seconds)
        self._dep_timeout = max(0.1, dependency_check_timeout_seconds)
        self._dep_retries = max(0, dependency_retry_attempts)
        self._dep_backoff = max(0.0, dependency_retry_backoff_seconds)
        self._dep_fail_threshold = max(1, dependency_circuit_fail_threshold)
        self._dep_circuit_open_seconds = max(0.0, dependency_circuit_open_seconds)
        self._dep_max_concurrency = max(1, dependency_max_concurrency)

        # name -> {"result": bool, "ts": float}
        self._dep_cache: dict[str, dict[str, Any]] = {}
        # name -> consecutive failure count
        self._dep_failures: dict[str, int] = {}
        # name -> open-until timestamp (monotonic)
        self._dep_circuit_open_until: dict[str, float] = {}
        # per-dependency locks to avoid stampede
        self._dep_locks: dict[str, asyncio.Lock] = {}
        # global limiter
        self._dep_semaphore = asyncio.Semaphore(self._dep_max_concurrency)

        # Register the health endpoints
        self._register_endpoints()

    def _register_endpoints(self) -> None:
        """Register all health endpoints with the router."""
        self.router.add_api_route("/health/live", self.health_live, methods=["GET"])
        self.router.add_api_route("/health/ready", self.health_ready, methods=["GET"])
        self.router.add_api_route(
            "/health/dependencies", self.health_dependencies, methods=["GET"]
        )

    def _make_serializable(self, obj: Any) -> Any:
        """
        Recursively make an object JSON-serializable by filtering out non-serializable types.

        Args:
            obj: Object to make serializable

        Returns:
            Serializable version of the object (None if object can't be serialized)
        """
        if obj is None:
            return None
        elif callable(obj) or isinstance(obj, type):
            # Filter out functions, methods, and types
            return None
        elif isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if not callable(k) and not isinstance(k, type):
                    serialized = self._make_serializable(v)
                    # Only include if serialization produced a valid value
                    # Use 'is not None' check but allow False/0/"" values
                    if serialized is not None or v is None:
                        result[k] = serialized
            return result
        elif isinstance(obj, (list, tuple)):
            serialized_items = []
            for item in obj:
                if not callable(item) and not isinstance(item, type):
                    serialized = self._make_serializable(item)
                    if serialized is not None or item is None:
                        serialized_items.append(serialized)
            return serialized_items
        elif isinstance(obj, (str, int, float, bool)):
            # Primitive types are always serializable
            return obj
        else:
            # Try to convert to string for unknown types
            try:
                import json

                # Test if it's JSON serializable
                json.dumps(obj)
                return obj
            except (TypeError, ValueError):
                # Convert to string as fallback
                try:
                    return str(obj)
                except Exception:
                    return None

    async def health_live(self) -> dict[str, str]:
        """
        Liveness check - always returns 200 if process is alive.

        Returns:
            Dict with status and service name
        """
        return {"status": "alive", "service": self.service_name}

    async def health_ready(self) -> dict[str, Any]:
        """
        Readiness check with component and dependency status.

        IMPORTANT: This endpoint is accessible immediately when uvicorn starts, even during
        service startup. It returns 503 Service Unavailable if:
        - Startup is not complete yet (startup_complete=False)
        - Critical dependencies are not ready (models downloading, caches warming, etc.)

        This allows orchestrators and load balancers to detect when services are still
        initializing and route traffic appropriately. Services should mark startup_complete
        early (after initiating background model loading) and register dependencies that
        check model loading status.

        Returns:
            Dict with detailed readiness information

        Raises:
            HTTPException: 503 with error detail in JSON response body ({"detail": "message"})
                if service is not ready. Error detail includes dependency names and error messages.
        """
        # Check if startup is complete first
        # This ensures 503 is returned during startup before models finish downloading
        if not self.health_manager._startup_complete:
            raise HTTPException(
                status_code=503,
                detail=f"Service {self.service_name} not ready - startup not complete",
            )

        # Get health status from health manager
        health_status = await self.health_manager.get_health_status()

        # If service is not ready, return 503 Service Unavailable
        # This allows circuit breakers and health checkers to properly detect unavailable services
        if not health_status.ready:
            status_str = (
                "degraded"
                if health_status.status == HealthStatus.DEGRADED
                else "not_ready"
            )
            # Extract failing dependencies with error details
            failing_deps = []
            failing_deps_with_errors = []
            for name, status in health_status.details.get("dependencies", {}).items():
                # Status is now always a dict with "available" and optional "error" fields
                is_available = (
                    status.get("available", False)
                    if isinstance(status, dict)
                    else bool(status)
                )
                if not is_available:
                    failing_deps.append(name)
                    if isinstance(status, dict):
                        error_info = status.get("error")
                        if error_info:
                            # Truncate long error messages to prevent excessive response size
                            max_error_len = 200
                            if len(error_info) > max_error_len:
                                error_info = error_info[:max_error_len] + "..."
                            failing_deps_with_errors.append(f"{name}: {error_info}")

            detail = f"Service {self.service_name} not ready - {status_str}"
            if failing_deps_with_errors:
                detail += f" (dependency errors: {'; '.join(failing_deps_with_errors)})"
            elif failing_deps:
                detail += f" (unavailable dependencies: {', '.join(failing_deps)})"

            raise HTTPException(
                status_code=503,
                detail=detail,
            )

        status_str = "ready"

        # Build components dict - evaluate callables first to avoid serialization issues
        components: dict[str, Any] = {
            "startup_complete": self.health_manager._startup_complete,
        }

        # Process custom components - evaluate callables before adding to dict
        for component_name, component_value in self.custom_components.items():
            if callable(component_value):
                try:
                    if asyncio.iscoroutinefunction(component_value):
                        evaluated_value = await component_value()
                    else:
                        evaluated_value = component_value()
                    # Ensure the evaluated value is serializable
                    components[component_name] = self._make_serializable(
                        evaluated_value
                    )
                except Exception:
                    components[component_name] = False
            elif isinstance(component_value, (dict, list)):
                components[component_name] = self._make_serializable(component_value)
            else:
                components[component_name] = bool(component_value)

        # Make all response values serializable - recursively filter everything
        health_details = self._make_serializable(health_status.details) or {}
        dependencies = (
            self._make_serializable(health_status.details.get("dependencies", {})) or {}
        )

        return {
            "status": status_str,
            "service": self.service_name,
            "components": components,
            "dependencies": dependencies,
            "health_details": health_details,
        }

    async def health_dependencies(self) -> dict[str, Any]:
        """
        Dependency health check endpoint.

        Returns:
            Dict with dependency status information including error details for failed dependencies.
            Format: {
                "service": str,
                "dependencies": {
                    "dep_name": {
                        "status": "healthy" | "unhealthy",
                        "available": bool,
                        "error": str,  # Optional, present if available=False
                        "error_type": str,  # Optional, present if error exists
                        "checked_at": float  # Optional, Unix timestamp
                    }
                },
                "startup_complete": bool
            }
        """
        dependencies: dict[str, dict[str, Any]] = {}

        # Run dependency checks with caching, retries, timeouts, circuit-breaker, and concurrency limits
        async def _evaluate_dependency(
            dep_name: str, dep_check: Callable[[], Any]
        ) -> tuple[str, dict[str, Any]]:
            now = time.monotonic()

            # Circuit breaker: if open, return cached unhealthy immediately
            open_until = self._dep_circuit_open_until.get(dep_name, 0.0)
            if open_until > now:
                cached = self._dep_cache.get(dep_name)
                if cached is not None:
                    return dep_name, {
                        "status": "healthy" if cached.get("result") else "unhealthy",
                        "available": bool(cached.get("result")),
                    }
                return dep_name, {"status": "unhealthy", "available": False}

            # Cache: serve fresh results
            cached = self._dep_cache.get(dep_name)
            if (
                cached is not None
                and (now - float(cached.get("ts", 0.0))) < self._dep_cache_ttl
            ):
                return dep_name, {
                    "status": "healthy" if cached.get("result") else "unhealthy",
                    "available": bool(cached.get("result")),
                }

            # Acquire per-dependency lock to avoid duplicate work
            lock = self._dep_locks.setdefault(dep_name, asyncio.Lock())
            async with lock:
                # Re-check cache inside lock
                cached = self._dep_cache.get(dep_name)
                now = time.monotonic()
                if (
                    cached is not None
                    and (now - float(cached.get("ts", 0.0))) < self._dep_cache_ttl
                ):
                    return dep_name, {
                        "status": "healthy" if cached.get("result") else "unhealthy",
                        "available": bool(cached.get("result")),
                    }

                # Perform the check with retries and timeout, limited by semaphore
                attempt = 0
                result = False
                async with self._dep_semaphore:
                    while True:
                        try:
                            if asyncio.iscoroutinefunction(dep_check):
                                result = await asyncio.wait_for(
                                    dep_check(), timeout=self._dep_timeout
                                )
                            else:
                                # Offload sync work to thread if potentially blocking
                                loop = asyncio.get_running_loop()
                                result = await asyncio.wait_for(
                                    loop.run_in_executor(None, dep_check),
                                    timeout=self._dep_timeout,
                                )
                            if result:
                                # Success: reset failures and close circuit
                                self._dep_failures[dep_name] = 0
                                if dep_name in self._dep_circuit_open_until:
                                    self._dep_circuit_open_until.pop(dep_name, None)
                                break
                            # Treat False as a failure eligible for retry
                            attempt += 1
                            if attempt > self._dep_retries:
                                break
                            backoff = (
                                self._dep_backoff * (2 ** (attempt - 1))
                                if self._dep_backoff > 0
                                else 0.0
                            )
                            if backoff > 0:
                                await asyncio.sleep(backoff)
                        except Exception:  # timeout or function error
                            attempt += 1
                            # Increment failure count and possibly open circuit after loop
                            if attempt > self._dep_retries:
                                break
                            # Backoff before retry
                            backoff = (
                                self._dep_backoff * (2 ** (attempt - 1))
                                if self._dep_backoff > 0
                                else 0.0
                            )
                            if backoff > 0:
                                await asyncio.sleep(backoff)

                # Update circuit breaker state
                if not result:
                    self._dep_failures[dep_name] = (
                        self._dep_failures.get(dep_name, 0) + 1
                    )
                    if self._dep_failures[dep_name] >= self._dep_fail_threshold:
                        self._dep_circuit_open_until[dep_name] = (
                            time.monotonic() + self._dep_circuit_open_seconds
                        )
                else:
                    self._dep_failures[dep_name] = 0

                # Cache the result
                self._dep_cache[dep_name] = {
                    "result": bool(result),
                    "ts": time.monotonic(),
                }

                if result:
                    return dep_name, {"status": "healthy", "available": True}
                # On failure, include minimal error info without changing schema expected by tests
                return dep_name, {"status": "unhealthy", "available": False}

        # Launch evaluations concurrently (respecting semaphore within)
        tasks = [
            asyncio.create_task(_evaluate_dependency(dep_name, dep_check))
            for dep_name, dep_check in self.custom_dependencies.items()
        ]
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=False)
            for dep_name, dep_info in results:
                dependencies[dep_name] = dep_info

        # Get health manager dependencies
        health_status = await self.health_manager.get_health_status()
        health_deps = (
            self._make_serializable(health_status.details.get("dependencies", {})) or {}
        )

        # Merge health manager dependencies
        for dep_name, dep_status in health_deps.items():
            if dep_name not in dependencies:
                # dep_status is now always a dict with "available" and optional "error" fields
                is_available = (
                    dep_status.get("available", False)
                    if isinstance(dep_status, dict)
                    else bool(dep_status)
                )
                dependencies[dep_name] = {
                    "status": "healthy" if is_available else "unhealthy",
                    "available": is_available,
                }
                # Include error information if present
                if (
                    isinstance(dep_status, dict)
                    and not is_available
                    and "error" in dep_status
                ):
                    dependencies[dep_name]["error"] = dep_status["error"]
                    dependencies[dep_name]["error_type"] = dep_status.get(
                        "error_type", "unknown"
                    )
                    if "checked_at" in dep_status:
                        dependencies[dep_name]["checked_at"] = dep_status["checked_at"]

        # Ensure all dependency data is serializable
        dependencies = self._make_serializable(dependencies) or {}

        return {
            "service": self.service_name,
            "dependencies": dependencies,
            "startup_complete": self.health_manager._startup_complete,
        }

    def get_router(self) -> APIRouter:
        """
        Get the FastAPI router with all health endpoints.

        Returns:
            APIRouter instance with health endpoints
        """
        return self.router
