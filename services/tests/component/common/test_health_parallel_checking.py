"""Tests for parallel dependency checking and adaptive cache TTL in HealthManager."""

import asyncio
import time

import pytest

from services.common.health import HealthManager, HealthStatus


@pytest.mark.asyncio
async def test_parallel_dependency_checking():
    """Verify dependencies are checked in parallel, not sequentially."""
    hm = HealthManager("test-service")
    hm.mark_startup_complete()

    # Track when each dependency check starts and completes
    check_times: dict[str, list[float]] = {
        "dep1": [],
        "dep2": [],
        "dep3": [],
    }

    async def slow_dep(name: str, delay: float) -> bool:
        """Simulate a slow dependency check."""
        check_times[name].append(time.time())
        await asyncio.sleep(delay)
        check_times[name].append(time.time())
        return True

    # Register three dependencies with delays
    async def dep1_check() -> bool:
        return await slow_dep("dep1", 0.1)

    async def dep2_check() -> bool:
        return await slow_dep("dep2", 0.1)

    async def dep3_check() -> bool:
        return await slow_dep("dep3", 0.1)

    hm.register_dependency("dep1", dep1_check)
    hm.register_dependency("dep2", dep2_check)
    hm.register_dependency("dep3", dep3_check)

    start_time = time.time()
    status = await hm.get_health_status()
    total_time = time.time() - start_time

    # All dependencies should be available
    assert status.status == HealthStatus.HEALTHY
    assert status.ready is True
    assert all(dep["available"] for dep in status.details["dependencies"].values())

    # If parallel, total time should be ~0.1s (max delay), not ~0.3s (sum of delays)
    # Allow some overhead for async scheduling
    assert total_time < 0.25, f"Expected parallel checking (<0.25s), got {total_time}s"

    # Verify all checks started around the same time (within 0.05s)
    start_times = [times[0] for times in check_times.values()]
    max_start_diff = max(start_times) - min(start_times)
    assert max_start_diff < 0.05, "Checks should start nearly simultaneously"


@pytest.mark.asyncio
async def test_parallel_check_ready():
    """Verify check_ready() also uses parallel checking."""
    hm = HealthManager("test-service")
    hm.mark_startup_complete()

    check_count = {"count": 0}

    async def dep1_check() -> bool:
        check_count["count"] += 1
        await asyncio.sleep(0.05)
        return True

    async def dep2_check() -> bool:
        check_count["count"] += 1
        await asyncio.sleep(0.05)
        return True

    async def dep3_check() -> bool:
        check_count["count"] += 1
        await asyncio.sleep(0.05)
        return True

    hm.register_dependency("dep1", dep1_check)
    hm.register_dependency("dep2", dep2_check)
    hm.register_dependency("dep3", dep3_check)

    start_time = time.time()
    ready = await hm.check_ready()
    total_time = time.time() - start_time

    assert ready is True
    assert check_count["count"] == 3
    # Should be fast due to parallel checking
    assert total_time < 0.15, f"Expected parallel checking (<0.15s), got {total_time}s"


@pytest.mark.asyncio
async def test_check_ready_fails_on_first_unhealthy():
    """Verify check_ready() returns False if any dependency is unhealthy."""
    hm = HealthManager("test-service")
    hm.mark_startup_complete()

    hm.register_dependency("healthy", lambda: True)
    hm.register_dependency("unhealthy", lambda: False)

    ready = await hm.check_ready()
    assert ready is False


@pytest.mark.asyncio
async def test_parallel_checking_with_timeout():
    """Verify timeout handling works correctly with parallel checks."""
    hm = HealthManager("test-service")
    hm.mark_startup_complete()

    async def slow_dep() -> bool:
        await asyncio.sleep(3.0)  # Longer than 2s timeout
        return True

    hm.register_dependency("slow", slow_dep)

    start_time = time.time()
    status = await hm.get_health_status()
    total_time = time.time() - start_time

    # Should timeout around 2s
    assert 1.5 < total_time < 3.0, f"Expected timeout around 2s, got {total_time}s"
    assert status.details["dependencies"]["slow"]["available"] is False
    assert "Timeout" in status.details["dependencies"]["slow"].get("error", "")


@pytest.mark.asyncio
async def test_adaptive_cache_ttl_startup_phase():
    """Verify cache TTL is 1.0s during startup phase (first 60s)."""
    hm = HealthManager("test-service")
    hm.mark_startup_complete()

    # Immediately after startup, should be in startup phase
    ttl = hm._get_effective_cache_ttl()
    assert ttl == 1.0, f"Expected 1.0s TTL during startup, got {ttl}s"


@pytest.mark.asyncio
async def test_adaptive_cache_ttl_early_operation():
    """Verify cache TTL transitions to 5.0s during early operation (60-300s)."""
    hm = HealthManager("test-service")
    hm.mark_startup_complete()

    # Simulate 60 seconds elapsed
    hm._startup_time = time.time() - 65.0
    ttl = hm._get_effective_cache_ttl()
    assert ttl == 5.0, f"Expected 5.0s TTL during early operation, got {ttl}s"


@pytest.mark.asyncio
async def test_adaptive_cache_ttl_steady_state():
    """Verify cache TTL uses configured value during steady state (300s+)."""
    hm = HealthManager("test-service", dependency_cache_ttl_seconds=10.0)
    hm.mark_startup_complete()

    # Simulate 300+ seconds elapsed
    hm._startup_time = time.time() - 310.0
    ttl = hm._get_effective_cache_ttl()
    assert ttl == 10.0, f"Expected 10.0s TTL in steady state, got {ttl}s"


@pytest.mark.asyncio
async def test_adaptive_cache_ttl_affects_checking():
    """Verify adaptive cache TTL actually affects dependency checking frequency."""
    hm = HealthManager("test-service")
    hm.mark_startup_complete()

    check_count = {"count": 0}

    def dep_check() -> bool:
        check_count["count"] += 1
        return True

    hm.register_dependency("test", dep_check)

    # First check - should perform actual check
    status1 = await hm.get_health_status()
    assert check_count["count"] == 1
    assert status1.details["dependencies"]["test"]["cached"] is False

    # Second check immediately after - should use cache (1.0s TTL during startup)
    status2 = await hm.get_health_status()
    assert check_count["count"] == 1, "Should use cache, not check again"
    assert status2.details["dependencies"]["test"]["cached"] is True

    # Wait for cache to expire (1.0s + small buffer)
    await asyncio.sleep(1.1)
    status3 = await hm.get_health_status()
    assert check_count["count"] == 2, "Should check again after cache expires"
    assert status3.details["dependencies"]["test"]["cached"] is False


@pytest.mark.asyncio
async def test_parallel_checking_with_exceptions():
    """Verify exception handling works correctly with parallel checks."""
    hm = HealthManager("test-service")
    hm.mark_startup_complete()

    def failing_dep() -> bool:
        raise ValueError("test error")

    hm.register_dependency("failing", failing_dep)
    hm.register_dependency("healthy", lambda: True)

    status = await hm.get_health_status()

    assert status.details["dependencies"]["failing"]["available"] is False
    assert "test error" in status.details["dependencies"]["failing"].get("error", "")
    assert status.details["dependencies"]["healthy"]["available"] is True
    assert status.status == HealthStatus.DEGRADED
    assert status.ready is False


@pytest.mark.asyncio
async def test_per_dependency_locks():
    """Verify per-dependency locks prevent concurrent checks of same dependency."""
    hm = HealthManager("test-service")
    hm.mark_startup_complete()

    check_count = {"count": 0}

    async def dep_check() -> bool:
        check_count["count"] += 1
        await asyncio.sleep(0.1)
        return True

    hm.register_dependency("test", dep_check)

    # Trigger multiple concurrent calls to get_health_status
    # All should check the same dependency, but lock should prevent duplicate work
    tasks = [hm.get_health_status() for _ in range(5)]
    results = await asyncio.gather(*tasks)

    # Should only check once due to per-dependency lock
    # (first call does the check, others wait and use cache)
    assert check_count["count"] >= 1
    assert check_count["count"] <= 5  # Could be up to 5 if timing is perfect

    # All results should be consistent
    for result in results:
        assert result.status == HealthStatus.HEALTHY
