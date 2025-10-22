---
title: Health Check Standards
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-20
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Operations ▸ Health Check Standards

# Health Check Standards

This document defines the standardized health check contract for all services in the Discord Voice Lab system.

## Endpoint Specifications

All services must implement two health check endpoints following Kubernetes best practices:

### GET /health/live

-  **Purpose**: Liveness probe - indicates if the process is running
-  **Response**: Always returns 200 if the process is alive
-  **Format**: Simple JSON with service identification

```json
{
  "status": "alive",
  "service": "service-name"
}
```

### GET /health/ready

-  **Purpose**: Readiness probe - indicates if the service can handle requests
-  **Response**:
  -  200 when service is ready to serve requests
  -  503 when service is not ready (startup incomplete or dependencies unavailable)
-  **Format**: Detailed JSON with component status and dependencies

## Response Format Requirements

### Ready Response (200)

```json
{
  "status": "ready|degraded|not_ready",
  "service": "service-name",
  "components": {
    "component_name": true|false,
    "startup_complete": true|false
  },
  "dependencies": {
    "dependency_name": true|false
  },
  "health_details": {
    "startup_complete": true|false,
    "dependencies": {
      "dependency_name": true|false
    }
  }
}
```

### Not Ready Response (503)

```json
{
  "detail": "Human-readable reason for not being ready"
}
```

## Status Values

-  **ready**: Service is fully operational and all dependencies are healthy
-  **degraded**: Service is operational but some dependencies are unhealthy
-  **not_ready**: Service cannot serve requests (startup incomplete or critical failures)

## Startup State Management Requirements

### Mandatory Implementation

All services must:

-  **Call `mark_startup_complete()`** after initialization is complete
-  **Register dependencies** using `_health_manager.register_dependency()`
-  **Handle startup failures gracefully** without crashing the service

### Implementation Pattern

```python
@app.on_event("startup")
async def _startup():
    try:
        # Initialize core components
        await _initialize_core_components()
        
        # Register dependencies
        _health_manager.register_dependency("dependency_name", _check_dependency_health)
        
        # Mark startup complete
        _health_manager.mark_startup_complete()
        
        logger.info("service.startup_complete", service=service_name)
    except Exception as exc:
        logger.error("service.startup_failed", error=str(exc))
        # Continue without crashing - service will report not_ready
```

## Dependency Registration Patterns

### Async Dependency Check

```python
async def _check_dependency_health() -> bool:
    """Check external service health."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/health/ready", timeout=5.0)
            return response.status_code == 200
    except Exception:
        return False

# Register the dependency
_health_manager.register_dependency("dependency_name", _check_dependency_health)
```

### Sync Dependency Check

```python
def _check_internal_component() -> bool:
    """Check internal component health."""
    return _component is not None and _component.is_healthy()

# Register the dependency
_health_manager.register_dependency("internal_component", _check_internal_component)
```

## Health Endpoint Implementation

### Standard Implementation Pattern

```python
@app.get("/health/ready")
async def health_ready() -> dict[str, Any]:
    """Readiness check - can serve requests."""
    if _critical_component is None:
        raise HTTPException(status_code=503, detail="Critical component not loaded")
    
    health_status = await _health_manager.get_health_status()
    
    # Determine status string
    if not health_status.ready:
        status_str = "degraded" if health_status.status == HealthStatus.DEGRADED else "not_ready"
    else:
        status_str = "ready"
    
    return {
        "status": status_str,
        "service": "service-name",
        "components": {
            "component_loaded": _critical_component is not None,
            "startup_complete": _health_manager._startup_complete,
            # Add service-specific components
        },
        "dependencies": health_status.details.get("dependencies", {}),
        "health_details": health_status.details
    }
```

## Metrics Requirements

All services expose the following Prometheus metrics for health checks:

### health_check_duration_seconds

-  **Type**: Histogram
-  **Description**: Health check execution duration
-  **Labels**: `service`, `check_type`
-  **Buckets**: Default Prometheus buckets

### service_health_status

-  **Type**: Gauge
-  **Description**: Current service health status
-  **Labels**: `service`, `component`
-  **Values**: 1=healthy, 0.5=degraded, 0=unhealthy

### service_dependency_health

-  **Type**: Gauge
-  **Description**: Dependency health status
-  **Labels**: `service`, `dependency`
-  **Values**: 1=healthy, 0=unhealthy

## Status Transitions

### Healthy → Degraded

-  Occurs when a non-critical dependency becomes unhealthy
-  Service continues to operate with reduced functionality
-  Health endpoint returns 200 with `"status": "degraded"`

### Degraded → Unhealthy

-  Occurs when a critical dependency becomes unhealthy
-  Service cannot serve requests
-  Health endpoint returns 503 with `"status": "not_ready"`

### Unhealthy → Healthy

-  Occurs when all dependencies become healthy
-  Service is fully operational
-  Health endpoint returns 200 with `"status": "ready"`

## Service-Specific Requirements

### STT Service

-  **Components**: `model_loaded`, `model_name`, `startup_complete`
-  **Dependencies**: None (standalone service)

### TTS Service

-  **Components**: `voice_loaded`, `sample_rate`, `max_concurrency`, `startup_complete`
-  **Dependencies**: None (standalone service)

### LLM Service

-  **Components**: `llm_loaded`, `tts_available`, `startup_complete`
-  **Dependencies**: `tts` (optional)

### Orchestrator Service

-  **Components**: `orchestrator_active`, `llm_available`, `tts_available`, `mcp_clients`, `startup_complete`
-  **Dependencies**: `llm`, `tts`

### Discord Service

-  **Components**: `bot_connected`, `mode`, `startup_complete`
-  **Dependencies**: `stt`, `orchestrator`

## Testing Requirements

### Unit Tests

-  Mock `_health_manager.get_health_status()` using `AsyncMock`
-  Validate response structure includes all required fields
-  Test both ready and not-ready scenarios

### Integration Tests

-  Validate health check response structure
-  Test dependency health tracking
-  Verify status transitions

### Health Check Validation

```python
def _validate_health_response(data: dict, service_name: str) -> bool:
    """Validate health check response structure."""
    required_fields = ["status", "service", "components", "health_details"]
    return (
        all(field in data for field in required_fields) and
        data["service"] == service_name and
        data["status"] in ["ready", "not_ready", "degraded"]
    )
```

## Monitoring and Alerting

### Key Metrics to Monitor

-  `service_health_status` - Overall service health
-  `service_dependency_health` - Dependency health
-  `health_check_duration_seconds` - Health check performance

### Alerting Rules

-  Alert when `service_health_status` drops below 1 (degraded/unhealthy)
-  Alert when `service_dependency_health` drops below 1 for critical dependencies
-  Alert when `health_check_duration_seconds` exceeds threshold

### Dashboard Queries

```promql
# Service health status
service_health_status{component="overall"}

# Dependency health
service_dependency_health

# Health check duration
histogram_quantile(0.95, health_check_duration_seconds_bucket)
```

## Migration Guide

### Breaking Changes

-  **Response Format**: Changed from simple fields to structured components
-  **Status Values**: Now supports "degraded" status
-  **Startup Behavior**: All services must call `mark_startup_complete()`
-  **Dependency Tracking**: Services must register dependencies
-  **Metrics**: New Prometheus metrics exposed

### Backward Compatibility

-  Old health check clients will need to be updated
-  Response format changes require client code updates
-  Status value changes may affect monitoring systems

## Examples

### Complete Health Check Response

```json
{
  "status": "ready",
  "service": "orchestrator",
  "components": {
    "orchestrator_active": true,
    "llm_available": true,
    "tts_available": true,
    "mcp_clients": {
      "file_tools": "connected",
      "web_search": "connected"
    },
    "startup_complete": true
  },
  "dependencies": {
    "llm": true,
    "tts": true
  },
  "health_details": {
    "startup_complete": true,
    "dependencies": {
      "llm": true,
      "tts": true
    }
  }
}
```

### Degraded Service Response

```json
{
  "status": "degraded",
  "service": "orchestrator",
  "components": {
    "orchestrator_active": true,
    "llm_available": true,
    "tts_available": false,
    "mcp_clients": {
      "file_tools": "connected",
      "web_search": "disconnected"
    },
    "startup_complete": true
  },
  "dependencies": {
    "llm": true,
    "tts": false
  },
  "health_details": {
    "startup_complete": true,
    "dependencies": {
      "llm": true,
      "tts": false
    }
  }
}
```
