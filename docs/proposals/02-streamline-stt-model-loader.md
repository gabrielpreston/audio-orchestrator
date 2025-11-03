# Proposal: Streamline STT Model Loader

## Summary
- Refactor `_load_from_cache` and `_load_with_fallback` in `services/stt/app.py` into reusable components with clearer responsibilities.
- Separate device validation, force-download logic, and model instantiation to reduce nesting and error-prone repetition.
- Provide structured status reporting for startup and runtime diagnostics.

## Goals
- Encapsulate device selection, cache loading, and download fallback into composable functions or classes.
- Maintain existing loader behavior (including fallback to CPU) while simplifying control flow.
- Expose structured status data that can be consumed by health checks and logs.

## Non-Goals
- Changing the default model selection strategy or supported Whisper variants.
- Replacing BackgroundModelLoader; focus is on the functions passed into it.
- Altering environment variable names or configuration surfaces.

## Motivation
- Current loader functions interleave environment parsing, CUDA validation, and fallback logic, making error handling convoluted.
- Similar CUDA fallback blocks are duplicated across cache and download paths, increasing maintenance overhead.
- Cleaner abstractions will make it easier to support additional model variants or hardware environments.

## Proposed Changes
- Introduce a `ModelLoadContext` data structure encapsulating device/compute decisions and timer metrics.
- Extract CUDA validation and adjustment into a dedicated utility callable from both loader paths.
- Simplify loader functions to orchestrate cache download attempts using shared helper methods for instrumentation and error reporting.
- Enhance background loader status objects with structured fields (e.g., last error, attempted device) for observability.

### Implementation Outline
1. Define `ModelLoadContext` capturing intended device, compute type, force-download flags, and timing metadata.
2. Implement `resolve_device_settings()` utility to handle CUDA validation and fallback logic once.
3. Refactor cache and download loader functions to:
   - Construct a context via the utility.
   - Attempt cache or download using shared helper methods (`load_from_local_cache`, `load_from_source`).
   - Populate structured status records for success/failure.
4. Update `BackgroundModelLoader` initialization to consume the new functions.
5. Adjust logging to rely on structured data rather than ad-hoc messages.
6. Write unit tests covering CPU/GPU availability, force download toggles, and error propagation.

## Acceptance Criteria
- Loader functions reduced in complexity with shared utilities controlling CUDA validation and error handling.
- Structured status objects expose fields consumed by health checks/logging (e.g., `device_used`, `last_error`).
- Unit tests verify fallback behaviors and force-download logic without duplication.
- Startup process for STT service remains successful across CPU-only and GPU-enabled environments.

## Dependencies
- Current CUDA validation utilities (`services.common.gpu_utils`).
- Coordination with modularization proposal to avoid conflicting edits.

## Risks & Mitigations
- **Risk:** Refactor may introduce subtle differences in loader timing or logging. *Mitigation:* Capture baseline logs and compare post-change; add assertions in tests.
- **Risk:** Additional abstraction may complicate debugging if not well documented. *Mitigation:* Provide docstrings and developer guide entry explaining context structure.

## Rollout Plan
- Week 1: Build utilities/context structures and unit tests.
- Week 2: Integrate with loader functions and run GPU/CPU smoke tests.
- Week 3: Final review with maintainers and merge once stability confirmed.

## Testing Strategy
- Add unit tests covering CUDA fallback scenarios, force-download flag behavior, and status reporting.
- Run STT service startup tests to ensure background loaders still complete successfully in CI and local environments.
- Perform manual verification on both CPU-only and GPU-enabled setups to confirm the simplified flow handles each properly.

## Open Questions
- Should we move the loader logic into a dedicated module (e.g., `services/stt/model_loader.py`) for cleaner separation, or refactor in place first?
- Do we need to support multiple concurrent models (e.g., multilingual variants) as part of this work, or leave that for a follow-up iteration?
