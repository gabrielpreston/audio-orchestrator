# Proposal: Standardize Service Metric Registration

## Summary

-  Create a shared helper to register observability metrics per service type during startup.
-  Replace copy-pasted metric creation blocks in audio, bark, discord, and other services with declarative calls.
-  Ensure consistent metric naming and lifecycle management across the stack.

## Goals

-  Provide a single helper that registers only the metric groups required by a service (audio, STT, TTS, HTTP, etc.).
-  Reduce duplicate boilerplate in startup routines while preserving existing metric semantics.
-  Document expected metric keys to streamline onboarding for new services.

## Non-Goals

-  Introducing new metrics or renaming existing ones beyond what is necessary for consolidation.
-  Modifying metric export pipelines (OpenTelemetry configuration remains unchanged).
-  Automatically enabling metrics for services that currently do not use them.

## Motivation

-  Multiple services replicate similar code to create audio/STT/HTTP/system metrics, risking inconsistencies when definitions evolve.
-  Centralizing setup allows quick updates to metric suites (e.g., adding attributes) without touching every service module.
-  Simplifies startup functions, making them easier to scan for business logic.

## Proposed Changes

-  Add `services.common.metrics.register_service_metrics(service_name, observability_manager, kinds=[...])` that returns the initialized metric dicts.
-  Refactor existing services to call the helper, requesting the subsets relevant to their domain (e.g., `audio`, `stt`, `tts`).
-  Update unit tests or fixtures that currently stub metric dicts to use the helper for consistent behavior.
-  Document usage and expectations (e.g., supported metric kinds) in a short README section.

### Implementation Outline

1.  Design helper signature with clear enumeration of supported metric groups (constants or Enum).
2.  Implement helper in `services/common/metrics.py`, reusing existing metric creation functions internally.
3.  Provide backward-compatible return structure (e.g., dictionary keyed by metric group) to minimize refactor scope.
4.  Update audio, bark, discord, and other services to adopt the helper.
5.  Adjust unit tests/mocks to rely on helper outputs where necessary.
6.  Document usage in developer guides, including example invocation.

## Acceptance Criteria

-  Helper exists with unit tests covering selection of different metric groups and invalid input handling.
-  All targeted services invoke the helper rather than duplicating metric creation logic.
-  No regression in emitted metric names verified via snapshot tests or manual inspection.
-  Documentation outlines how to use the helper for new services.

## Dependencies

-  Existing metric creation utilities in `services.common.audio_metrics`.
-  Coordination with service owners to schedule the refactor without conflicting changes.

## Risks & Mitigations

-  **Risk:** Helper may not cover edge-case metric combinations. *Mitigation:* Allow passing custom creators or extend supported groups iteratively.
-  **Risk:** Refactor might break tests relying on manual metric setup. *Mitigation:* Update fixtures/mocks as part of rollout and run full test suite.

## Rollout Plan

-  Week 1: Implement helper, add unit tests, and update documentation.
-  Week 2: Refactor audio and bark services; verify metrics.
-  Week 3: Refactor remaining services (discord, orchestrator, etc.) and finalize adoption.

## Testing Strategy

-  Add unit coverage for the helper to verify it returns the correct metric mapping for each service type.
-  Run `make test-component` to ensure service tests still pass after adopting the helper.
-  Perform a manual smoke test to confirm metrics export unchanged via existing observability tooling.

## Open Questions

-  Should the helper automatically attach metrics to `HealthManager`, or remain focused on OpenTelemetry instrumentation?
-  Do we need to backfill services that currently lack metrics hooks, or limit adoption to those already instrumented?
