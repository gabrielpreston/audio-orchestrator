# Proposal: Capturing `openai-agents-python` Capabilities Without Adopting the Library

## Summary

- Isolate the library features that materially advance Discord Voice Lab’s roadmap—threaded
  context, tool orchestration, event streaming, and recovery semantics.
  【F:docs/ROADMAP.md†L16-L118】
- Map those capabilities to current service responsibilities so we can target gaps without
  depending on `openai-agents-python`.
  【F:README.md†L9-L53】【F:services/llm/app.py†L1-L217】
- Present alternative implementation strategies using established Python components already
  present in, or compatible with, the stack.

## Project needs recap

The platform must maintain voice-driven workflows that span Discord, Monday.com, GitHub, and AWS
while preserving low-latency transcription, persona-consistent orchestration, and MCP tool
interoperability.
【F:docs/ROADMAP.md†L16-L118】
Key responsibilities for the orchestrator service are:

- Expose an OpenAI-compatible chat endpoint that the Discord bot already targets, including JSON
  payload structures with streaming deltas and optional audio attachments.
  【F:services/llm/app.py†L1-L217】
- Marshal MCP tool calls for external systems while logging correlation metadata through the shared
  utilities package.
  【F:README.md†L17-L53】【F:services/llm/app.py†L55-L150】
- Sustain fallback strategies so deployments without managed connectivity can continue using the
  local `llama_cpp` inference stack.
  【F:README.md†L17-L53】

## Capabilities from `openai-agents-python` that would benefit the project

- **Threaded conversations**
  - Benefit: Centralized history keeps Discord and MCP sessions consistent across turns.
    【F:docs/ROADMAP.md†L43-L118】
  - Considerations: Map channel IDs to thread IDs and prune history according to retention rules.
- **Tool scheduling and invocation**
  - Benefit: Declarative definitions mirror MCP schemas and trim boilerplate for GitHub, Monday,
    or AWS tasks.
  - Considerations: Library expects OpenAI Agents contracts; bridging to MCP clients adds glue
    code.
- **Structured streaming events**
  - Benefit: Granular deltas and tool notices align with Discord TTS timing and progress updates.
    【F:services/llm/app.py†L85-L206】
  - Considerations: Discord payloads use OpenAI-style `choices`, so events must be reshaped before
    forwarding.
- **Thread recovery and continuation**
  - Benefit: Resume logic prevents replaying full transcripts during retries, boosting resilience.
    【F:docs/ROADMAP.md†L62-L118】
  - Considerations: Requires external availability, clashing with offline requirements.

These features illuminate functional gaps in today’s orchestrator even if the hosted runtime is not adopted outright.

## Why the library is not a direct fit

1. **Hosted dependency** — The managed runtime would introduce an external availability and data
   residency dependency that conflicts with the roadmap’s offline and fallback objectives.
   【F:README.md†L17-L53】
2. **Protocol impedance** — Discord integrations consume OpenAI-compatible responses; translating
   granular Agent events adds maintenance cost without delivering unique value over bespoke
   streaming enhancements.
   【F:services/llm/app.py†L85-L206】
3. **Observability gaps** — Success metrics in the roadmap (parity ledgers, transcript replays,
   regression harnesses) would still need custom instrumentation, reducing the benefit of adopting
   the library wholesale.
   【F:docs/ROADMAP.md†L62-L118】

The priority is therefore to reproduce the useful features using components that align with the existing deployment and compliance boundaries.

## Implementation pathways with well-supported Python components

### Option A — Reinforce the current FastAPI orchestrator with Redis and OpenTelemetry

- **Context store**: Use Redis (already standard in many Python stacks) or PostgreSQL to persist
  per-channel dialogue state and tool artifacts, providing the thread continuity showcased by the
  library.
- **Streaming envelope**: Extend the existing SSE or chunked-response logic in
  `services/llm/app.py` to emit structured progress events, instrumented with OpenTelemetry spans
  for parity ledgers and regression capture.
  【F:services/llm/app.py†L85-L206】【F:docs/ROADMAP.md†L62-L118】
- **Retry and recovery**: Leverage `tenacity` or similar retry helpers to resume tool executions
  and regenerate responses after transient failures, mirroring the library’s continuation
  semantics.
- **Telemetry**: Export metrics and traces through `opentelemetry-sdk`, aligning with the
  roadmap’s observability goals without tying into a proprietary event format.
  【F:docs/ROADMAP.md†L62-L118】

### Option B — Adopt LangChain Runnable or LlamaIndex agent primitives for tool orchestration

- **Tool registry**: Define tools via LangChain’s Runnable interfaces or LlamaIndex tool
  abstractions, gaining schema validation, parallel execution, and structured output enforcement.
- **Memory modules**: Utilize built-in conversation memory classes to capture channel-specific
  context, storing serialized state in Redis or the existing database layer to achieve thread
  semantics.
- **Execution control**: Combine these frameworks with `asyncio` queues to orchestrate multi-step
  reasoning while preserving compatibility with the OpenAI-format responses expected by the
  Discord bot.
  【F:services/llm/app.py†L1-L217】
- **Community support**: Both ecosystems are actively maintained, integrate with FastAPI, and offer
  adapters for OpenAI-compatible APIs, reducing bespoke glue code compared with the Agents library.

### Option C — Introduce a Celery or Dramatiq task backbone for tool execution and resilience

- **Task offloading**: Route long-running MCP actions through Celery or Dramatiq workers, allowing
  the orchestrator to stream interim status updates akin to the Agents event protocol.
- **Result backend**: Persist results in Redis or SQL backends, enabling the orchestrator to resume
  conversations or replay tool outputs without re-executing expensive calls.
  【F:docs/ROADMAP.md†L62-L118】
- **Failure handling**: Built-in retries, circuit breakers, and monitoring dashboards deliver the
  recovery semantics observed in `openai-agents-python` while staying within the project’s
  deployment footprint.

### Option D — Formalize a pluggable backend interface inside `services/llm`

- **Backend contract**: Define a Python protocol or abstract base class for chat completion
  backends (`LocalLlamaBackend`, `ExternalAPIBackend`, `LangChainBackend`), enabling parity testing
  and feature flags without coupling to a single vendor.
  【F:services/llm/app.py†L55-L206】
- **Parity harness**: Reuse the roadmap’s planned regression ledgers to replay captured Discord
  transcripts through each backend, quantifying differences and guiding further enhancements.
  【F:docs/ROADMAP.md†L62-L118】
- **Future flexibility**: Once the parity envelope exists, integrating alternative hosted services
  (including Agents) becomes a configuration exercise instead of a rewrite.

## Recommended course

Prioritize Option A to close immediate gaps in streaming fidelity, context retention, and
observability while staying within the existing FastAPI footprint. Layer Option D in parallel so
new backends can be trialed safely. Evaluate LangChain/LlamaIndex (Option B) or a task queue
backbone (Option C) selectively for workflows that demand deeper planning or retries than the core
service currently provides.

## Success indicators

- Discord interactions maintain sub-2 s response times while streaming intermediate tool progress and final answers in the familiar OpenAI payload structure.【F:services/llm/app.py†L85-L206】
- Regression ledgers and transcript replays show parity across backends, supporting the roadmap’s validation gates.【F:docs/ROADMAP.md†L62-L118】
- Observability dashboards capture per-thread metrics, tool latencies, and retry counts without relying on hosted infrastructure.【F:README.md†L17-L53】

## Open questions

1. Which datastore (Redis vs. PostgreSQL) best balances latency, durability, and existing operational tooling for conversation state?【F:docs/ROADMAP.md†L62-L118】
2. Do specific MCP tools require long-running orchestration that would benefit more from a task queue (Option C) than synchronous execution inside FastAPI?

   **Answer:** Most planned MCP tools finish within the FastAPI request window—Monday.com item
   updates, board summaries, and GitHub metadata fetches typically settle within a few seconds and
   can stream results directly back to Discord without exhausting worker capacity.
   【F:docs/proposals/discord-voice-mcp-user-journeys.md†L17-L118】

   Option C becomes valuable for AWS-heavy workflows and composite release checklists because they
   chain remote operations that each consume tens of seconds.
   【F:docs/proposals/discord-voice-mcp-user-journeys.md†L142-L253】
   Examples include:
   - CloudWatch metric scrapes that await stabilization before reporting.
   - Auto Scaling adjustments that require follow-up verification.
   - SSM run commands or CloudFormation validations that block until infrastructure converges.

   Offloading those steps to Celery or Dramatiq workers keeps the orchestrator responsive while
   background tasks poll for completion and emit progress events. The FastAPI layer can then stream
   task-status deltas without holding the original request open for minutes at a time.
3. What guardrails are necessary to keep optional hosted integrations (Agents or otherwise) from conflicting with the offline fallback mandated in the roadmap?【F:README.md†L17-L53】
