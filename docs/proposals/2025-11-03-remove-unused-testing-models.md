# Proposal: Remove Unused Testing Service Models

## Summary
- Delete `TranscriptRequest` and `TranscriptResponse` data models from `services/testing/app.py` since they are not referenced.
- Reduce clutter and avoid misleading contributors about supported endpoints.

## Motivation
- Unused models can trick developers into assuming HTTP routes consume or return these structures.
- Leaner files make it easier to maintain the testing service and spot real opportunities for improvements.

## Proposed Changes
- Remove the two `BaseModel` classes and any associated imports that become redundant.
- Verify no documentation or UI components reference the unused models.

## Testing Strategy
- Run existing tests for the testing service to confirm behavior remains unchanged.
- Perform a quick manual smoke test of the Gradio UI to ensure no runtime errors arise from missing symbols.

## Open Questions
- None – the models are confirmed unused in the current codebase.
