# Proposal: Remove Unused Testing Service Models

## Summary
- Delete `TranscriptRequest` and `TranscriptResponse` data models from `services/testing/app.py` since they are not referenced.
- Reduce clutter and avoid misleading contributors about supported endpoints.

## Goals
- Ensure the testing service only contains actively used data models and schemas.
- Keep API surface documentation aligned with implementation.

## Non-Goals
- Adding new request/response models for the testing service.
- Modifying Gradio UI components beyond removing unused references.

## Motivation
- Unused models can trick developers into assuming HTTP routes consume or return these structures.
- Leaner files make it easier to maintain the testing service and spot real opportunities for improvements.

## Proposed Changes
- Remove the two `BaseModel` classes and any associated imports that become redundant.
- Verify no documentation or UI components reference the unused models.

### Implementation Outline
1. Remove `TranscriptRequest` and `TranscriptResponse` class definitions.
2. Delete related import statements (e.g., `BaseModel`) if they become unused elsewhere.
3. Search the repo to confirm no references remain to the removed classes.
4. Update documentation or comments if they mentioned the models.

## Acceptance Criteria
- Testing service imports compile without unused references.
- Static analysis (e.g., `ruff`, `mypy`) reports no missing symbols.
- Manual review confirms no runtime code relied on the removed models.

## Dependencies
- None; change is internal to testing service module.

## Risks & Mitigations
- **Risk:** Hidden dependency on the models in external scripts. *Mitigation:* Perform repository-wide search before removal.

## Rollout Plan
- Implement removal in current PR, run lint/tests, and document the cleanup in release notes if necessary.

## Testing Strategy
- Run existing tests for the testing service to confirm behavior remains unchanged.
- Perform a quick manual smoke test of the Gradio UI to ensure no runtime errors arise from missing symbols.

## Open Questions
- None – the models are confirmed unused in the current codebase.
