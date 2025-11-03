"""Tests for health endpoints startup failure handling."""

import pytest
from fastapi import HTTPException

from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints


@pytest.mark.asyncio
async def test_health_ready_returns_503_on_startup_failure():
    """Test /health/ready returns 503 with startup failure details."""
    hm = HealthManager("test-service")
    error = ValueError("Model loading failed")

    # Record critical startup failure
    hm.record_startup_failure(error, component="model_loader", is_critical=True)

    endpoints = HealthEndpoints(service_name="test-service", health_manager=hm)

    # health_ready should raise HTTPException with 503
    with pytest.raises(HTTPException) as exc_info:
        await endpoints.health_ready()

    assert exc_info.value.status_code == 503
    assert "startup failed" in exc_info.value.detail.lower()
    assert "model_loader" in exc_info.value.detail
    assert "ValueError" in exc_info.value.detail


@pytest.mark.asyncio
async def test_health_ready_distinguishes_startup_failed_from_in_progress():
    """Test /health/ready distinguishes startup failed from startup in progress."""
    hm = HealthManager("test-service")

    # Case 1: Startup not complete (no failure)
    endpoints1 = HealthEndpoints(service_name="test-service", health_manager=hm)
    with pytest.raises(HTTPException) as exc_info:
        await endpoints1.health_ready()
    assert exc_info.value.status_code == 503
    assert "startup in progress" in exc_info.value.detail.lower()

    # Case 2: Startup failed (with failure)
    error = RuntimeError("Initialization error")
    hm.record_startup_failure(error, component="config", is_critical=True)
    endpoints2 = HealthEndpoints(service_name="test-service", health_manager=hm)
    with pytest.raises(HTTPException) as exc_info2:
        await endpoints2.health_ready()
    assert exc_info2.value.status_code == 503
    assert "startup failed" in exc_info2.value.detail.lower()
    assert "config" in exc_info2.value.detail


@pytest.mark.asyncio
async def test_health_ready_error_message_sanitization():
    """Test that error messages are sanitized (truncated) in health responses."""
    hm = HealthManager("test-service")

    # Create a very long error message
    long_error_msg = "A" * 500
    error = ValueError(long_error_msg)

    hm.record_startup_failure(error, component="component", is_critical=True)

    endpoints = HealthEndpoints(service_name="test-service", health_manager=hm)

    with pytest.raises(HTTPException) as exc_info:
        await endpoints.health_ready()

    # Error message should be truncated (we truncate to 200 chars in detail message)
    # The detail should not contain the full error message
    detail = exc_info.value.detail
    assert len(detail) < 500  # Should be much shorter after truncation
    assert "component" in detail
    assert "ValueError" in detail


@pytest.mark.asyncio
async def test_health_ready_succeeds_with_non_critical_failure():
    """Test /health/ready succeeds when only non-critical failure exists."""
    hm = HealthManager("test-service")
    error = ValueError("Optional component failed")

    # Record non-critical failure
    hm.record_startup_failure(error, component="optional", is_critical=False)

    # Mark startup complete (should succeed)
    hm.mark_startup_complete()

    endpoints = HealthEndpoints(service_name="test-service", health_manager=hm)

    # health_ready should succeed (return 200)
    response = await endpoints.health_ready()
    assert response["status"] == "ready"
    assert response["service"] == "test-service"
