# Proposal: Avoid Disk I/O in Testing UI

## Summary
- Update the testing UI service to keep synthesized audio results in memory until users explicitly download them.
- Reduce reliance on temporary files when running the end-to-end pipeline via Gradio.

## Goals
- Provide a responsive UI experience by minimizing filesystem latency.
- Maintain compatibility with Gradio components while preferring in-memory storage.
- Offer explicit download functionality that writes to disk only when required by the user.

## Non-Goals
- Replacing Gradio with another UI framework.
- Changing the pipeline sequence or service calls used by the testing interface.
- Implementing long-term storage for generated audio.

## Motivation
- Writing every synthesis output to disk introduces delays and potential cleanup issues, especially during rapid iteration.
- In-memory handling simplifies deployment in environments with restricted filesystem access.

## Proposed Changes
- Modify `run_pipeline` to retain orchestrator-generated audio in memory (e.g., `BytesIO`) and only persist to disk if Gradio requires a file path.
- Provide a lightweight download helper that writes the file on demand, using deterministic naming when necessary.
- Remove tempfile usage where possible, updating logging and error handling accordingly.

### Implementation Outline
1. Audit Gradio components in use to understand input requirements (bytes vs. file path).
2. Update pipeline to keep audio data in memory (e.g., `bytes` or `BytesIO`).
3. If Gradio requires file paths, generate them lazily only when user chooses to download.
4. Implement cleanup strategy for any temporary files created on demand.
5. Adjust logging to capture memory-based workflow.
6. Update documentation/instructions for contributors explaining new behavior.

## Acceptance Criteria
- Default pipeline execution avoids writing files unless user explicitly downloads audio.
- UI functionality (playback, download) operates correctly after change.
- Tests (unit/integration/manual) confirm no regression in pipeline behavior.

## Dependencies
- Gradio component capabilities regarding in-memory audio handling.

## Risks & Mitigations
- **Risk:** Gradio may still require filesystem paths for certain widgets. *Mitigation:* Provide conditional logic to create temporary files only when necessary, with immediate cleanup.
- **Risk:** Increased memory usage for long sessions. *Mitigation:* Add limits or periodic cleanup of cached audio objects.

## Rollout Plan
- Week 1: Validate Gradio capabilities and prototype in-memory playback.
- Week 2: Implement changes, add tests, and update documentation.
- Week 3: Conduct manual QA on the UI and roll out alongside other testing service improvements.

## Testing Strategy
- Manual smoke tests through the Gradio UI to ensure audio playback still works and download buttons behave correctly.
- Add unit tests (if feasible) for the new helper to verify memory-to-disk conversion.
- Run integration tests to confirm pipeline responses remain unchanged.

## Open Questions
- Does the Gradio component in use mandate a filesystem path, or can it consume raw bytes directly?
- Should we introduce retention limits or cleanup hooks for any files that still need to be written?
