# Proposal: Use In-Memory WAV Buffer for STT

## Summary
- Replace temporary file writes in `_transcribe_request` with in-memory `BytesIO` buffers for faster-whisper input.
- Reduce filesystem I/O overhead during transcription while maintaining compatibility with the model API.

## Goals
- Eliminate reliance on disk I/O for routine transcription requests.
- Preserve compatibility with faster-whisper by providing acceptable file-like interfaces.
- Maintain existing logging and metrics for input size/duration.

## Non-Goals
- Introducing streaming transcription or chunked uploads.
- Changing the transcription API surface or response payloads.
- Removing optional fallback to disk for extreme edge cases (unless necessary).

## Motivation
- Writing every request to disk is expensive on shared volumes and complicates cleanup logic.
- In-memory buffers are sufficient for the typical audio sizes handled by the STT service and simplify error handling.

## Proposed Changes
- Investigate whether faster-whisper accepts file-like objects or raw bytes; if not, wrap bytes in a custom reader object to mimic file behavior.
- Remove `NamedTemporaryFile` usage and associated cleanup code from `_transcribe_request`.
- Adjust metrics/logging to track buffer sizes rather than file paths.

### Implementation Outline
1. Verify faster-whisper support for file-like objects; if needed, implement wrapper class exposing `.read()`/`__enter__` semantics.
2. Replace temp-file creation with `BytesIO` buffer creation from request bytes.
3. Update inference call to accept buffer/wrapper.
4. Remove cleanup logic tied to temp files.
5. Update logging to reference buffer info (size) instead of file paths.
6. Add unit tests verifying inference path functions with in-memory buffers, including fallback for translation/language parameters.

## Acceptance Criteria
- `_transcribe_request` no longer writes to disk under normal conditions.
- Unit/integration tests pass, confirming successful transcription with in-memory buffers.
- Benchmarks demonstrate equal or improved latency compared to baseline.

## Dependencies
- Modularization effort for `_transcribe_request` (helps isolate changes).
- Compatibility of faster-whisper with file-like objects.

## Risks & Mitigations
- **Risk:** Large audio files could consume significant memory. *Mitigation:* Optionally retain fallback to disk when payload exceeds configurable threshold.
- **Risk:** faster-whisper might require file paths for certain operations. *Mitigation:* Provide compatibility wrapper or maintain fallback code path.

## Rollout Plan
- Week 1: Validate approach with prototype and unit tests.
- Week 2: Integrate into STT service, run benchmarks, and update documentation.
- Week 3: Monitor in staging for memory usage, adjust thresholds if needed, and roll out to production.

## Testing Strategy
- Unit test the new buffer approach, mocking faster-whisper to validate compatibility and ensure cleanup occurs.
- Run integration and E2E tests to confirm transcription accuracy and latency improvements.
- Benchmark before/after throughput to quantify performance gains.

## Open Questions
- Are there extreme audio durations where memory usage becomes a concern, and should we fall back to temp files above a threshold?
