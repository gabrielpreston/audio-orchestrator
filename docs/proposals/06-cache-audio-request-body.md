# Proposal: Cache Audio Request Body Once

## Summary
- Modify audio enhancement endpoints to read the request body a single time and reuse the buffered bytes across success and error paths.
- Prevent reliance on FastAPI's body caching semantics and eliminate redundant memory/disk operations.

## Goals
- Ensure all audio enhancement routes read the request body exactly once per request.
- Preserve current API behavior, including fallback to original audio on errors.
- Improve clarity of code by making body caching explicit.

## Non-Goals
- Switching to streaming request handling (scope limited to buffering once).
- Changing response payloads or headers.
- Rewriting MetricGAN enhancement logic.

## Motivation
- The current implementation re-reads the request body during error handling, which is fragile and can double workload for large audio payloads.
- Explicitly caching the bytes improves clarity and avoids surprises if framework internals change.

## Proposed Changes
- Read the request body once at the top of the helper (per the consolidation proposal) and store it in a local variable.
- Use the cached bytes for enhancement, logging, and fallback responses.
- Update logging to rely on cached lengths instead of re-inspecting the request.

### Implementation Outline
1. Introduce helper (or update existing helper from consolidation proposal) to read body into `bytes` and return alongside correlation context.
2. Refactor enhancement endpoints to consume cached bytes for primary processing and failure fallback.
3. Update logging statements to use cached lengths or metadata.
4. Add guardrails for memory usage (optional threshold or warnings) if payload exceeds expected size.

## Acceptance Criteria
- Each endpoint reads request body once (validated by tests/mocks) and reuses cached bytes.
- Error paths return original audio using cached bytes without re-reading from request.
- Unit/integration tests confirm behavior parity.

## Dependencies
- Consolidation of audio enhancement endpoints (companion proposal) for shared helper integration.

## Risks & Mitigations
- **Risk:** Large payloads may increase memory usage when fully buffered. *Mitigation:* Document limits and consider optional streaming follow-up if needed.

## Rollout Plan
- Implement caching during consolidation refactor, run tests, and verify with sample uploads.

## Testing Strategy
- Add unit tests confirming that repeated reads are no longer attempted (e.g., via mocked `Request.stream`).
- Run integration tests covering both success and failure paths to ensure responses remain unchanged.
- Conduct manual tests with large audio uploads to validate memory usage and performance improvements.

## Open Questions
- Should we stream extremely large audio payloads instead of buffering them entirely in memory, or is a full read acceptable for current use cases?
