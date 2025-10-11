# Structured Intent, Memory, and Confirmation Safeguards Plan

## Objective

- Introduce structured intent schemas, short-term conversation memory, and confirmation heuristics so
  the orchestrator validates user goals before performing write actions against external systems.
- Ensure safety scaffolding works across both the legacy orchestrator runtime and the Redis-backed
  sandbox so adoption can progress without regressions.

## Success Criteria

- Voice transcripts map into intent objects that classify read vs. write actions, target systems,
  confidence, and required confirmations.
- Short-term memory preserves referenced entities (tasks, PRs, incidents) across turns with decay
  rules and manual reset hooks.
- Write-intent MCP tools require confirmation, log outcome metadata, and provide overridable
  safeguards for trusted flows.
- Telemetry captures every intent evaluation, memory read/write, and confirmation outcome for audit
  and rollback decisions.

## Scope

- Services: `services/llm` orchestrator, `services/discord` voice bot confirmation prompts,
  Monday.com ledger worker, Redis sandbox runtime.
- Integrations: Monday.com state ledger, GitHub MCP tools, AWS observability hooks, Discord text
  bridges for confirmations.
- Deliverables: intent schema definitions, memory storage modules, confirmation middleware,
  configuration updates, telemetry dashboards, documentation, regression harness extensions.

## Constraints & Assumptions

- Redis sandbox remains optional until parity sign-off; new components must run in-process when Redis
  is disabled.
- Monday.com continues as the canonical audit ledger for actions; confirmation logs replicate there.
- Confirmation heuristics must support both voice prompts and Discord text fallback for
  accessibility.
- Intent schemas should align with MCP manifest metadata to avoid duplication and schema drift.

## Workstreams & Requirements

### 1. Intent Schema Modeling

| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Intent taxonomy | Current orchestrator reasons in free-form text, making safety checks unreliable. | Define JSON schema capturing action type, target system, operation (read/write), confidence, entities, and required confirmations; store in `services/llm/intent_schema.py`. | All requests emit structured intents that downstream components can validate deterministically. |
| Parser implementation | LLM outputs lack structured guarantees. | Add parser that converts model reasoning into the schema using constrained decoding or schema-enforced prompts; include fallbacks when validation fails. | Intent objects validate automatically, falling back to clarification prompts on schema errors. |
| Schema governance | Schemas may diverge from MCP tool definitions. | Generate intent-to-tool mapping doc from source, add CI check ensuring tool manifests declare expected intent types. | MCP registry stays synchronized with intent definitions, preventing drift. |
| Configurability | Different environments require tuned confidence thresholds. | Expose thresholds and feature flags through `.env.sample`, `.env.docker`, and service env files; document defaults. | Operators adjust sensitivity without code changes. |

### 2. Short-Term Memory Layer

| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Memory store abstraction | Context references vanish between turns. | Implement memory interface supporting in-memory and Redis backends; store conversation entities keyed by session/channel. | Agent recalls referenced entities across turns irrespective of runtime. |
| Entity extraction | Agent lacks canonical entity identifiers. | Extend intent parser to emit normalized entity descriptors (IDs, names, timestamps) and persist them in memory store with TTL. | Memory captures actionable entities with expiry rules to avoid stale data. |
| Reset controls | Users need to clear stale context. | Add voice/text command (`reset context`) routed through orchestrator to purge memory and confirm success. | Participants can manually clear memory when context shifts. |
| Monday.com ledger sync | Memory updates not logged for audit. | Mirror memory writes tied to Monday.com items into ledger metadata for traceability. | Ledger reflects context references, aiding audits and follow-ups. |

### 3. Confirmation Heuristics & Safeguards

| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Write-action gating | Write tools can run without validation. | Tag MCP tools with required confirmation levels; orchestrator checks intent + tool metadata before execution. | State-changing actions pause until confirmation completes. |
| Multi-channel prompts | Voice-only confirmations limit accessibility. | Add Discord text prompt fallback with buttons or keyword replies; log responses with timestamps. | Users confirm actions via voice or text, with consistent audit trails. |
| Heuristic tuning | Over-confirmation slows workflows. | Implement dynamic heuristics based on entity risk (e.g., production repos) and user trust levels; support policy configuration. | Confirmation prompts trigger only when risk warrants it, reducing fatigue. |
| Failure handling | Declined or timed-out confirmations lack escalation. | Route declined/timeouts to Monday.com follow-up tasks with owner/due date; notify Discord channel. | Unconfirmed actions become trackable tasks instead of silent failures. |

### 4. Toolchain & Telemetry Integration

| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Legacy runtime compatibility | Redis sandbox features must not break legacy path. | Implement feature flags ensuring intent, memory, and confirmations operate in both runtimes; add regression fixtures covering both. | New safeguards coexist with current orchestrator until rollout completes. |
| Telemetry instrumentation | Safety events lack observability. | Emit structured logs + metrics for intent parsing latency, memory hits/misses, confirmation outcomes; integrate with existing dashboards. | Teams monitor safety performance and investigate anomalies quickly. |
| Discord UX alignment | Confirmation prompts need consistent copy. | Update Discord bot templates for confirmations, timeouts, and declines; provide localization hooks for future expansion. | End-users experience uniform confirmation messaging across workflows. |
| Config propagation | Missing env keys break deployments. | Update `.env.sample`, `.env.docker`, and service `.env` files with new flags; document changes in README and ops guides. | Deployments start with correct configuration across environments. |

### 5. Testing, Documentation, and Enablement

| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Regression harness updates | Safety regressions could ship unnoticed. | Add unit/integration tests for intent validation, memory persistence, confirmation flows; run in CI for both runtimes. | Automated checks block regressions before release. |
| Scenario scripts | Stakeholders need reproducible demos. | Author demo scripts showcasing structured intents, memory carry-over, and confirmation handling for Monday/GitHub/AWS flows. | Teams can validate safeguards end-to-end during reviews. |
| Operational documentation | Operators require guidance on policies. | Update roadmap, README, and ops docs with configuration, troubleshooting, and escalation procedures. | Contributors onboard quickly with clear safety guidelines. |
| Rollout checklist | Adoption may stall without gating criteria. | Publish checklist covering schema validation, memory accuracy, confirmation telemetry, and ledger reconciliation. | Teams know when safeguards are ready for production use. |

## Milestones & Sequencing

| Milestone | Target | Key Deliverables |
| --- | --- | --- |
| M1 — Intent Schema Baseline | Week 1 | Intent taxonomy, parser, configuration flags |
| M2 — Memory Layer Ready | Week 2 | Memory store abstraction, entity extraction, reset controls |
| M3 — Confirmation Gating Enabled | Week 3 | Tool tagging, multi-channel prompts, heuristic tuning |
| M4 — Toolchain & Telemetry Integrated | Week 4 | Runtime flags, telemetry dashboards, Discord UX updates |
| M5 — Enablement Sign-off | Week 5 | Tests, documentation, rollout checklist |

## Risks & Mitigations

- **Model misclassification**: LLM may mislabel intent types. → Add deterministic rules for
  high-risk tools and require manual review for low-confidence outputs.
- **Memory staleness**: Entities could linger past relevance. → Apply TTL decay, user reset commands,
  and ledger auditing to detect stale context.
- **Confirmation fatigue**: Too many prompts slow workflows. → Tune heuristics per risk level and
  allow trusted personas to bypass after audit approval.
- **Dual-runtime drift**: Legacy and Redis paths may diverge. → Maintain shared test suites and
  parity dashboards to catch behavioral differences.

## Exit Criteria

- Structured intents drive all MCP tool selections with confidence metrics and logged outcomes.
- Memory-backed conversations resolve entity references accurately across at least three-turn flows
  in both runtimes with parity telemetry.
- Write actions across Monday.com, GitHub, and AWS require confirmations with auditable trails in
  Discord and Monday.com, including declined/time-out escalations.
- Documentation, demos, and rollout checklists reviewed by platform owners, with telemetry
  dashboards showing no unhandled errors across a week of regression runs.
