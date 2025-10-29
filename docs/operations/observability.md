---
title: Solo Observability Guide
author: Discord Voice Lab Team
status: active
last-updated: 2025-01-27
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Operations ▸ Solo Observability

# Solo Observability

This guide documents simplified logging and health check expectations for solo development.

## Logging

-  All Python services use `services.common.logging` to emit JSON-formatted logs.
-  Configure verbosity with `LOG_LEVEL` (`debug`, `info`, `warning`) in `.env.common`.
-  Toggle JSON output via `LOG_JSON`; switch to plain text when debugging locally.
-  Use `make logs SERVICE=<name>` to stream per-service output and correlate events across the stack.

## Simple Metrics (Optional)

-  Basic health checks are sufficient for solo development
-  No complex Prometheus metrics required
-  Focus on "does it work" over comprehensive monitoring

## Standardized Health Checks

All services now use the common health endpoints module for consistent health check implementation:

-  **GET /health/live**: Always returns 200 if process is alive
-  **GET /health/ready**: Returns detailed readiness status with component information
-  **GET /health/dependencies**: Returns dependency health status

### Common Health Check Implementation

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

All services return consistent health check responses:

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

### Basic Health Check Requirements

-  **Startup Management**: Track if service has completed initialization
-  **Basic Endpoints**: Implement `/health/live` and `/health/ready`
-  **Simple Status**: Return basic status information
-  **No Complex Metrics**: Keep it simple for solo development

## Solo Development Summary

### Simplified Approach

-  **Basic functionality**: Service can handle requests
-  **Simple implementation**: No complex metrics or extensive dependency checking
-  **Solo development**: Optimized for rapid iteration and manual testing
-  **Essential coverage**: Critical paths covered without over-engineering
