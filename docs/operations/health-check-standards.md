---
title: Health Check Standards
author: Discord Voice Lab Team
status: active
last-updated: 2025-01-27
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Operations ▸ Health Check Standards

# Health Check Standards

This document defines the standardized health check implementation using the common health endpoints module across all services in the Discord Voice Lab system.

## Common Health Endpoints Module

All services now use the standardized `HealthEndpoints` class from `services.common.health_endpoints` to implement consistent health check endpoints.

### Standardized Health Endpoints

-  **GET /health/live**: Always returns 200 if process is alive
-  **GET /health/ready**: Returns detailed readiness status with component information
-  **GET /health/dependencies**: Returns dependency health status

### Common Module Implementation

```python
from services.common.health_endpoints import HealthEndpoints
from services.common.health import HealthManager

# Initialize health manager
_health_manager = HealthManager("service_name")

# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="service_name",
    health_manager=_health_manager,
    custom_components={
        "component_name": lambda: component_value,
        "another_component": lambda: another_value,
    },
    custom_dependencies={
        "dependency_name": dependency_check_function,
    }
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())
```

### Standardized Response Formats

#### `/health/live` Response

```json
{
    "status": "alive",
    "service": "service_name"
}
```

#### `/health/ready` Response

```json
{
    "status": "ready|degraded|not_ready",
    "service": "service_name",
    "components": {
        "startup_complete": true,
        "component_name": true,
        "another_component": false
    },
    "dependencies": {
        "dependency_name": {
            "status": "healthy|unhealthy|error",
            "available": true
        }
    },
    "health_details": {
        "startup_complete": true,
        "dependencies": {}
    }
}
```

#### `/health/dependencies` Response

```json
{
    "service": "service_name",
    "dependencies": {
        "dependency_name": {
            "status": "healthy|unhealthy|error",
            "available": true,
            "error": "error_message_if_error"
        }
    },
    "startup_complete": true
}
```

## Service-Specific Health Check Examples

### Discord Service Health

```python
# services/discord/app.py
from services.common.health_endpoints import HealthEndpoints

# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="discord",
    health_manager=_health_manager,
    custom_components={
        "bot_connected": lambda: _bot is not None,
        "mode": "http",
    },
    custom_dependencies={
        "stt": _check_stt_health,
        "orchestrator": _check_orchestrator_health,
    }
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())
```

### STT Service Health

```python
# services/stt/app.py
from services.common.health_endpoints import HealthEndpoints

# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="stt",
    health_manager=_health_manager,
    custom_components={
        "model_loaded": lambda: _model is not None,
        "model_name": lambda: MODEL_NAME,
        "enhancer_loaded": lambda: _audio_enhancer is not None,
        "enhancer_enabled": lambda: (
            _audio_enhancer.is_enhancement_enabled if _audio_enhancer else False
        ),
        "audio_processor_client_loaded": lambda: _audio_processor_client is not None,
    },
    custom_dependencies={
        "audio_processor": lambda: _audio_processor_client is not None,
    }
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())
```

### Audio Service Health

```python
# services/audio/app.py
from services.common.health_endpoints import HealthEndpoints

# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="audio",
    health_manager=_health_manager,
    custom_components={
        "processor_loaded": lambda: _audio is not None,
        "enhancer_loaded": lambda: _audio_enhancer is not None,
        "enhancer_enabled": lambda: (
            _audio_enhancer.is_enhancement_enabled if _audio_enhancer else False
        ),
    }
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())
```

## Health Check Requirements

### Standardized Implementation

-  **Common Module**: All services use `HealthEndpoints` from `services.common.health_endpoints`
-  **Standardized Endpoints**: Implement `/health/live`, `/health/ready`, and `/health/dependencies`
-  **Consistent Responses**: All services return standardized response formats
-  **Component Tracking**: Track service-specific components and dependencies
-  **Startup Management**: Properly track startup completion state

### Health Check Testing

```python
def test_health_live_endpoint():
    """Test liveness endpoint returns 200."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"
    assert response.json()["service"] == "service_name"

def test_health_ready_endpoint():
    """Test readiness endpoint returns correct status."""
    response = client.get("/health/ready")
    if response.status_code == 200:
        data = response.json()
        assert "status" in data
        assert "service" in data
        assert "components" in data
        assert "dependencies" in data
    else:
        # Service not ready - this is expected behavior
        assert response.status_code == 503

def test_health_dependencies_endpoint():
    """Test dependencies endpoint returns dependency status."""
    response = client.get("/health/dependencies")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "dependencies" in data
    assert "startup_complete" in data
```

## Benefits of Common Module Approach

### Consistency

-  **Standardized Responses**: All services return identical response formats
-  **Unified Implementation**: Single source of truth for health endpoint logic
-  **Easier Debugging**: Consistent health check patterns across all services

### Maintainability

-  **Code Reusability**: Common module eliminates duplication across 9 services
-  **Centralized Updates**: Health endpoint changes only need to be made in one place
-  **Type Safety**: Consistent typing and validation across all services

### Reliability

-  **Graceful Degradation**: Services handle dependency failures gracefully
-  **Startup Independence**: Services can start without waiting for Docker health checks
-  **Better CI Performance**: No health check timeouts in CI environment

## Summary

The common health endpoints module provides:

-  **Standardized Implementation**: Consistent health check patterns across all services
-  **Code Reusability**: Single module eliminates duplication across 9 services
-  **Better Reliability**: Graceful handling of dependency failures and startup independence
-  **Easier Maintenance**: Centralized health endpoint logic with consistent response formats
