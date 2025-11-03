# Proposal: Tighten Startup Error Propagation

## Summary
- Ensure service startup failures surface in readiness checks instead of being swallowed by broad `except Exception` blocks.
- Record failure details in `HealthManager` so operators can identify initialization issues quickly.

## Goals
- Provide a consistent mechanism for capturing and exposing startup failures across services.
- Prevent services from reporting ready status when critical initialization steps fail.
- Supply actionable diagnostics (error message, failed dependency) through health endpoints or logs.

## Non-Goals
- Redesigning the overall health endpoint structure beyond startup failure reporting.
- Implementing automatic retries/backoff for failed dependencies (can be follow-up work).
- Exposing sensitive configuration details in error messages.

## Motivation
- Several services log startup errors but still mark readiness complete, leading to false-positive health signals.
- Accurate readiness gating prevents upstream services from sending traffic to partially initialized dependencies.

## Proposed Changes
- Refactor startup routines to capture exceptions, store them in the `HealthManager`, and avoid calling `mark_startup_complete()` when critical steps fail.
- Provide helper utilities for common patterns (e.g., `health_manager.record_startup_failure(...)`).
- Update health endpoints to surface failure details (status + reason) while maintaining security considerations.
- Audit services for redundant try/except blocks once central handling is in place.

### Implementation Outline
1. Extend `HealthManager` with methods for recording failure state and exposing failure details.
2. Update startup routines in key services (audio, STT, bark, discord) to wrap initialization in try/except that records failures without marking ready.
3. Adjust health endpoints to read failure state and respond with appropriate status codes/messages.
4. Provide documentation and examples for handling optional dependencies (e.g., degrade gracefully vs. fail readiness).
5. Add regression tests ensuring readiness stays false until startup completes successfully.

## Acceptance Criteria
- `HealthManager` exposes APIs for recording and retrieving startup failures.
- Services under scope adopt the new pattern and no longer mark ready on failure.
- Health endpoints return `503` (or relevant code) with summarized failure reason when startup fails.
- Test coverage ensures that both success and failure paths behave as expected.

## Dependencies
- Existing health endpoint implementation and `HealthManager` structure.
- Coordination with service owners to time refactor alongside other startup changes.

## Risks & Mitigations
- **Risk:** Over-reporting failures for optional components. *Mitigation:* Allow services to classify dependencies as required vs. optional when recording failure.
- **Risk:** Revealing sensitive information in error responses. *Mitigation:* Sanitize messages and restrict details to logs while keeping health responses high-level.

## Rollout Plan
- Week 1: Implement `HealthManager` enhancements and add unit tests.
- Week 2: Apply changes to audio/STT services and verify integration tests.
- Week 3: Roll out to remaining services, update documentation, and monitor deployment.

## Testing Strategy
- Add unit tests verifying that startup failures prevent readiness and that health endpoints report the expected status codes.
- Run integration tests simulating dependency failures to confirm the new behavior propagates through Compose environments.
- Perform manual smoke tests by intentionally misconfiguring a service and confirming readiness stays false until resolved.

## Open Questions
- Should we introduce exponential backoff/retry loops for optional dependencies, or keep failure handling explicit?
- How do we balance verbose error reporting with security/privacy (e.g., hiding sensitive configuration values)?
