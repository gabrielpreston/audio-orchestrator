---
title: Health Check Standards
author: Discord Voice Lab Team
status: active
last-updated: 2025-01-27
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Operations ▸ Health Check Standards

# Solo Health Check Standards

This document defines simplified health check standards for solo development in the Discord Voice Lab system.

## Basic Health Check Standards

All services must implement simple health checks for solo development:

### Basic Health Endpoints

-  **GET /health/live**: Always returns 200 if process is alive
-  **GET /health/ready**: Returns basic status if service can handle requests

### Simple Implementation

-  **Basic functionality**: Service can handle requests
-  **No complex metrics**: Keep it simple
-  **No extensive dependency checking**: Focus on core functionality

## Simple Implementation Pattern

### Basic Health Check Implementation

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

### Optional Dependency Health Checks

```python
async def _check_stt_service() -> bool:
    """Check STT service health (optional)."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get("http://stt:9000/health/ready")
            return response.status_code == 200
    except Exception:
        return False

async def _check_orchestrator() -> bool:
    """Check orchestrator service health (optional)."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get("http://orchestrator:8200/health/ready")
            return response.status_code == 200
    except Exception:
        return False
```

## Simple Health Check Best Practices

### Basic Health Check Requirements

-  **Startup Management**: Track if service has completed initialization
-  **Basic Endpoints**: Implement `/health/live` and `/health/ready`
-  **Simple Status**: Return basic status information
-  **No Complex Metrics**: Keep it simple for solo development

## Service-Specific Health Checks (Simplified)

### Discord Service Health

```python
# services/discord/health.py
class DiscordHealthManager:
    """Discord service specific health management."""
    
    def __init__(self):
        self._discord_connected = False
        self._voice_channel_ready = False
    
    def set_discord_connected(self, connected: bool):
        """Set Discord connection status."""
        self._discord_connected = connected
    
    def set_voice_channel_ready(self, ready: bool):
        """Set voice channel readiness."""
        self._voice_channel_ready = ready
```

### STT Service Health

```python
# services/stt/health.py
class STTHealthManager:
    """STT service specific health management."""
    
    def __init__(self):
        self._model_loaded = False
        self._processor_ready = False
    
    def set_model_loaded(self, loaded: bool):
        """Set model loaded status."""
        self._model_loaded = loaded
    
    def set_processor_ready(self, ready: bool):
        """Set processor readiness."""
        self._processor_ready = ready
```

## Quality Gates (Simplified)

### Health Check Requirements

-  **Basic Endpoints**: Implement `/health/live` and `/health/ready`
-  **Startup Tracking**: Track if service has completed initialization
-  **Simple Status**: Return basic status information
-  **No Complex Metrics**: Keep it simple for solo development

## Simple Testing Requirements

### Basic Health Check Tests

```python
def test_health_live_endpoint():
    """Test liveness endpoint returns 200."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"

def test_health_ready_endpoint():
    """Test readiness endpoint returns 200 when ready."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
```

## Solo Development Notes

### Simplified Approach

-  **No Complex Metrics**: Keep it simple for solo development
-  **Basic Functionality**: Focus on "does it work" over comprehensive monitoring
-  **Manual Testing**: Use manual testing for rapid iteration
-  **Essential Coverage**: Critical paths covered only

## Summary

This simplified health check approach focuses on:

-  **Basic functionality**: Service can handle requests
-  **Simple implementation**: No complex metrics or extensive dependency checking
-  **Solo development**: Optimized for rapid iteration and manual testing
-  **Essential coverage**: Critical paths covered without over-engineering
