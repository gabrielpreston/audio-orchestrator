# Proposal: Standardize Service Metric Registration

## Summary
- Create a shared helper to register observability metrics per service type during startup.
- Replace copy-pasted metric creation blocks in audio, bark, discord, and other services with declarative calls.
- Ensure consistent metric naming and lifecycle management across the stack.

## Motivation
- Multiple services replicate similar code to create audio/STT/HTTP/system metrics, risking inconsistencies when definitions evolve.
- Centralizing setup allows quick updates to metric suites (e.g., adding attributes) without touching every service module.
- Simplifies startup functions, making them easier to scan for business logic.

## Proposed Changes
- Add `services.common.metrics.register_service_metrics(service_name, observability_manager, kinds=[...])` that returns the initialized metric dicts.
- Refactor existing services to call the helper, requesting the subsets relevant to their domain (e.g., `audio`, `stt`, `tts`).
- Update unit tests or fixtures that currently stub metric dicts to use the helper for consistent behavior.
- Document usage and expectations (e.g., supported metric kinds) in a short README section.

## Testing Strategy
- Add unit coverage for the helper to verify it returns the correct metric mapping for each service type.
- Run `make test-component` to ensure service tests still pass after adopting the helper.
- Perform a manual smoke test to confirm metrics export unchanged via existing observability tooling.

## Open Questions
- Should the helper automatically attach metrics to `HealthManager`, or remain focused on OpenTelemetry instrumentation?
- Do we need to backfill services that currently lack metrics hooks, or limit adoption to those already instrumented?
