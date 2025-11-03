# Proposal: Consolidate Audio Enhancement Endpoints

## Summary
- Unify `/enhance/audio`, `/denoise`, and `/denoise/streaming` handling in `services/audio/app.py` behind a single shared orchestration function.
- Centralize request parsing, MetricGAN invocation, logging, and failure fallbacks to eliminate triplicated code paths.
- Provide a flexible helper that supports future enhancement modes without repeating boilerplate.

## Motivation
- Current endpoints duplicate nearly identical logic, increasing the chance of inconsistent metrics and error handling.
- Maintaining multiple copies of streaming vs. batch behavior slows iteration on enhancement improvements.
- Consolidation clarifies the difference between API semantics and processing strategy, improving long-term maintainability.

## Proposed Changes
- Add an internal helper that ingests the `Request`, extracts correlation/context metadata once, invokes the enhancer, and returns the appropriate `Response`.
- Parameterize the helper with endpoint-specific attributes (e.g., response filename, log keys) to preserve existing surface behavior.
- Update the three endpoints to delegate to the helper while keeping their route definitions intact.
- Introduce shared tests validating success/error flows through the helper rather than per-endpoint copies.

## Testing Strategy
- Extend unit tests in `services/audio/tests` to cover helper-level logic with mocked enhancer outcomes.
- Use existing integration tests (e.g., `services/tests/integration/test_full_pipeline_e2e.py`) to confirm endpoints remain backwards compatible.
- Manually verify correlation-ID propagation and response headers via local requests.

## Open Questions
- Should the helper return FastAPI `Response` objects directly, or surface structured results that the endpoints convert to HTTP responses?
- Are there additional enhancement endpoints (e.g., chunked streaming) planned that should align with this abstraction now?
