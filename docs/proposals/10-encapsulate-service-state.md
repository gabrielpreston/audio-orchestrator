# Proposal: Encapsulate Service State

**Status: Complete (All Phases Complete - STT, Discord, Orchestrator, Guardrails Services)**

## Implementation Progress

### Phase 1: STT Service ✅ COMPLETE

**Completed:**

-  ✅ Updated `_startup()` to store state in `app.state` instead of module globals
-  ✅ Updated route handlers (`_transcribe_request`, `asr`, `transcribe`) to access state via `request.app.state`
-  ✅ Updated health endpoints to access `app.state` via lambda functions
-  ✅ Updated helper functions (`_enhance_audio_if_enabled`, `_lazy_load_model`) to accept `Request` and access `app.state`
-  ✅ Removed module-level globals (kept only `_health_manager` which is needed for app creation)
-  ✅ Fixed linting issues

**Remaining for Phase 1:**

-  ✅ Updated critical health endpoint tests to use `app.state`
-  ✅ All unit tests pass

### Phase 2: Discord Service ✅ COMPLETE

**Completed:**

-  ✅ Updated `_startup()` to store state in `app.state` instead of module globals
-  ✅ Updated `_start_discord_bot()` to accept app instance and store bot/bot_task in `app.state`
-  ✅ Updated route handlers (`send_message`, `handle_transcript`) to access state via `app.state`
-  ✅ Updated health endpoints to access `app.state` via lambda functions
-  ✅ Updated helper functions (`_check_stt_health`, `_check_orchestrator_health`, `_get_bot_status`) to access `app.state`
-  ✅ Updated `_shutdown()` to access state from `app.state`
-  ✅ Removed module-level globals (kept only `_health_manager` which is needed for app creation)
-  ✅ Fixed linting issues
-  ✅ All unit tests pass

**Remaining for Phase 2:**

-  ⏳ Additional test updates can be done incrementally as needed

### Phase 3: Orchestrator Service ✅ COMPLETE

**Completed:**

-  ✅ Updated `_startup()` to store state in `app.state` instead of module globals
-  ✅ Updated route handlers (`process_transcript`) to access state via `app.state`
-  ✅ Updated health endpoints to access `app.state` via lambda functions
-  ✅ Updated helper functions (`_check_llm_health`, `_check_tts_health`, `_check_guardrails_health`) to access `app.state`
-  ✅ Updated `_shutdown()` to access state from `app.state`
-  ✅ Removed module-level globals (kept only `_health_manager` which is needed for app creation)
-  ✅ Fixed linting issues (including mypy type annotations)
-  ✅ All unit tests pass

**Remaining for Phase 3:**

-  ⏳ Additional test updates can be done incrementally as needed

### Phase 4: Guardrails Service ✅ COMPLETE

**Completed:**

-  ✅ Updated `_startup()` to store state in `app.state` instead of module globals
-  ✅ Updated route handlers (`validate_input`, `validate_output`, `escalate_to_human`) to access state via `app.state`
-  ✅ Updated health endpoints to access `app.state` via lambda functions
-  ✅ Updated helper functions (`_load_toxicity_model`, `initialize_rate_limiter`) to use `app.state`
-  ✅ Updated all metrics, cache, and model loader references to use `app.state`
-  ✅ Removed module-level globals (kept only `_health_manager` which is needed for app creation)
-  ✅ Fixed linting issues (including mypy type annotations)
-  ✅ All unit tests pass

**Remaining for Phase 4:**

-  ⏳ Additional test updates can be done incrementally as needed

## Summary

-  Replace module-level global state in services (STT, discord, orchestrator, etc.) with FastAPI `app.state` and dependency injection.
-  Improve concurrency safety and testability by localizing mutable state.
-  **Note:** Audio service is excluded from this proposal as it will be deprecated per Proposal 15.

## Goals

-  Introduce a consistent pattern using FastAPI's built-in `app.state` and dependency injection (`Depends()`).
-  Ensure startup/shutdown logic is centralized and test-friendly.
-  Reduce reliance on mutable globals that complicate background tasks and parallel requests.
-  Leverage FastAPI idioms rather than creating custom abstractions.

## Non-Goals

-  Changing business logic of services (transcription, orchestration, etc.).
-  Re-architecting FastAPI applications beyond state management.
-  Implementing custom dependency injection frameworks.
-  Including audio service (deprecated per Proposal 15).

## Motivation

-  Global variables complicate unit testing and risk unintended cross-request interactions when multiple async tasks run concurrently.
-  Encapsulation enables clearer lifecycle management (startup/shutdown) and simplifies dependency injection.
-  FastAPI already provides excellent state management via `app.state` and dependency injection via `Depends()` — we should use these built-in patterns rather than creating new abstractions.

## Current State Analysis

### Existing Patterns

-  **Module-level globals**: All services use extensive module-level globals (e.g., `_model`, `_audio_processor_client`, `_health_manager`, `_observability_manager`, `_stt_metrics`).
-  **Lifespan management**: Services already use `create_service_app()` which provides lifespan context managers with startup/shutdown callbacks.
-  **State access**: Route handlers directly access module globals (e.g., `if not _audio: raise HTTPException(...)`).

### Issues Identified

1.  **Testing complexity**: Tests must manage module-level state, making parallel test execution risky.
2.  **Concurrency concerns**: Module globals can be accessed/modified by concurrent requests.
3.  **Initialization order**: Startup logic in callbacks modifies globals, creating implicit dependencies.
4.  **Over-engineering risk**: Original proposal suggested creating a new `ServiceContainer` abstraction when FastAPI already provides `app.state`.

## Proposed Solution: FastAPI Idiomatic Approach

Use FastAPI's built-in state management and dependency injection instead of creating custom containers:

### 1. Store State in `app.state`

During startup, store stateful components in `app.state` (already used for `app.state.http_metrics`):

```python
async def _startup() -> None:
    # Get observability manager
    _observability_manager = get_observability_manager("stt")

    # Initialize components
    _model_loader = BackgroundModelLoader(...)
    _audio_processor_client = STTAudioProcessorClient(...)

    # Store in app.state instead of module globals
    app.state.model_loader = _model_loader
    app.state.audio_processor_client = _audio_processor_client
    app.state.observability_manager = _observability_manager
    app.state.stt_metrics = _stt_metrics
```

### 2. Access State via Dependency Injection

Use FastAPI's `Depends()` for route handlers:

```python
from fastapi import Depends
from typing import Annotated

def get_model_loader(app: Request) -> BackgroundModelLoader:
    """Dependency to get model loader from app.state."""
    loader = app.app.state.model_loader
    if loader is None:
        raise HTTPException(status_code=503, detail="Model loader not initialized")
    return loader

@app.post("/transcribe")
async def transcribe(
    request: Request,
    model_loader: Annotated[BackgroundModelLoader, Depends(get_model_loader)],
) -> JSONResponse:
    # Use model_loader directly, no global access
    model = await model_loader.get_model()
    ...
```

### 3. Alternative: Direct `app.state` Access (Simpler)

For services with minimal state, direct access via `Request.app.state` is acceptable:

```python
@app.post("/transcribe")
async def transcribe(request: Request) -> JSONResponse:
    model_loader = request.app.state.model_loader
    if model_loader is None:
        raise HTTPException(status_code=503, detail="Model loader not initialized")
    model = await model_loader.get_model()
    ...
```

## Implementation Plan

### Phase 1: Pilot with STT Service (Highest Value)

**Confidence: 95%**

STT service has the most stateful components and will benefit most from encapsulation.

**Steps:**

1.  Update `services/stt/app.py`:

   -  Move globals (`_model_loader`, `_audio_processor_client`, `_transcript_cache`, `_stt_metrics`) to `app.state` during `_startup()`.
   -  Update route handlers to access state via `request.app.state` or `Depends()`.
   -  Remove module-level global assignments after startup.

2.  Update tests:

   -  Modify test fixtures to set `app.state.*` instead of patching module globals.
   -  Update `conftest.py` to initialize test app with proper state.

**Validation:**

-  All existing tests pass.
-  No regression in functionality.
-  Health checks continue to work.

### Phase 2: Discord Service

**Confidence: 90%**

Discord service has fewer stateful components but complex initialization.

**Steps:**

1.  Update `services/discord/app.py`:

   -  Move `_bot`, `_bot_task`, `_stt_health_client`, `_orchestrator_health_client` to `app.state`.
   -  Update route handlers and health checks to access state via `request.app.state`.

2.  Update `services/discord/discord_voice.py`:

   -  If needed, pass state via constructor instead of module globals.

**Validation:**

-  Discord bot connects successfully.
-  Health checks work.
-  HTTP API endpoints function correctly.

### Phase 3: Remaining Services (Orchestrator, Guardrails, etc.)

**Confidence: 85%**

Apply pattern to other services following the same approach.

**Steps:**

1.  For each service:

   -  Identify module-level globals.
   -  Move to `app.state` during startup.
   -  Update route handlers to access via `request.app.state` or `Depends()`.

2.  Document pattern in `services/common/README.md`.

**Validation:**

-  All services start successfully.
-  Integration tests pass.
-  No performance regressions.

## Over-Engineering Analysis

### Original Proposal Issues

1.  **Custom ServiceContainer abstraction**: Unnecessary when FastAPI provides `app.state`.
2.  **Additional abstraction layer**: Adds complexity without clear benefits.
3.  **Inconsistent with FastAPI patterns**: FastAPI apps use `app.state` for shared state.

### Simplified Approach

✅ **Use FastAPI built-ins:**

-  `app.state` for storing state (already used in codebase for `http_metrics`).
-  `Depends()` for dependency injection (optional, but idiomatic).
-  Lifespan callbacks for initialization (already in place).

✅ **Benefits:**

-  No new abstractions to learn or maintain.
-  Consistent with FastAPI best practices.
-  Leverages existing patterns in codebase.
-  Easier testing via `app.state` manipulation.

### Holistic Application

This approach can be applied consistently across all services:

1.  **Startup**: Store initialized components in `app.state` during lifespan startup.
2.  **Access**: Route handlers use `request.app.state.*` or `Depends()`.
3.  **Testing**: Test fixtures manipulate `app.state` directly.
4.  **Shutdown**: Cleanup components stored in `app.state` during lifespan shutdown.

## Dependencies and Conflicts

### Proposal 15 Conflict Resolution

**Issue:** Original proposal included audio service, but Proposal 15 plans to deprecate it.

**Resolution:** Exclude audio service from this proposal. Focus on services that will remain:

-  STT service
-  Discord service
-  Orchestrator service
-  Guardrails service
-  Other services as needed

### Coordination with Other Proposals

-  **Metrics/Health**: Already use module globals that should move to `app.state`.
-  **Model Loading**: `BackgroundModelLoader` instances should be in `app.state`.
-  **HTTP Clients**: Resilient HTTP clients for health checks should be in `app.state`.

## Risks & Mitigations

-  **Risk:** Refactor might introduce bugs if state access is inconsistent. *Mitigation:* Start with STT service (pilot), validate thoroughly, then roll out incrementally.

-  **Risk:** Performance impact of `request.app.state` access. *Mitigation:* `app.state` access is O(1) attribute lookup, negligible overhead. Benchmark if concerns arise.

-  **Risk:** Test fixtures need updates. *Mitigation:* Update fixtures incrementally, document pattern in `services/common/README.md`.

## Acceptance Criteria

-  ✅ Target services (STT, Discord, Orchestrator) no longer rely on mutable module-level globals for key components.
-  ✅ Startup/shutdown sequences are encapsulated in lifespan callbacks using `app.state`.
-  ✅ Route handlers access state via `request.app.state` or `Depends()`.
-  ✅ Integration tests pass, demonstrating unchanged runtime behavior.
-  ✅ Unit tests can manipulate `app.state` directly without module-level side effects.
-  ✅ Documentation in `services/common/README.md` outlines the `app.state` pattern.

## Testing Strategy

1.  **Unit Tests**: Update fixtures to set `app.state.*` instead of patching globals.
2.  **Integration Tests**: Verify services start correctly with new state management.
3.  **Concurrency Tests**: Ensure parallel requests don't interfere with each other.
4.  **Health Check Tests**: Verify health endpoints continue to work with `app.state`.

## Validation Section

After implementation, validate:

1.  **Functionality**: All services operate correctly with new state management.
2.  **Performance**: No regressions in request latency or throughput.
3.  **Tests**: All existing tests pass with updated fixtures.
4.  **Documentation**: Pattern is documented and examples provided.

## Implementation Notes

### FastAPI `app.state` Best Practices

-  Store initialized objects, not configuration (config remains in module-level constants).
-  Access via `request.app.state.key` in route handlers.
-  Use type hints for better IDE support: `loader: BackgroundModelLoader = request.app.state.model_loader`.
-  Consider `Depends()` for complex dependency graphs, but direct access is acceptable for simple cases.

### Migration Pattern

```python
# BEFORE: Module global
_model_loader: BackgroundModelLoader | None = None

async def _startup() -> None:
    global _model_loader
    _model_loader = BackgroundModelLoader(...)

@app.post("/transcribe")
async def transcribe(...):
    if _model_loader is None:
        raise HTTPException(...)
    model = await _model_loader.get_model()

# AFTER: app.state
async def _startup() -> None:
    app.state.model_loader = BackgroundModelLoader(...)

@app.post("/transcribe")
async def transcribe(request: Request):
    loader = request.app.state.model_loader
    if loader is None:
        raise HTTPException(...)
    model = await loader.get_model()
```

## Confidence Scores

| Phase | Component | Confidence | Risk | Notes |
|-------|-----------|------------|------|-------|
| 1 | STT Service Migration | 95% | Low | Most stateful, clear benefit |
| 2 | Discord Service Migration | 90% | Low | Fewer components, straightforward |
| 3 | Other Services | 85% | Medium | Variable complexity per service |
| Overall | Pattern Adoption | 90% | Low | Well-established FastAPI pattern |

## References

-  FastAPI State Management: <https://fastapi.tiangolo.com/advanced/application-state/>
-  FastAPI Dependency Injection: <https://fastapi.tiangolo.com/tutorial/dependencies/>
-  Proposal 15: Audio Service Deprecation Plan
