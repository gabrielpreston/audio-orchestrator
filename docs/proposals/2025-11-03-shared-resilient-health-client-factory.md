# Proposal: Shared Resilient Health Client Factory

## Summary
- Deduplicate `ResilientHTTPClient` setup across services by introducing a shared factory in `services.common`.
- Standardize circuit breaker configuration, startup grace period, and logging for downstream health checks.
- Simplify service startup code by replacing custom client wiring with declarative dependency registration.

## Goals
- Provide a single entry point for creating resilient health clients that covers current Discord, Orchestrator, and future services.
- Maintain compatibility with existing environment variable overrides (e.g., `STT_BASE_URL`).
- Document default behaviors (timeouts, retries) to set clear expectations for operators.

## Non-Goals
- Changing the core behavior of `ResilientHTTPClient` beyond parameter defaults.
- Handling non-HTTP dependencies (queues, databases) within this proposal.
- Replacing service-specific health logic (e.g., additional readiness criteria) beyond client creation.

## Motivation
- Orchestrator and Discord services currently repeat similar initialization logic, leading to subtle drift in retry/backoff settings.
- Centralizing configuration reduces risk of missing health checks when onboarding new dependencies.
- A shared factory shortens startup modules, making them easier to audit during incidents.

## Proposed Changes
- Add a helper (e.g., `services.common.health_clients.create_dependency_health_client`) that returns a configured `ResilientHTTPClient` based on service name and env prefix.
- Provide sensible defaults for timeout, circuit breaker thresholds, and startup grace period, while allowing overrides via kwargs.
- Update existing services (orchestrator, discord, others as applicable) to call the helper and register dependencies via the existing `HealthManager`.
- Document usage in `docs/getting-started` or service-specific READMEs to guide future integrations.

### Implementation Outline
1. Define factory interface including required inputs (service name, env prefix) and optional overrides (timeout, grace period).
2. Implement helper in `services/common/health_clients.py`, encapsulating circuit breaker configuration and logging hooks.
3. Provide utility functions for reading environment overrides consistently across services.
4. Refactor Orchestrator and Discord startup modules to call the helper instead of constructing clients manually.
5. Update documentation with examples and integrate with any service templates for new endpoints.

## Acceptance Criteria
- Factory exists with unit tests covering default parameter usage and override scenarios.
- Orchestrator and Discord services adopt the factory without losing existing functionality.
- Health endpoints continue to report accurate readiness, verified via integration tests.
- Documentation references the new factory for future dependency integrations.

## Dependencies
- Current implementation of `ResilientHTTPClient` and `CircuitBreakerConfig`.
- Coordination with any parallel efforts modifying health check logic to avoid conflicts.

## Risks & Mitigations
- **Risk:** Factory abstraction may hide service-specific tweaks needed in edge cases. *Mitigation:* Allow opt-out parameters or extension hooks for bespoke behavior.
- **Risk:** Refactor could introduce regressions in retry/backoff behavior. *Mitigation:* Capture existing configuration via tests before refactoring.

## Rollout Plan
- Week 1: Implement factory and unit tests.
- Week 2: Update Orchestrator and Discord services, run integration tests, and gather feedback.
- Week 3: Roll out to additional services if desired and finalize documentation.

## Testing Strategy
- Add unit tests covering factory behavior, ensuring environment overrides and default fallbacks work as expected.
- Run service-level tests to confirm health endpoints still respect dependency readiness.
- Perform a manual smoke test by simulating dependency outages and observing consistent logs/retries.

## Open Questions
- Should the factory also encapsulate cleanup (e.g., closing clients) or leave lifecycle management to service modules?
- Are there non-HTTP dependencies that need analogous factories (e.g., message queues) to pursue later?
