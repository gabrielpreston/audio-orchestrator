# Proposal: Consolidate Audio Enhancement Endpoints

## Summary
- Unify `/enhance/audio`, `/denoise`, and `/denoise/streaming` handling in `services/audio/app.py` behind a single shared orchestration function.
- Centralize request parsing, MetricGAN invocation, logging, and failure fallbacks to eliminate triplicated code paths.
- Provide a flexible helper that supports future enhancement modes without repeating boilerplate.

## Goals
- Deliver one reusable helper that can service all three endpoints while allowing endpoint-specific metadata (e.g., filenames).
- Ensure correlation IDs, logging, and metrics behave identically across all routes post-refactor.
- Make it straightforward to introduce new enhancement endpoints with minimal additional code.

## Non-Goals
- Changing the HTTP routes or public API names.
- Modifying the underlying `AudioEnhancer` implementation (beyond minor adjustments required by consolidation).
- Introducing streaming transformations beyond current MetricGAN functionality.

## Motivation
- Current endpoints duplicate nearly identical logic, increasing the chance of inconsistent metrics and error handling.
- Maintaining multiple copies of streaming vs. batch behavior slows iteration on enhancement improvements.
- Consolidation clarifies the difference between API semantics and processing strategy, improving long-term maintainability.

## Proposed Changes
- Add an internal helper that ingests the `Request`, extracts correlation/context metadata once, invokes the enhancer, and returns the appropriate `Response`.
- Parameterize the helper with endpoint-specific attributes (e.g., response filename, log keys) to preserve existing surface behavior.
- Update the three endpoints to delegate to the helper while keeping their route definitions intact.
- Introduce shared tests validating success/error flows through the helper rather than per-endpoint copies.

### Implementation Outline
1. Map the common steps across the three endpoints (body read, correlation ID extraction, enhancement call, response construction).
2. Define helper signature (e.g., `process_enhancement(request: Request, *, response_filename: str, log_context: dict[str, Any])`).
3. Implement helper ensuring it caches the request body once, handles success/error logging, and records metrics.
4. Refactor each endpoint to call the helper with the appropriate parameters.
5. Update tests to target the helper directly plus smoke-test each endpoint.
6. Document the pattern for adding future endpoints (e.g., new streaming variants).

## Acceptance Criteria
- All three endpoints rely on the helper, with no duplicated request/response logic left in route handlers.
- Metrics and logs emitted before and after the refactor align (validated via unit tests or snapshot comparisons).
- Error handling remains consistent, including returning original audio when enhancement fails.
- Tests cover success and failure in the helper, and integration tests confirm no regression in API behavior.

## Dependencies
- Consolidated helper requires `AudioEnhancer` interface stability.
- Coordination with the ?Cache Audio Request Body Once? proposal, which complements this change.

## Risks & Mitigations
- **Risk:** Helper may inadvertently alter response headers. *Mitigation:* Write assertions validating headers in unit/integration tests.
- **Risk:** Streaming-specific behavior may require special casing. *Mitigation:* Provide hooks in helper for streaming configuration or keep lightweight branching per caller.

## Rollout Plan
- Align with audio service owners on helper API (Week 1).
- Implement helper and refactor endpoints (Week 2), followed by unit/integration tests.
- Monitor logs after deployment for inconsistencies (Week 3) and update documentation if required.

## Testing Strategy
- Extend unit tests in `services/audio/tests` to cover helper-level logic with mocked enhancer outcomes.
- Use existing integration tests (e.g., `services/tests/integration/test_full_pipeline_e2e.py`) to confirm endpoints remain backwards compatible.
- Manually verify correlation-ID propagation and response headers via local requests.

## Open Questions
- Should the helper return FastAPI `Response` objects directly, or surface structured results that the endpoints convert to HTTP responses?
- Are there additional enhancement endpoints (e.g., chunked streaming) planned that should align with this abstraction now?
