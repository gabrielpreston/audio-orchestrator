# Monday.com State Ledger and Capability Registry Plan

## Objective
- Build a Monday.com-linked state ledger and capability registry that keep cross-surface workflows
  synchronized on ownership, status, and available execution tools.
- Ensure Discord voice journeys, MCP tooling, and Redis sandbox runtimes can rely on the ledger for
  persistent accountability and on the registry for tooling coverage before production rollout.

## Success Criteria
- Voice and MCP-triggered actions automatically create or update Monday.com items with current owner,
  due date, status, and escalation metadata.
- Capability registry reflects the available tooling per workflow (Discord voice, MCP, Cursor/local),
  including health, latency, and fallback options.
- Ledger exposes APIs or events that downstream services (Discord bot, orchestrator, telemetry
  dashboards) can query to reconcile workflow state.
- Telemetry dashboards provide parity views of ledger updates and capability registry health across
  Redis sandbox and legacy runtimes with no unresolved discrepancies for a full regression week.

## Scope
- Services: Monday ledger worker, `services/llm` orchestrator, `services/discord` prompts, Redis
  sandbox instrumentation, documentation under `docs/`.
- Integrations: Monday.com GraphQL API, Discord webhooks/messages, MCP tooling catalog, capability
  registry persistence (Redis or database).
- Deliverables: Ledger schema definitions, synchronization jobs, registry service/module, API
  documentation, telemetry dashboards, rollout checklist, regression harness updates.

## Constraints & Assumptions
- Monday.com remains the canonical source of truth; external replicas (Redis, caches) must reconcile
  back to Monday before closing workflows.
- Capability registry should operate in-memory with optional Redis persistence to match sandbox
  architecture while supporting a file-backed fallback for local development.
- Ledger and registry must function when orchestrator runs in either legacy or Redis sandbox modes;
  feature flags will control advanced behaviors until parity sign-off.
- Monday.com API rate limits require batching and retry/backoff strategies aligned with existing HTTP
  helper utilities.

## Workstreams & Requirements

### 1. Ledger Architecture & Data Modeling
| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Canonical schema | Current workflows lack a normalized record of intent, owner, and due dates. | Design Monday item schema (groups, columns, tags) for workflow ledger; document in `docs/operations/monday-ledger.md`. | Every voice/MCP workflow maps to a predictable Monday structure with required accountability fields. |
| State transitions | Ledger updates are ad hoc and inconsistent across surfaces. | Define status taxonomy (requested, in-progress, blocked, done) with automation recipes; enforce via orchestrator helper. | All workflows progress through consistent states that downstream systems can interpret. |
| API facade | Services need a stable way to query/update ledger state. | Build orchestrator ledger client exposing CRUD helpers, using shared HTTP retries and schema validation. | Discord bot and MCP tools interact with ledger via consistent, typed helper functions. |
| Data retention | Historical actions need traceable archives. | Configure Monday board archives or mirrored storage for closed items; add purge policy documentation. | Teams can audit past workflows without bloating active boards. |

### 2. Monday.com Synchronization & Automation
| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Ingestion pipeline | Voice actions may not reach Monday ledger reliably. | Implement worker consuming orchestrator events (webhook or queue) and reconciling Monday updates with idempotency keys. | All actions produce ledger entries even if transient failures occur. |
| Bi-directional sync | Manual Monday updates don't reflect back into orchestrator context. | Poll or subscribe to Monday webhooks; update Redis/local caches and Discord prompts when status/owner changes. | Voice flows stay aware of latest Monday state and notify channels of changes. |
| Escalation rules | Overdue items lack automated reminders. | Encode SLA policies (due date drift, blocked duration) that create Discord alerts and Monday subitems for follow-up. | Unattended tasks trigger timely reminders and escalation workflows. |
| Privacy & permissions | Sensitive boards require scoped access. | Use board-specific tokens/permissions and document least-privilege setup in `.env.sample` and ops guide. | Ledger worker operates with minimal necessary access and clear rotation steps. |

### 3. Capability Registry Foundation
| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Registry schema | Orchestrator lacks visibility into available execution surfaces. | Define registry schema capturing workflow, tool surface, health, latency, feature flags; persist in Redis + file fallback. | Agent can select appropriate tooling based on real-time capability data. |
| Health monitoring | Tool outages go undetected. | Integrate periodic health checks leveraging existing telemetry; update registry status and surface alerts in Discord/Monday. | Registry reflects live availability, guiding fallback decisions automatically. |
| Selection logic | No deterministic mapping from workflow to tool. | Implement orchestrator strategy module that ranks tools by capability/health, logs decisions, and records fallback rationale in ledger. | Voice journeys consistently choose best-fit tooling with auditable reasoning. |
| Registry management API | Operators cannot adjust registry without code deploys. | Provide CLI/HTTP admin endpoints secured via feature flags for manual overrides (e.g., disable Cursor). | Operations can adjust tooling coverage quickly during incidents. |

### 4. Cross-Surface Workflow Integration
| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Discord prompts | Users need visibility into ledger and registry state. | Update Discord bot to announce ledger updates, tooling availability, and escalation notices via embeds or follow-up messages. | Participants stay informed about ownership changes and tooling status in real time. |
| Replay compatibility | Redis sandbox must validate ledger/registry flows. | Extend replay harness to include ledger and registry events; compare against legacy baseline reports. | Sandbox proves parity before enabling registry-driven tooling selection in production. |
| Documentation alignment | Contributors lack guidance on new workflows. | Update roadmap, README, and operations docs with ledger/registry usage patterns and troubleshooting. | Teams onboard quickly with clear instructions across surfaces. |
| Security review | New data flows require compliance checks. | Conduct lightweight security review covering Monday scopes, data residency, and audit logging; record findings in proposal appendix. | Stakeholders sign off on ledger/registry launch with documented mitigations. |

### 5. Telemetry, Testing, and Enablement
| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Telemetry dashboards | Hard to assess ledger/registry health. | Instrument structured logs/metrics (success rates, latency, escalations) and build Grafana or equivalent dashboards. | Operators monitor system health and spot regressions quickly. |
| Regression harness | Changes risk breaking safety workflows. | Add CI tests simulating ledger updates, registry selection, and failover paths using mocked Monday/Discord responses. | Automated checks catch regressions prior to deployment. |
| Runbooks & training | Teams need repeatable rollout steps. | Publish runbook covering setup, SLA policies, registry overrides, and rollback procedures; add demo scripts for key journeys. | Rollout proceeds smoothly with shared understanding across teams. |
| Launch checklist | Adoption may stall without gating criteria. | Create checklist ensuring schema migration, telemetry readiness, replay parity, and stakeholder sign-offs before enabling globally. | Decision-makers know when ledger/registry are production-ready. |

## Milestones & Sequencing
| Milestone | Target | Key Deliverables |
| --- | --- | --- |
| M1 — Ledger Schema Finalized | Week 1 | Canonical Monday schema, status taxonomy, API facade |
| M2 — Synchronization Online | Week 2 | Event ingestion, bi-directional sync, escalation rules |
| M3 — Capability Registry Ready | Week 3 | Registry schema, health monitoring, selection logic |
| M4 — Cross-Surface Integration | Week 4 | Discord prompts, replay parity, security review |
| M5 — Enablement Complete | Week 5 | Telemetry dashboards, regression harness, rollout checklist |

## Risks & Mitigations
- **Monday API constraints**: Rate limits or schema changes could delay sync jobs. → Implement caching,
  backoff, and schema validation tests; monitor Monday changelog.
- **Data drift between runtimes**: Legacy and sandbox paths may diverge. → Use replay parity reports
  and shared clients to keep behaviors aligned before rollout.
- **Tooling availability gaps**: Registry may expose missing coverage. → Establish manual override
  process and prioritize backlog items surfaced by registry health alerts.
- **Security/compliance gaps**: New data retention policies may be required. → Engage security review
  early and document data flows with mitigation steps.

## Exit Criteria
- Monday.com ledger reflects every orchestrated workflow with accurate ownership, status, due dates,
  and escalation trails updated automatically from voice/MCP interactions.
- Capability registry drives tooling selection for Redis sandbox and legacy runtimes with telemetry
  confirming healthy fallback behavior and no unresolved parity gaps for one regression week.
- Discord prompts, documentation, and runbooks keep teams informed about ledger updates, tooling
  status, and escalation actions with auditable history in Monday.com.
- Rollout checklist completed with security sign-off, replay parity reports, and dashboard coverage
  reviewed by platform leadership.
