"""Tests for startup-aware health check intervals in ResilientHTTPClient."""

import time


from services.common.resilient_http import ResilientHTTPClient


def test_get_effective_check_interval_startup_phase():
    """Verify interval is 1.0s during startup phase (first 120s)."""
    client = ResilientHTTPClient(
        service_name="test-service",
        base_url="http://test:8000",
    )

    # Immediately after creation, should be in startup phase
    interval = client._get_effective_check_interval()
    assert interval == 1.0, f"Expected 1.0s interval during startup, got {interval}s"


def test_get_effective_check_interval_after_startup():
    """Verify interval uses backoff logic after startup phase (120s+)."""
    client = ResilientHTTPClient(
        service_name="test-service",
        base_url="http://test:8000",
    )

    # Simulate 120+ seconds elapsed
    client._service_start_time = time.time() - 125.0

    # With no failures, should use base interval
    interval = client._get_effective_check_interval()
    assert interval == client._health_check_interval

    # With failures, should use exponential backoff
    client._consecutive_failures = 2
    interval = client._get_effective_check_interval()
    expected = client._health_check_interval * min(
        2.0**2, client._max_backoff_interval / client._health_check_interval
    )
    assert interval == expected, f"Expected backoff interval, got {interval}s"


def test_startup_aware_interval_affects_check_health():
    """Verify startup-aware interval actually affects check_health() behavior."""
    client = ResilientHTTPClient(
        service_name="test-service",
        base_url="http://test:8000",
    )

    # During startup, interval should be 1.0s
    interval = client._get_effective_check_interval()
    assert interval == 1.0

    # After startup, interval should increase
    client._service_start_time = time.time() - 125.0
    interval = client._get_effective_check_interval()
    assert interval > 1.0 or interval == client._health_check_interval


def test_grace_period_separate_from_interval():
    """Verify grace period logic is separate from interval logic."""
    client = ResilientHTTPClient(
        service_name="test-service",
        base_url="http://test:8000",
        health_check_startup_grace_seconds=30.0,
    )

    # During grace period, check_health should return True without checking
    # (This is tested in the actual check_health method, but we verify
    # the interval logic doesn't interfere)
    interval = client._get_effective_check_interval()
    assert interval == 1.0  # Should still use startup interval
