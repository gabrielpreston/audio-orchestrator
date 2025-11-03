# Proposal: Modularize STT Transcription Flow

## Summary
- Decompose `_transcribe_request` in `services/stt/app.py` into focused modules handling validation, enhancement, inference, and response formatting.
- Improve readability and testability by isolating responsibilities currently packed into a single 400+ line function.
- Create clear extension points for future features (e.g., alternative enhancement strategies or caching policies).

## Motivation
- The existing function is difficult to reason about, mixing HTTP concerns with device management, caching, and metrics.
- Minor changes risk regressions because there are few seams for targeted unit tests.
- Aligning with single-responsibility principles will make future contributions faster and safer.

## Proposed Changes
- Introduce separate modules/functions for: request parsing & metadata, optional enhancement, model readiness checks, inference execution, and response assembly.
- Wire these modules together in a slim orchestration function that retains current HTTP interface.
- Expand unit tests to cover each module individually, ensuring complex branches (e.g., cache hits, CUDA fallbacks) remain verified.
- Update documentation (if any) describing the transcription pipeline to reflect the new structure.

## Testing Strategy
- Create targeted unit tests for each new module, especially around error handling and logging side effects.
- Run STT service integration tests and pipeline end-to-end tests to confirm behavior parity.
- Perform manual benchmarking to ensure modularization does not introduce measurable latency.

## Open Questions
- Should enhancement invocation live inside the transcription service or be delegated entirely to audio processor clients in the long term?
- Do we want to expose hooks for alternative inference backends during this refactor, or keep the scope limited to structural cleanup?
