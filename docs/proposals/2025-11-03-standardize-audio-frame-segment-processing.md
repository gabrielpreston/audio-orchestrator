# Proposal: Standardize Audio Frame and Segment Processing

## Summary
- Extract common frame/segment request handling in `services/audio/app.py` into a reusable helper within `services.common`.
- Reduce duplicated base64 decoding, PCM construction, and metric recording logic across `/process/frame` and `/process/segment` endpoints.
- Prepare shared utilities for future audio services to adopt the same contract with less boilerplate.

## Goals
- Deliver a single helper that covers request parsing, telemetry hooks, and shared error handling for frame and segment processing.
- Preserve existing API contracts and response payloads so downstream clients require no changes.
- Document the helper usage so other services can onboard quickly.

## Non-Goals
- Changing the response schema or status codes of current endpoints.
- Reworking audio processor internals beyond the shared helper extraction.
- Introducing new metrics; scope is limited to consolidating existing ones.

## Motivation
- Current endpoints repeat nearly identical steps, increasing maintenance cost and drift risk.
- Shared instrumentation makes it easier to refine logging/metrics consistently.
- Consolidation improves testability by enabling coverage of the shared helper in isolation.

## Proposed Changes
- Introduce a `services.common.audio_processing` module exposing helpers for decoding PCM payloads, constructing `PCMFrame`/`AudioSegment`, and recording metrics.
- Refactor `/process/frame` and `/process/segment` handlers to delegate to the new helper while keeping HTTP concerns local.
- Add targeted unit tests around the helper to capture error handling behavior currently duplicated inline.
- Update integration tests, if necessary, to reflect any minor response shape adjustments (none anticipated).

### Implementation Outline
1. Audit existing logic in both endpoints to produce a checklist of shared steps (decode, build domain object, process, metrics, logging).
2. Design helper API signatures (e.g., `process_pcm_frame(request: PCMFrameRequest, context: AudioProcessingContext) -> ProcessingResponse`).
3. Implement helper in `services.common.audio_processing` with configurable callbacks for processing functions provided by `AudioProcessor`.
4. Update endpoints to invoke helper while passing service-specific callbacks and log metadata.
5. Add unit tests for helper covering success, processor unavailable, and decode failure scenarios.
6. Run existing integration tests to confirm behavior parity, adjusting fixtures only if necessary.

## Acceptance Criteria
- Both `/process/frame` and `/process/segment` endpoints delegate to the shared helper with no loss in functionality.
- Unit tests cover happy-path and error-path flows for the helper (minimum: decode failure, processor missing, metrics recording).
- Integration tests for audio service pass without regression.
- Documentation or inline comments explain how other services can reuse the helper.

## Dependencies
- Availability of `AudioProcessor` methods (`process_frame`, `process_segment`, `calculate_quality_metrics`).
- Coordination with any ongoing changes in `services.common.surfaces` to avoid merge conflicts.

## Risks & Mitigations
- **Risk:** Helper abstraction may hide subtle differences between frame and segment flows. *Mitigation:* Keep helper configurable and ensure tests cover branch-specific attributes.
- **Risk:** Metrics keys could change inadvertently. *Mitigation:* Snapshot current metric names and assert them in tests.

## Rollout Plan
- Week 1: Finalize helper API design and gather stakeholder feedback (audio service maintainer).
- Week 2: Implement helper + unit tests; raise PR for review.
- Week 3: Merge after verification and update developer documentation.

## Testing Strategy
- Extend existing unit tests (`services/audio/tests`) to cover the helper and edge cases (invalid base64, missing audio).
- Run `make test-component` to ensure service-level tests and integration suites remain green.
- Spot-check `/process/frame` and `/process/segment` manually with sample payloads via cURL or existing fixtures.

## Open Questions
- Should the helper also own the HTTP exception mapping, or remain agnostic and return typed errors?
- Are there other services (e.g., STT enhancement) that should reuse the helper in the same iteration, or defer until after stabilization?
