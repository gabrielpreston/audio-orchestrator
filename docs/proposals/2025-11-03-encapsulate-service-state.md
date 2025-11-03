# Proposal: Encapsulate Service State

## Summary
- Replace module-level global state in services (e.g., audio, STT, discord) with encapsulated objects or FastAPI lifespan managers.
- Improve concurrency safety and testability by localizing mutable state.

## Motivation
- Global variables complicate unit testing and risk unintended cross-request interactions when multiple async tasks run concurrently.
- Encapsulation enables clearer lifecycle management (startup/shutdown) and simplifies dependency injection.

## Proposed Changes
- Introduce lightweight service containers that hold stateful components (processors, clients, metrics) and expose accessors to route handlers.
- Use FastAPI `lifespan` context or dependency injection to manage initialization and cleanup instead of manual globals.
- Update affected services to retrieve the container via dependency injection rather than referencing module globals directly.
- Adjust tests to instantiate containers explicitly, reducing reliance on implicit module initialization.

## Testing Strategy
- Add unit tests covering container initialization, ensuring state is correctly reset between tests.
- Run service integration tests to confirm startup/shutdown behavior remains intact.
- Perform manual smoke tests to ensure handlers operate correctly when multiple requests run in parallel.

## Open Questions
- Should we standardize on a shared container pattern across all services or allow service-specific implementations?
- Do we need helper utilities in `services.common` to simplify container creation and reuse?
