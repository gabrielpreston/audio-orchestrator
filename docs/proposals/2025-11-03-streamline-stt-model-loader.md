# Proposal: Streamline STT Model Loader

## Summary
- Refactor `_load_from_cache` and `_load_with_fallback` in `services/stt/app.py` into reusable components with clearer responsibilities.
- Separate device validation, force-download logic, and model instantiation to reduce nesting and error-prone repetition.
- Provide structured status reporting for startup and runtime diagnostics.

## Motivation
- Current loader functions interleave environment parsing, CUDA validation, and fallback logic, making error handling convoluted.
- Similar CUDA fallback blocks are duplicated across cache and download paths, increasing maintenance overhead.
- Cleaner abstractions will make it easier to support additional model variants or hardware environments.

## Proposed Changes
- Introduce a `ModelLoadContext` data structure encapsulating device/compute decisions and timer metrics.
- Extract CUDA validation and adjustment into a dedicated utility callable from both loader paths.
- Simplify loader functions to orchestrate cache download attempts using shared helper methods for instrumentation and error reporting.
- Enhance background loader status objects with structured fields (e.g., last error, attempted device) for observability.

## Testing Strategy
- Add unit tests covering CUDA fallback scenarios, force-download flag behavior, and status reporting.
- Run STT service startup tests to ensure background loaders still complete successfully in CI and local environments.
- Perform manual verification on both CPU-only and GPU-enabled setups to confirm the simplified flow handles each properly.

## Open Questions
- Should we move the loader logic into a dedicated module (e.g., `services/stt/model_loader.py`) for cleaner separation, or refactor in place first?
- Do we need to support multiple concurrent models (e.g., multilingual variants) as part of this work, or leave that for a follow-up iteration?
