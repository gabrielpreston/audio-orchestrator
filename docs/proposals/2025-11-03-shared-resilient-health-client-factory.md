# Proposal: Shared Resilient Health Client Factory

## Summary
- Deduplicate `ResilientHTTPClient` setup across services by introducing a shared factory in `services.common`.
- Standardize circuit breaker configuration, startup grace period, and logging for downstream health checks.
- Simplify service startup code by replacing custom client wiring with declarative dependency registration.

## Motivation
- Orchestrator and Discord services currently repeat similar initialization logic, leading to subtle drift in retry/backoff settings.
- Centralizing configuration reduces risk of missing health checks when onboarding new dependencies.
- A shared factory shortens startup modules, making them easier to audit during incidents.

## Proposed Changes
- Add a helper (e.g., `services.common.health_clients.create_dependency_health_client`) that returns a configured `ResilientHTTPClient` based on service name and env prefix.
- Provide sensible defaults for timeout, circuit breaker thresholds, and startup grace period, while allowing overrides via kwargs.
- Update existing services (orchestrator, discord, others as applicable) to call the helper and register dependencies via the existing `HealthManager`.
- Document usage in `docs/getting-started` or service-specific READMEs to guide future integrations.

## Testing Strategy
- Add unit tests covering factory behavior, ensuring environment overrides and default fallbacks work as expected.
- Run service-level tests to confirm health endpoints still respect dependency readiness.
- Perform a manual smoke test by simulating dependency outages and observing consistent logs/retries.

## Open Questions
- Should the factory also encapsulate cleanup (e.g., closing clients) or leave lifecycle management to service modules?
- Are there non-HTTP dependencies that need analogous factories (e.g., message queues) to pursue later?
