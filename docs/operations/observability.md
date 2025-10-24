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

## Simple Health Checks

Each service implements basic health check endpoints for solo development:

-  **GET /health/live**: Always returns 200 if process is alive
-  **GET /health/ready**: Returns basic status if service can handle requests

### Simple Health Check Implementation

```python
from fastapi import FastAPI, HTTPException
from typing import Dict, Any

app = FastAPI()

# Simple startup tracking
_startup_complete = False

@app.on_event("startup")
async def _startup():
    """Service startup event handler."""
    global _startup_complete
    try:
        # Initialize core components
        await _initialize_core_components()
        _startup_complete = True
    except Exception as exc:
        # Continue without crashing - service will report not_ready
        pass

@app.get("/health/live")
async def health_live():
    """Liveness check - always returns 200 if process is alive."""
    return {"status": "alive", "service": "discord"}

@app.get("/health/ready")
async def health_ready() -> Dict[str, Any]:
    """Readiness check - basic functionality."""
    if not _startup_complete:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    return {
        "status": "ready",
        "service": "discord",
        "startup_complete": _startup_complete
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
