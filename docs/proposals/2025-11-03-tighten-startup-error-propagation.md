# Proposal: Tighten Startup Error Propagation

## Summary
- Ensure service startup failures surface in readiness checks instead of being swallowed by broad `except Exception` blocks.
- Record failure details in `HealthManager` so operators can identify initialization issues quickly.

## Motivation
- Several services log startup errors but still mark readiness complete, leading to false-positive health signals.
- Accurate readiness gating prevents upstream services from sending traffic to partially initialized dependencies.

## Proposed Changes
- Refactor startup routines to capture exceptions, store them in the `HealthManager`, and avoid calling `mark_startup_complete()` when critical steps fail.
- Provide helper utilities for common patterns (e.g., `health_manager.record_startup_failure(...)`).
- Update health endpoints to surface failure details (status + reason) while maintaining security considerations.
- Audit services for redundant try/except blocks once central handling is in place.

## Testing Strategy
- Add unit tests verifying that startup failures prevent readiness and that health endpoints report the expected status codes.
- Run integration tests simulating dependency failures to confirm the new behavior propagates through Compose environments.
- Perform manual smoke tests by intentionally misconfiguring a service and confirming readiness stays false until resolved.

## Open Questions
- Should we introduce exponential backoff/retry loops for optional dependencies, or keep failure handling explicit?
- How do we balance verbose error reporting with security/privacy (e.g., hiding sensitive configuration values)?
