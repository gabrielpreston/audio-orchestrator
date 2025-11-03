# Proposal: Cache Audio Request Body Once

## Summary
- Modify audio enhancement endpoints to read the request body a single time and reuse the buffered bytes across success and error paths.
- Prevent reliance on FastAPI's body caching semantics and eliminate redundant memory/disk operations.

## Motivation
- The current implementation re-reads the request body during error handling, which is fragile and can double workload for large audio payloads.
- Explicitly caching the bytes improves clarity and avoids surprises if framework internals change.

## Proposed Changes
- Read the request body once at the top of the helper (per the consolidation proposal) and store it in a local variable.
- Use the cached bytes for enhancement, logging, and fallback responses.
- Update logging to rely on cached lengths instead of re-inspecting the request.

## Testing Strategy
- Add unit tests confirming that repeated reads are no longer attempted (e.g., via mocked `Request.stream`).
- Run integration tests covering both success and failure paths to ensure responses remain unchanged.
- Conduct manual tests with large audio uploads to validate memory usage and performance improvements.

## Open Questions
- Should we stream extremely large audio payloads instead of buffering them entirely in memory, or is a full read acceptable for current use cases?
