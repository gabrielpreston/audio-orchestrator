# Proposal: Refine Bark Startup Pipeline

## Summary
- Break the Bark TTS startup routine into discrete steps covering environment patching, model downloads, GPU migration, and compilation.
- Replace deeply nested logic in `services/bark/synthesis.py` with composable helpers that clarify failure handling.
- Improve observability by emitting structured status updates per stage.

## Motivation
- The current startup method spans hundreds of lines, mixing environment configuration with heavy operations, making it hard to audit.
- Error cases (e.g., torch.compile failures) are handled inline, complicating reasoning about fallback behavior.
- A modular approach makes it easier to support alternative engines or adjust optimization steps.

## Proposed Changes
- Introduce helper functions for: cache directory preparation, force-download orchestration, PyTorch `safe_globals` patching, model preloading, GPU migration, and optional `torch.compile` optimization.
- Sequence the helpers in a clear startup pipeline that records stage results for diagnostics.
- Add minimal data classes or enums to describe stage outcomes, enabling targeted warnings vs. hard failures.
- Update or add tests to cover individual helpers, especially around environment variable handling and compilation toggles.

## Testing Strategy
- Unit test each helper with controlled environment variable inputs and mocked Bark/PyTorch APIs.
- Run TTS service startup tests to ensure the new pipeline still initializes models successfully on supported hardware.
- Conduct manual smoke tests generating audio to confirm end-to-end functionality and measure any startup time changes.

## Open Questions
- Should we generalize the pipeline framework for other ML-heavy services, or focus solely on Bark for now?
- Do we need to expose stage telemetry externally (e.g., via health endpoints), or keep it internal to logs and metrics?
