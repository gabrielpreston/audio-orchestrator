# Migration Candidates Breakdown

## Discord Voice Interface

### Voice Activity Detection Pipeline
- **Current state:** Audio segments now run through WebRTC VAD with configurable aggressiveness and
  resampling before accumulation, replacing the old RMS threshold gating in
  `AudioPipeline.register_frame`.【F:services/discord/audio.py†L120-L233】
- **`silero-vad`:**
  - *Pros:* TorchScript models deliver robust noise handling, per-frame speech probabilities, and
    ready-to-use segment generators suitable for Discord voice quality.
  - *Cons:* Introduces PyTorch dependency and optional GPU acceleration, increasing deployment
    footprint relative to the current numpy-only implementation.
  - *Tradeoffs:* Higher accuracy at the cost of model downloads and slightly more compute.
- **`pyannote.audio`:**
  - *Pros:* Offers pre-trained diarization/VAD pipelines with speaker change detection that could
    simplify multi-user channel handling.
  - *Cons:* Heavyweight dependency (PyTorch, pretrained checkpoints) and may exceed latency targets
    for real-time Discord streaming.
  - *Tradeoffs:* Rich features versus operational complexity.
- **Recommendation:** Adopt `silero-vad` if GPU/CPU resources permit for better wake responsiveness;
  otherwise continue tuning the WebRTC VAD parameters for a lightweight improvement.

- **Current state:** Audio segments are screened with `openwakeword` models before falling back to
  regex-based transcript checks, improving resilience to noisy environments while retaining text
  matching as a safety net.【F:services/discord/wake.py†L1-L129】
- **Picovoice Porcupine:**
  - *Pros:* Commercially supported SDK with high accuracy, tiny footprint, and managed model
    updates.
  - *Cons:* Licensing costs for production and closed-source constraints; custom wake words require
    vendor tooling.
  - *Tradeoffs:* Enterprise-grade quality at monetary and licensing costs.
- **Spokestack Wakeword:**
  - *Pros:* Cloud-managed training pipeline and hybrid on-device/inference options with Python SDK.
  - *Cons:* Adds SaaS dependency and ongoing subscription for managed models.
  - *Tradeoffs:* Simplifies custom wake word training while tying availability to vendor services.
- **Recommendation:** Continue tuning `openwakeword` thresholds/models for on-device detection and
  keep Porcupine on the radar if commercial support or additional wake phrases become mandatory.

### MCP / JSON-RPC Server
- **Current state:** The MCP server hand-rolls JSON-RPC parsing, routing, and buffering over stdio,
  including manual tool registration and notification queuing.【F:services/discord/mcp.py†L33-L200】
- **`jsonrpcserver` or `json-rpc`:**
  - *Pros:* Provide request validation, method dispatch, and error handling out of the box while
    remaining lightweight.
  - *Cons:* Primarily HTTP-oriented; adapting to stdio transport may need extra wiring.
  - *Tradeoffs:* Saves boilerplate but might require custom adapters for MCP-specific metadata.
- **`fastapi-jsonrpc`:**
  - *Pros:* Integrates seamlessly with FastAPI, enabling a unified HTTP transport and schema
    validation through Pydantic models.
  - *Cons:* Requires hosting MCP over HTTP/WebSocket instead of stdio, changing deployment
    assumptions.
  - *Tradeoffs:* Gains automatic documentation and validation in exchange for a transport change.
- **`aiohttp-json-rpc`:**
  - *Pros:* Async-native server/client implementation with batching support and middleware hooks.
  - *Cons:* Pulls in the aiohttp stack and still leaves stdio bridging work to you.
  - *Tradeoffs:* Useful if migrating MCP to a socket or HTTP transport; less so for pure stdio.
- **Recommendation:** If MCP transport can shift to HTTP, `fastapi-jsonrpc` aligns with existing
  FastAPI services; otherwise wrap `jsonrpcserver` to reduce error-handling boilerplate while
  keeping stdio.

### Transcription HTTP Client
- **Current state:** The Discord bot now streams multipart uploads through a shared `httpx`
  helper with structured retry logging, eliminating bespoke `aiohttp` form handling while keeping
  WAV conversion local.【F:services/discord/transcription.py†L1-L113】
- **Speech-to-text SDKs (e.g., `assemblyai`, `speech_recognition`):**
  - *Pros:* Offer turnkey upload helpers, streaming, and error semantics targeting speech APIs.
  - *Cons:* Typically assume vendor-specific endpoints; less flexible for your in-house STT server.
  - *Tradeoffs:* Rapid integration if moving to managed STT, but mismatched with bespoke FastAPI
    service.
- **`aiohttp` higher-level helpers (e.g., `aiohttp_retry`):**
  - *Pros:* Minimal change while gaining standardized retry/backoff policies and metrics hooks.
  - *Cons:* Still leaves multipart composition and PCM-to-WAV conversions in local code.
  - *Tradeoffs:* Incremental ergonomics without broader ecosystem switch.
- **Recommendation:** Revisit managed SDKs only if migrating away from the in-house STT service; the
  shared `httpx` helper already centralizes retries and logging for current needs.

## Speech-to-Text Service

### Model Hosting and API Layer
- **Current state:** The FastAPI app lazily imports `WhisperModel`, writes each request to a temp
  WAV, and streams results directly from faster-whisper with optional per-call tuning parameters.【F:services/stt/app.py†L1-L200】
- **`faster-whisper` community REST servers (e.g., `guillaumekln/faster-whisper-server`):**
  - *Pros:* Maintained reference implementations with queueing, batching, and GPU placement handled
    centrally.
  - *Cons:* Less customizable endpoint contract; migrating bespoke query parameters may be tricky.
  - *Tradeoffs:* Operational maturity versus customization flexibility.
- **Hugging Face `transformers` pipeline (`pipeline("automatic-speech-recognition")`):**
  - *Pros:* Broad model catalog (Whisper, Wav2Vec2, etc.) and auto device placement with common
    configs.
  - *Cons:* Higher latency than optimized faster-whisper and larger dependency footprint.
  - *Tradeoffs:* Flexibility in model choice at the expense of performance and resource usage.
- **Cloud STT SDKs (OpenAI Whisper API, Google Speech, Azure Speech):**
  - *Pros:* Managed scalability, diarization/translation features, and SLA-backed availability.
  - *Cons:* Introduces recurring costs, external latency, and data governance concerns.
  - *Tradeoffs:* Operational offloading versus vendor lock-in and privacy considerations.
- **Recommendation:** Stay on self-hosted faster-whisper but track the community server to inherit
  queueing/backpressure logic; consider cloud APIs only for edge cases requiring diarization or
  multilingual guarantees.

## Local LLM Shim

### OpenAI-Compatible Serving
- **Current state:** The service now loads GGUF models directly via `llama-cpp-python`, returning
  chat completions when a model is available and falling back to echoing the latest user message if
  not.【F:services/llm/app.py†L1-L168】
- **`llama-cpp-python` server:**
  - *Pros:* Provides a maintained Python API and an OpenAI-compatible web server with streaming and
    tokenizer management baked in.
  - *Cons:* Requires building C++ bindings and managing GPU/CPU-specific wheels.
  - *Tradeoffs:* Smooth upgrade path from CLI to native API while adding build complexity.
- **`LiteLLM`:**
  - *Pros:* Acts as a router/proxy across many local and hosted backends with caching, cost tracking,
    and OpenAI-compatible schema out of the box.
  - *Cons:* Additional configuration and dependency weight; optimal when juggling multiple models.
  - *Tradeoffs:* Gains multi-backend flexibility at the cost of another orchestration layer.
- **`FastChat` or `vLLM`:**
  - *Pros:* Production-grade serving stacks with batching, quantization support, and streaming Chat
    Completions endpoints.
  - *Cons:* Expect GPU-first deployment and higher resource usage; overkill for small local models.
  - *Tradeoffs:* Excellent throughput if scaling beyond single-user latency requirements.
- **Recommendation:** Keep iterating on the `llama-cpp-python` integration and explore `LiteLLM` or
  `vLLM` if throughput or multi-backend routing requirements emerge.

## Shared Logging Utilities

### Structured Logging Stack
- **Current state:** Logging is centralized around `structlog` with context binding and JSON
  rendering shared across services, replacing the custom adapter/`pythonjsonlogger` stack.【F:services/common/logging.py†L1-L94】
- **`loguru`:**
  - *Pros:* Batteries-included structured logging with sink rotation, serialization, and colorful
    console output.
  - *Cons:* Non-standard API that may clash with libraries expecting stdlib loggers.
  - *Tradeoffs:* Developer-friendly ergonomics versus compatibility concerns.
- **`betterlogging` / `structlog-sugar`:**
  - *Pros:* Thin wrappers around stdlib logging that provide contextual binding and JSON formatting
    with minimal API changes.
  - *Cons:* Smaller ecosystems and less documentation than flagship libraries.
  - *Tradeoffs:* Incremental improvements while keeping the stdlib surface area.
- **Recommendation:** Continue expanding `structlog` processors (e.g., for tracing IDs or sampling)
  before considering heavier alternatives like `loguru`.
