"""Tests for HealthManager startup failure tracking."""

import pytest

from services.common.health import HealthManager, HealthStatus


def test_record_startup_failure_critical():
    """Test recording a critical startup failure."""
    hm = HealthManager("test-service")
    error = ValueError("Critical initialization failed")

    hm.record_startup_failure(error, component="model_loader", is_critical=True)

    failure = hm.get_startup_failure()
    assert failure is not None
    assert failure["error"] == "Critical initialization failed"
    assert failure["error_type"] == "ValueError"
    assert failure["component"] == "model_loader"
    assert failure["is_critical"] is True
    assert "timestamp" in failure


def test_record_startup_failure_non_critical():
    """Test recording a non-critical startup failure."""
    hm = HealthManager("test-service")
    error = RuntimeError("Optional component failed")

    hm.record_startup_failure(error, component="optional_feature", is_critical=False)

    failure = hm.get_startup_failure()
    assert failure is not None
    assert failure["is_critical"] is False


def test_has_startup_failure():
    """Test has_startup_failure() method."""
    hm = HealthManager("test-service")

    # Initially no failure
    assert hm.has_startup_failure() is False

    # Critical failure
    hm.record_startup_failure(ValueError("error"), is_critical=True)
    assert hm.has_startup_failure() is True

    # Non-critical failure should not be considered
    hm2 = HealthManager("test-service-2")
    hm2.record_startup_failure(ValueError("error"), is_critical=False)
    assert hm2.has_startup_failure() is False


def test_mark_startup_complete_blocked_by_critical_failure():
    """Test that mark_startup_complete() is blocked when critical failure exists."""
    hm = HealthManager("test-service")
    error = ValueError("Critical failure")

    # Record critical failure
    hm.record_startup_failure(error, component="critical", is_critical=True)

    # Try to mark startup complete - should be blocked
    hm.mark_startup_complete()
    assert hm._startup_complete is False


def test_mark_startup_complete_allowed_with_non_critical_failure():
    """Test that mark_startup_complete() succeeds with non-critical failure."""
    hm = HealthManager("test-service")
    error = ValueError("Optional failure")

    # Record non-critical failure
    hm.record_startup_failure(error, component="optional", is_critical=False)

    # Mark startup complete should succeed
    hm.mark_startup_complete()
    assert hm._startup_complete is True


def test_mark_startup_complete_allowed_without_failure():
    """Test that mark_startup_complete() succeeds when no failure exists."""
    hm = HealthManager("test-service")

    # No failure recorded, should succeed
    hm.mark_startup_complete()
    assert hm._startup_complete is True


@pytest.mark.asyncio
async def test_get_health_status_with_startup_failure():
    """Test get_health_status() returns startup_failed when critical failure exists."""
    hm = HealthManager("test-service")
    error = ValueError("Startup failed")

    # Record critical failure
    hm.record_startup_failure(error, component="initialization", is_critical=True)

    # Get health status
    status = await hm.get_health_status()

    assert status.status == HealthStatus.UNHEALTHY
    assert status.ready is False
    assert status.details["reason"] == "startup_failed"
    assert "startup_failure" in status.details
    assert status.details["startup_failure"]["component"] == "initialization"
    assert status.details["startup_failure"]["error_type"] == "ValueError"


@pytest.mark.asyncio
async def test_get_health_status_without_startup_complete():
    """Test get_health_status() returns startup_not_complete when startup not done."""
    hm = HealthManager("test-service")

    # Don't mark startup complete, don't record failure
    status = await hm.get_health_status()

    assert status.status == HealthStatus.UNHEALTHY
    assert status.ready is False
    assert status.details["reason"] == "startup_not_complete"


@pytest.mark.asyncio
async def test_check_ready_with_startup_failure():
    """Test check_ready() returns False when critical startup failure exists."""
    hm = HealthManager("test-service")
    error = ValueError("Critical failure")

    # Record critical failure
    hm.record_startup_failure(error, is_critical=True)

    # Try to mark complete (should be blocked)
    hm.mark_startup_complete()

    # check_ready should return False even if we tried to mark complete
    ready = await hm.check_ready()
    assert ready is False


@pytest.mark.asyncio
async def test_check_ready_with_non_critical_failure():
    """Test check_ready() returns True when only non-critical failure exists."""
    hm = HealthManager("test-service")
    error = ValueError("Optional failure")

    # Record non-critical failure
    hm.record_startup_failure(error, is_critical=False)

    # Mark startup complete should succeed
    hm.mark_startup_complete()

    # check_ready should return True (no dependencies registered)
    ready = await hm.check_ready()
    assert ready is True
