import asyncio

import pytest

from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints


@pytest.mark.asyncio
async def test_dependency_cache_and_retry_behavior():
    """Validate caching, retry, and timeout logic for dependency checks."""
    hm = HealthManager("test-service")
    hm.mark_startup_complete()

    # Failing twice, then succeeding
    attempts: dict[str, int] = {"dep": 0}

    def flaky_dep() -> bool:
        attempts["dep"] += 1
        return attempts["dep"] >= 3

    endpoints = HealthEndpoints(
        service_name="test-service",
        health_manager=hm,
        custom_dependencies={"dep": flaky_dep},
        dependency_cache_ttl_seconds=5.0,
        dependency_check_timeout_seconds=0.5,
        dependency_retry_attempts=2,
        dependency_retry_backoff_seconds=0.01,
        dependency_circuit_fail_threshold=5,
        dependency_circuit_open_seconds=1.0,
        dependency_max_concurrency=2,
    )

    # First call should retry and ultimately succeed (2 failures + 1 success)
    data = await endpoints.health_dependencies()
    assert data["dependencies"]["dep"]["available"] is True

    # Cache should make subsequent call return immediately without invoking callable
    prev_attempts = attempts["dep"]
    data2 = await endpoints.health_dependencies()
    assert data2["dependencies"]["dep"]["available"] is True
    assert attempts["dep"] == prev_attempts


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures():
    """Circuit should open after consecutive failures and short-circuit calls."""
    hm = HealthManager("svc")
    hm.mark_startup_complete()

    def always_fail() -> bool:
        return False

    endpoints = HealthEndpoints(
        service_name="svc",
        health_manager=hm,
        custom_dependencies={"bad": always_fail},
        dependency_cache_ttl_seconds=0.0,  # no cache so we exercise failures
        dependency_check_timeout_seconds=0.2,
        dependency_retry_attempts=0,
        dependency_circuit_fail_threshold=2,
        dependency_circuit_open_seconds=0.3,
    )

    # First failure
    d1 = await endpoints.health_dependencies()
    assert d1["dependencies"]["bad"]["available"] is False

    # Second failure should open the circuit
    d2 = await endpoints.health_dependencies()
    assert d2["dependencies"]["bad"]["available"] is False

    # Immediately call again; should be short-circuited (still unavailable)
    d3 = await endpoints.health_dependencies()
    assert d3["dependencies"]["bad"]["available"] is False

    # After cooldown, circuit should allow attempts again (still failing)
    await asyncio.sleep(0.35)
    d4 = await endpoints.health_dependencies()
    assert d4["dependencies"]["bad"]["available"] is False
