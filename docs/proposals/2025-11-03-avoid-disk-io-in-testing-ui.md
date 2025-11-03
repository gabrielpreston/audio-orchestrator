# Proposal: Avoid Disk I/O in Testing UI

## Summary
- Update the testing UI service to keep synthesized audio results in memory until users explicitly download them.
- Reduce reliance on temporary files when running the end-to-end pipeline via Gradio.

## Motivation
- Writing every synthesis output to disk introduces delays and potential cleanup issues, especially during rapid iteration.
- In-memory handling simplifies deployment in environments with restricted filesystem access.

## Proposed Changes
- Modify `run_pipeline` to retain orchestrator-generated audio in memory (e.g., `BytesIO`) and only persist to disk if Gradio requires a file path.
- Provide a lightweight download helper that writes the file on demand, using deterministic naming when necessary.
- Remove tempfile usage where possible, updating logging and error handling accordingly.

## Testing Strategy
- Manual smoke tests through the Gradio UI to ensure audio playback still works and download buttons behave correctly.
- Add unit tests (if feasible) for the new helper to verify memory-to-disk conversion.
- Run integration tests to confirm pipeline responses remain unchanged.

## Open Questions
- Does the Gradio component in use mandate a filesystem path, or can it consume raw bytes directly?
- Should we introduce retention limits or cleanup hooks for any files that still need to be written?
