# Proposal: Use In-Memory WAV Buffer for STT

## Summary
- Replace temporary file writes in `_transcribe_request` with in-memory `BytesIO` buffers for faster-whisper input.
- Reduce filesystem I/O overhead during transcription while maintaining compatibility with the model API.

## Motivation
- Writing every request to disk is expensive on shared volumes and complicates cleanup logic.
- In-memory buffers are sufficient for the typical audio sizes handled by the STT service and simplify error handling.

## Proposed Changes
- Investigate whether faster-whisper accepts file-like objects or raw bytes; if not, wrap bytes in a custom reader object to mimic file behavior.
- Remove `NamedTemporaryFile` usage and associated cleanup code from `_transcribe_request`.
- Adjust metrics/logging to track buffer sizes rather than file paths.

## Testing Strategy
- Unit test the new buffer approach, mocking faster-whisper to validate compatibility and ensure cleanup occurs.
- Run integration and E2E tests to confirm transcription accuracy and latency improvements.
- Benchmark before/after throughput to quantify performance gains.

## Open Questions
- Are there extreme audio durations where memory usage becomes a concern, and should we fall back to temp files above a threshold?
