---
title: MCP Tooling Wave 1 Enablement Plan
description: Deliver MCP tooling that unlocks Wave 1 voice-first user journeys across Monday.com sprint planning, GitHub status readouts, and AWS latency triage.
status: proposed
created: 2025-01-27
updated: 2025-01-27
last-updated: 2025-10-11
---

# MCP Tooling Wave 1 Enablement Plan

## Objective

-  Deliver MCP tooling that unlocks Wave 1 voice-first user journeys across Monday.com sprint planning, GitHub status readouts, and AWS latency triage.
-  Ensure the orchestrator can orchestrate read/write actions safely with confirmation prompts, telemetry, and Monday.com-linked accountability trails.

## Success Criteria

-  Discord voice sessions can trigger Monday.com MCP tools that retrieve board context, update items, and record confirmations with owner and due-date metadata.
-  GitHub MCP tools authenticate with repo-scoped tokens, return paginated PR/check-run status, and raise Monday.com follow-ups when blockers persist.
-  AWS observability MCP tools surface latency metrics with guard rails, publish Discord embeds for incidents, and mirror triage activity into Monday.com timelines.
-  Telemetry captures every MCP invocation, response time, and confirmation prompt outcome for audit and regression analysis.

## Scope

-  Services: `services/llm` orchestrator MCP registry, Monday.com/GitHub/AWS tool implementations, Discord voice bot confirmation prompts, Monday.com ledger sync worker.
-  Integrations: Monday.com GraphQL API, GitHub REST/GraphQL APIs, AWS CloudWatch Metrics, Discord text bridge for notifications.
-  Deliverables: MCP manifests, tool implementations, configuration updates, documentation, telemetry dashboards, regression harness updates.

## Constraints & Assumptions

-  OAuth or token management for Monday.com, GitHub, and AWS must reuse existing secrets handling patterns (`.env.sample`, service-specific `.env`).
-  Monday.com remains the source of truth for action ownership; no alternative task system is introduced in Wave 1.
-  Orchestrator continues to run in legacy mode while Redis sandbox matures; MCP tools must support both runtimes via feature flags.
-  AWS access limited to read-only CloudWatch queries during Wave 1 to de-risk credentials and guardrails.

## Workstreams & Requirements

### 1. MCP Platform Foundation

| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Credential propagation | MCP tools lack standardized access to third-party tokens. | Extend `.env.sample`, `.env.docker`, and `services/llm/.env.service` with Monday.com, GitHub, and AWS credentials; document secret provisioning steps. | Contributors can launch tooling locally or in Docker with consistent credential wiring. |
| MCP manifest updates | Discord orchestrator cannot discover new tools. | Update `docs/MCP_MANIFEST.md` and orchestrator registration code to declare Monday, GitHub, AWS tools with input/output schemas and capability tags. | Tooling advertised to clients with accurate schemas and discoverability. |
| Confirmation scaffolding | Voice flows need consistent confirmations for write actions. | Add orchestrator middleware that flags write-intent tools, prompts for verbal confirmation, and records responses in Monday.com ledger metadata. | State-changing requests include safety prompts and auditable outcomes. |
| Telemetry hooks | Lack of MCP observability hides failures. | Emit structured logs and metrics (latency, status codes, retries) for each tool invocation; wire into existing logging/metrics stack. | Teams can trace MCP usage and diagnose regressions quickly. |

### 2. Monday.com Sprint Planning Tools

| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Board discovery | Agent cannot target correct board or workspace. | Implement `monday.board_summary` to list boards filtered by channel context metadata; cache lookups with TTL. | Voice sessions retrieve relevant board context automatically. |
| Item status updates | Manual follow-ups cause drift between Discord and Monday. | Deliver `monday.update_item` that adjusts status, owner, due date, and ensures channel tag metadata persists; include optimistic concurrency checks. | Monday.com reflects latest spoken decisions with traceable ownership. |
| Update logging | Verbal confirmations lack persistent trail. | Implement `monday.create_update` that posts confirmation notes including Discord message references and transcript snippet; link to ledger worker. | Every action leaves an auditable record tied to voice interaction. |
| Ledger synchronization | Monday.com notifiers need canonical state trail. | Extend Monday ledger worker to capture tool request payloads, confirmations, and resulting item snapshots. | Monday.com remains authoritative state ledger for Wave 1 flows. |

### 3. GitHub Status Readouts

| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Authenticated client | Anonymous GitHub calls fail for private repos. | Introduce shared GitHub client with repo-scoped PAT, retry/backoff, and GraphQL pagination helpers. | MCP tools access required GitHub data reliably within rate limits. |
| Pull request listing | Voice agent lacks visibility into active PRs. | Build `github.list_pull_requests` returning status, reviewers, and aging metrics; support filters for repo, branch, and author. | Users receive concise voice summaries of PR queues. |
| Check run inspection | CI health is opaque in voice interface. | Implement `github.get_check_runs` summarizing latest CI statuses, failure reasons, and links; degrade gracefully on API limits. | Agent delivers actionable CI summaries and highlights blockers. |
| Monday follow-up linkage | Outstanding reviews lack accountability. | Automate creation/update of Monday items when PRs have failing checks or pending reviews beyond SLA; include deep links. | Review gaps become tracked work with owners and due dates. |

### 4. AWS Observability Hooks

| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| AWS credential guardrails | Mis-scoped access could compromise environments. | Configure IAM policy limited to CloudWatch `GetMetricData` and `ListMetrics`; document credential rotation cadence. | Observability tooling operates with least privilege and clear maintenance steps. |
| Metric retrieval tool | Voice agent cannot surface latency/health metrics. | Implement `aws.cloudwatch_get_metric` supporting namespace/dimension presets, time windows, and rate limiting; format results for speech and embeds. | Operators receive timely metric snapshots via voice and Discord text. |
| Incident embed pipeline | Metric alerts lack rich context in Discord. | Generate Discord embed payloads summarizing metric anomalies, linked dashboards, and next steps; reuse existing Discord message bridge. | Incident responders see structured context without switching tools. |
| Monday timeline sync | Incident progress not captured centrally. | Extend ledger worker to append incident timeline entries with timestamps, responders, metrics queried, and follow-up tasks. | Monday.com incident timelines stay synchronized with voice-driven actions. |

### 5. Testing, Documentation, and Enablement

| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Regression harness | MCP regressions may ship unnoticed. | Add test fixtures for Monday/GitHub/AWS tool calls with mocked responses; run in CI using feature flags. | Tool behavior validated automatically before release. |
| Operational docs | Contributors lack runbooks for new tools. | Update `README.md`, `docs/operations/mcp-tools.md`, and Monday/AWS/GitHub sections with setup, troubleshooting, and confirmation policies. | Engineers and operators can onboard quickly with clear guidance. |
| Demo scripts | Stakeholders need proof of end-to-end value. | Author sample Discord scripts demonstrating sprint summary, PR status review, and latency snapshot flows. | Wave 1 journeys are reproducible for demos and training. |
| Rollout checklist | Adoption may stall without gating criteria. | Publish checklist covering credential readiness, telemetry review, Monday ledger verification, and fallback instructions. | Teams have clear path to enable tooling confidently. |

## Milestones & Sequencing

| Milestone | Target | Key Deliverables |
| --- | --- | --- |
| M1 — MCP Platform Ready | Week 1 | Credentials propagated, manifest updates, confirmation + telemetry scaffolding |
| M2 — Monday.com Tools Live | Week 2 | Board discovery, item updates, ledger sync |
| M3 — GitHub Status Coverage | Week 3 | PR listing, check run summaries, Monday follow-up automation |
| M4 — AWS Observability Hooks | Week 4 | CloudWatch tool, Discord embeds, Monday timeline sync |
| M5 — Enablement Complete | Week 5 | Regression tests, docs, demo scripts, rollout checklist |

## Risks & Mitigations

-  **Credential sprawl**: Secrets might diverge across environments. → Centralize in `.env.sample` and document rotation via vault integration.
-  **API rate limits**: High-frequency polling could throttle tools. → Add caching, exponential backoff, and alerting when limits approach thresholds.
-  **Voice confirmation fatigue**: Excess prompts could slow workflows. → Batch confirmations per session and allow opt-in bypass for read-only tools.
-  **Schema drift**: Monday/GitHub API changes could break tooling. → Monitor changelogs and add schema validation tests in CI.

## Exit Criteria

-  Voice-driven Monday.com sprint updates, GitHub status summaries, and AWS metric snapshots complete end-to-end with confirmations recorded in Monday.com ledger entries.
-  Telemetry dashboards demonstrate tool latency under target thresholds and zero unhandled errors across a week of regression runs.
-  Documentation, demo scripts, and rollout checklist reviewed and signed off by platform lead before enabling tools for broader team.
