# Proposal: Standardize Audio Frame and Segment Processing

## Summary
- Extract common frame/segment request handling in `services/audio/app.py` into a reusable helper within `services.common`.
- Reduce duplicated base64 decoding, PCM construction, and metric recording logic across `/process/frame` and `/process/segment` endpoints.
- Prepare shared utilities for future audio services to adopt the same contract with less boilerplate.

## Motivation
- Current endpoints repeat nearly identical steps, increasing maintenance cost and drift risk.
- Shared instrumentation makes it easier to refine logging/metrics consistently.
- Consolidation improves testability by enabling coverage of the shared helper in isolation.

## Proposed Changes
- Introduce a `services.common.audio_processing` module exposing helpers for decoding PCM payloads, constructing `PCMFrame`/`AudioSegment`, and recording metrics.
- Refactor `/process/frame` and `/process/segment` handlers to delegate to the new helper while keeping HTTP concerns local.
- Add targeted unit tests around the helper to capture error handling behavior currently duplicated inline.
- Update integration tests, if necessary, to reflect any minor response shape adjustments (none anticipated).

## Testing Strategy
- Extend existing unit tests (`services/audio/tests`) to cover the helper and edge cases (invalid base64, missing audio).
- Run `make test-component` to ensure service-level tests and integration suites remain green.
- Spot-check `/process/frame` and `/process/segment` manually with sample payloads via cURL or existing fixtures.

## Open Questions
- Should the helper also own the HTTP exception mapping, or remain agnostic and return typed errors?
- Are there other services (e.g., STT enhancement) that should reuse the helper in the same iteration, or defer until after stabilization?
