"""Circuit breaker implementation for service resilience."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .structured_logging import get_logger


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: float = 30.0
    max_timeout_seconds: float = 300.0


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures."""

    def __init__(self, name: str, config: CircuitBreakerConfig):
        self._name = name
        self._config = config
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._logger = get_logger(__name__)

    def is_available(self) -> bool:
        """Check if circuit allows requests."""
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if timeout has passed
            if self._last_failure_time is None:
                return False

            elapsed = time.time() - self._last_failure_time
            timeout = min(
                self._config.timeout_seconds * (2**self._failure_count),
                self._config.max_timeout_seconds,
            )

            if elapsed >= timeout:
                self._transition_to_half_open()
                return True

            return False

        return self._state == CircuitState.HALF_OPEN

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute function with circuit breaker protection."""
        if not self.is_available():
            raise CircuitOpenError(f"Circuit {self._name} is open")

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            self._on_success()
            return result

        except Exception:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful operation."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            self._logger.debug(
                "circuit.success_in_half_open",
                circuit=self._name,
                success_count=self._success_count,
            )

            if self._success_count >= self._config.success_threshold:
                self._transition_to_closed()
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed operation."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        self._logger.warning(
            "circuit.failure",
            circuit=self._name,
            failure_count=self._failure_count,
            state=self._state.value,
        )

        if self._state == CircuitState.CLOSED:
            if self._failure_count >= self._config.failure_threshold:
                self._transition_to_open()
        elif self._state == CircuitState.HALF_OPEN:
            # Any failure in half-open goes back to open
            self._transition_to_open()

    def _transition_to_closed(self) -> None:
        """Transition to closed state."""
        old_state = self._state
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None

        self._logger.info(
            "circuit.state_transition",
            circuit=self._name,
            from_state=old_state.value,
            to_state=self._state.value,
        )

    def _transition_to_open(self) -> None:
        """Transition to open state."""
        old_state = self._state
        self._state = CircuitState.OPEN
        self._success_count = 0

        self._logger.warning(
            "circuit.state_transition",
            circuit=self._name,
            from_state=old_state.value,
            to_state=self._state.value,
            failure_count=self._failure_count,
        )

    def _transition_to_half_open(self) -> None:
        """Transition to half-open state."""
        old_state = self._state
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0

        self._logger.info(
            "circuit.state_transition",
            circuit=self._name,
            from_state=old_state.value,
            to_state=self._state.value,
        )

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self._name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
            "is_available": self.is_available(),
        }


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""


__all__ = ["CircuitState", "CircuitBreakerConfig", "CircuitBreaker", "CircuitOpenError"]
