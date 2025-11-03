# Proposal: Refine Bark Startup Pipeline

## Summary
- Break the Bark TTS startup routine into discrete steps covering environment patching, model downloads, GPU migration, and compilation.
- Replace deeply nested logic in `services/bark/synthesis.py` with composable helpers that clarify failure handling.
- Improve observability by emitting structured status updates per stage.

## Goals
- Provide a deterministic startup pipeline where each stage has a clear success/failure signal.
- Preserve existing capabilities (force download, torch.compile optimizations) while improving readability.
- Make it easy to extend or skip stages (e.g., when running on CPU-only environments).

## Non-Goals
- Changing the Bark API surface or switching to a different TTS engine.
- Addressing runtime synthesis performance beyond ensuring startup remains efficient.
- Implementing new caching strategies outside the current directories.

## Motivation
- The current startup method spans hundreds of lines, mixing environment configuration with heavy operations, making it hard to audit.
- Error cases (e.g., torch.compile failures) are handled inline, complicating reasoning about fallback behavior.
- A modular approach makes it easier to support alternative engines or adjust optimization steps.

## Proposed Changes
- Introduce helper functions for: cache directory preparation, force-download orchestration, PyTorch `safe_globals` patching, model preloading, GPU migration, and optional `torch.compile` optimization.
- Sequence the helpers in a clear startup pipeline that records stage results for diagnostics.
- Add minimal data classes or enums to describe stage outcomes, enabling targeted warnings vs. hard failures.
- Update or add tests to cover individual helpers, especially around environment variable handling and compilation toggles.

### Implementation Outline
1. Document existing startup stages and dependencies between them.
2. Create data structures (`StartupStage`, `StageResult`) to model pipeline execution and logging.
3. Implement helper functions per stage, each returning a `StageResult` with status and metadata.
4. Build a pipeline executor that runs stages sequentially, short-circuiting on fatal failures and logging results.
5. Refactor `BarkSynthesizer.initialize()` to use the pipeline executor.
6. Add unit tests for each helper with mocked Bark/PyTorch APIs, covering success/failure paths.
7. Update integration tests to ensure overall startup still succeeds and logs remain informative.

## Acceptance Criteria
- Startup pipeline is composed of discrete helper functions with associated unit tests.
- Logging output clearly indicates success/failure of each stage with structured metadata.
- Bark service initializes successfully in both GPU-enabled and CPU-only environments.
- Documentation captures the new pipeline structure and stage responsibilities.

## Dependencies
- Current Bark models and environment variables (e.g., `BARK_ENABLE_TORCH_COMPILE`).
- Coordination with metric registration proposal if startup metrics are recorded.

## Risks & Mitigations
- **Risk:** Breaking torch.compile optimizations during refactor. *Mitigation:* Include explicit tests for compile-enabled and disabled modes.
- **Risk:** Increased abstraction might obscure debugging. *Mitigation:* Ensure stage results include error messages and references to remediation steps.

## Rollout Plan
- Week 1: Define pipeline structure and implement helper scaffolding.
- Week 2: Integrate helpers into Bark startup and add unit/integration tests.
- Week 3: Conduct performance validation and finalize documentation before merging.

## Testing Strategy
- Unit test each helper with controlled environment variable inputs and mocked Bark/PyTorch APIs.
- Run TTS service startup tests to ensure the new pipeline still initializes models successfully on supported hardware.
- Conduct manual smoke tests generating audio to confirm end-to-end functionality and measure any startup time changes.

## Open Questions
- Should we generalize the pipeline framework for other ML-heavy services, or focus solely on Bark for now?
- Do we need to expose stage telemetry externally (e.g., via health endpoints), or keep it internal to logs and metrics?
