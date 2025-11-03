# Proposal: Modularize STT Transcription Flow

## Summary
- Decompose `_transcribe_request` in `services/stt/app.py` into focused modules handling validation, enhancement, inference, and response formatting.
- Improve readability and testability by isolating responsibilities currently packed into a single 400+ line function.
- Create clear extension points for future features (e.g., alternative enhancement strategies or caching policies).

## Goals
- Achieve clear separation between request validation, enhancement, caching, inference, and response formatting components.
- Maintain parity in API behavior, metrics, and logging after refactor.
- Provide reusable utilities or classes so additional features can hook into defined extension points.

## Non-Goals
- Switching to a different transcription engine or altering the HTTP interface.
- Replacing the existing caching implementation (beyond moving invocations into dedicated modules).
- Introducing asynchronous streaming responses (scope limited to code organization).

## Motivation
- The existing function is difficult to reason about, mixing HTTP concerns with device management, caching, and metrics.
- Minor changes risk regressions because there are few seams for targeted unit tests.
- Aligning with single-responsibility principles will make future contributions faster and safer.

## Proposed Changes
- Introduce separate modules/functions for: request parsing & metadata, optional enhancement, model readiness checks, inference execution, and response assembly.
- Wire these modules together in a slim orchestration function that retains current HTTP interface.
- Expand unit tests to cover each module individually, ensuring complex branches (e.g., cache hits, CUDA fallbacks) remain verified.
- Update documentation (if any) describing the transcription pipeline to reflect the new structure.

### Implementation Outline
1. Identify logical sub-components within `_transcribe_request` and document their current responsibilities.
2. Create dedicated modules/classes (e.g., `RequestContext`, `EnhancementPipeline`, `InferenceExecutor`, `ResponseBuilder`).
3. Move corresponding logic into each module, ensuring dependencies are passed explicitly rather than relying on globals.
4. Replace the monolithic function body with a high-level orchestration flow that invokes each module sequentially.
5. Update unit tests or create new ones per module for success/failure paths, ensuring coverage of cache hits, enhancement errors, and CUDA fallbacks.
6. Refresh integration tests and re-run performance benchmarks to compare latency before/after refactor.

## Acceptance Criteria
- `_transcribe_request` is reduced to high-level orchestration (<150 lines) with core logic housed in separate modules.
- Unit tests exist for each new module covering primary success and error scenarios.
- Integration tests for STT service pass without behavioral regressions.
- Performance metrics show no statistically significant degradation versus baseline.

## Dependencies
- Availability of supporting proposals (e.g., in-memory buffer handling) though not strictly required for structural refactor.
- Coordination with maintainers to freeze unrelated feature work during refactor to minimize merge conflicts.

## Risks & Mitigations
- **Risk:** Moving logic may break implicit assumptions (e.g., access to globals). *Mitigation:* Introduce explicit dependency injection and add regression tests.
- **Risk:** Refactor may destabilize performance. *Mitigation:* Capture baseline benchmarks and compare post-change.

## Rollout Plan
- Week 1: Finalize module boundaries and prepare design doc for stakeholder review.
- Week 2: Implement modularization with accompanying unit tests.
- Week 3: Run full integration/performance suite, gather feedback, and merge once stability is confirmed.

## Testing Strategy
- Create targeted unit tests for each new module, especially around error handling and logging side effects.
- Run STT service integration tests and pipeline end-to-end tests to confirm behavior parity.
- Perform manual benchmarking to ensure modularization does not introduce measurable latency.

## Open Questions
- Should enhancement invocation live inside the transcription service or be delegated entirely to audio processor clients in the long term?
- Do we want to expose hooks for alternative inference backends during this refactor, or keep the scope limited to structural cleanup?
