# Proposal: Encapsulate Service State

## Summary

-  Replace module-level global state in services (e.g., audio, STT, discord) with encapsulated objects or FastAPI lifespan managers.
-  Improve concurrency safety and testability by localizing mutable state.

## Goals

-  Introduce a consistent pattern (service container or lifespan manager) for managing per-service state.
-  Ensure startup/shutdown logic is centralized and test-friendly.
-  Reduce reliance on mutable globals that complicate background tasks and parallel requests.

## Non-Goals

-  Changing business logic of services (audio processing, transcription, etc.).
-  Re-architecting FastAPI applications beyond state management.
-  Implementing dependency injection frameworks beyond lightweight helpers.

## Motivation

-  Global variables complicate unit testing and risk unintended cross-request interactions when multiple async tasks run concurrently.
-  Encapsulation enables clearer lifecycle management (startup/shutdown) and simplifies dependency injection.

## Proposed Changes

-  Introduce lightweight service containers that hold stateful components (processors, clients, metrics) and expose accessors to route handlers.
-  Use FastAPI `lifespan` context or dependency injection to manage initialization and cleanup instead of manual globals.
-  Update affected services to retrieve the container via dependency injection rather than referencing module globals directly.
-  Adjust tests to instantiate containers explicitly, reducing reliance on implicit module initialization.

### Implementation Outline

1.  Design a reusable `ServiceContainer` interface capturing startup, shutdown, and access methods.
2.  For each service (audio, STT, discord), implement a container that owns stateful resources (processors, clients, metrics).
3.  Replace module-level globals with container instances managed via FastAPI lifespan functions or dependencies.
4.  Update route handlers to acquire required components from container (e.g., dependency injection or request state).
5.  Adjust unit tests to instantiate containers directly, allowing deterministic setup/teardown.

## Acceptance Criteria

-  Target services no longer rely on mutable module-level globals for key components.
-  Startup/shutdown sequences are encapsulated and unit-testable.
-  Integration tests pass, demonstrating unchanged runtime behavior.
-  Documentation (README or service-specific notes) outlines the container pattern for contributors.

## Dependencies

-  Coordination with other proposals modifying startup logic (metrics, health clients) to avoid conflicts.
-  FastAPI support for lifespan hooks (already available).

## Risks & Mitigations

-  **Risk:** Refactor might introduce circular dependencies or initialization order issues. *Mitigation:* Start with one service (pilot) and document pattern before broad rollout.
-  **Risk:** Increased abstraction could confuse contributors. *Mitigation:* Provide clear examples and templates.

## Rollout Plan

-  Week 1: Pilot container pattern in one service (e.g., audio) and validate via tests.
-  Week 2: Extend to remaining services (STT, discord) and update documentation.
-  Week 3: Gather feedback, refine pattern, and ensure cross-service consistency.

## Testing Strategy

-  Add unit tests covering container initialization, ensuring state is correctly reset between tests.
-  Run service integration tests to confirm startup/shutdown behavior remains intact.
-  Perform manual smoke tests to ensure handlers operate correctly when multiple requests run in parallel.

## Open Questions

-  Should we standardize on a shared container pattern across all services or allow service-specific implementations?
-  Do we need helper utilities in `services.common` to simplify container creation and reuse?
