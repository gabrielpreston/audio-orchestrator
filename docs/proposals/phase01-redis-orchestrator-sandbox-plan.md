# Redis-Orchestrator Sandbox Rollout Plan

## Objective
- Deliver a Redis-backed orchestrator sandbox capable of replaying Discord event traffic
  through the adaptive runtime prior to production rollout.
- Establish telemetry and parity ledger foundations so replay sessions capture state deltas,
  outcomes, and reliability metrics aligned with the target production behavior.

## Success Criteria
- Docker Compose (or Makefile) target provisions Redis, orchestrator, and telemetry exporters
  in an isolated sandbox environment using repository-standard configuration files.
- Discord capture pipeline can inject previously recorded traffic or live-mirrored events into
  the sandbox without impacting production Discord sessions.
- Parity ledger persists orchestrator inputs/outputs and Redis state transitions for at least
  48 hours, enabling diff analysis against production behavior.
- Telemetry dashboards expose key lagging and leading indicators (latency, queue depth,
  tool invocation success rates) to validate replay fidelity.

## Scope
- Services: `services/llm` orchestrator runtime, Redis broker/cache, telemetry exporters,
  Discord ingestion tooling for replay, parity ledger process (likely Python worker).
- Environments: Local Docker Compose sandbox and CI smoke tests validating Redis migrations
  and health checks.
- Deliverables: Infrastructure manifests, configuration docs, operational runbooks,
  automated smoke tests, initial dashboards.

## Constraints & Assumptions
- Redis will be the canonical store for session state and replay buffers; no alternative
  persistence layer is in scope for this milestone.
- Discord traffic is replayed from stored PCM/transcript artifacts captured via existing
  Discord bot instrumentation or synthetic fixtures.
- Telemetry stack reuses existing observability tooling (e.g., Prometheus exporters,
  structlog JSON logs) with minimal new dependencies.
- Monday.com integration is out of scope until the ledger proves accurate within the sandbox.

## Workstreams & Tasks

### 1. Sandbox Infrastructure
| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Provision Redis sandbox | The orchestrator cannot exercise Redis-backed flows locally, preventing parity testing. | Add Redis service definition to `docker-compose.yml`, persist data via volume mounts, and publish metrics through `redis_exporter`. | Local sandbox offers durable Redis storage and visibility for orchestrator experiments. |
| Propagate configuration | Redis credentials and endpoints are missing from environment defaults, breaking service boot. | Update `.env.sample`, `.env.docker`, and orchestrator `.env.service` with host, port, password, and TLS flags. | Contributors can launch the sandbox without hand-editing env files and avoid configuration drift. |
| Unified launch workflow | Engineers manually orchestrate containers, causing inconsistent setups. | Create Makefile target (e.g., `make run-sandbox`) that starts Redis, orchestrator, and telemetry exporters; document usage in `README.md` and `docs/operations/sandbox.md`. | One command reproducibly brings up the sandbox with validated documentation. |
| Redis health assurance | Orchestrator failures go undetected until runtime when Redis is unreachable. | Implement startup health checks and retry logic within `services/llm`, surfacing structured errors if Redis is offline or misconfigured. | Orchestrator detects Redis availability issues early and logs actionable diagnostics. |

### 2. Orchestrator Redis Integration
| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Redis data model | Lack of agreed-upon key structure makes replay state inconsistent. | Design schema for session state, tool queues, and replay buffers; codify TTLs and naming conventions in docs. | All components write/read Redis data consistently, enabling deterministic replays. |
| Shared Redis client | Duplicate Redis connections create drift and impede observability. | Build reusable client module under `services/common` with connection pooling, tracing, and metrics hooks. | Services adopt a single client abstraction, gaining uniform telemetry and configuration. |
| Adaptive runtime wiring | Orchestrator currently bypasses Redis, so sandbox parity cannot be evaluated. | Integrate Redis client into adaptive runtime for state caching and workflow coordination guarded by sandbox feature flags. | Sandbox traffic exercises Redis-backed logic without impacting production flows. |
| Test coverage | Redis regressions could ship undetected. | Add unit/integration tests for Redis operations (set/get, pipelines, failure modes) and run them in CI. | CI enforces Redis contract fidelity before release. |

### 3. Telemetry & Observability
| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Metrics instrumentation | Redis usage lacks visibility, hindering capacity planning. | Emit Prometheus metrics for command rates, latency, and errors; add correlation IDs and Redis context to structlog events. | Operators can quantify Redis load and trace replay flows end to end. |
| Dashboard coverage | Teams cannot inspect sandbox health at a glance. | Provision Grafana (or JSON dashboards) charting orchestrator latency, Redis queue depth, and replay throughput. | Stakeholders monitor sandbox reliability via curated dashboards. |
| Log policy | Replay logs may overwhelm storage or omit crucial context. | Document log sampling/retention guidance and configure filters for sandbox sessions. | Logs remain actionable while keeping volume manageable. |
| Alerting runbook | Failures lack standardized triage steps. | Publish runbook entries detailing alert thresholds, escalation, and remediation workflows. | On-call responders resolve sandbox incidents quickly using documented playbooks. |

### 4. Parity Ledger Implementation
| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Ledger schema | Without a canonical schema, parity comparisons are ad hoc and incomplete. | Define schema capturing Discord metadata, orchestrator decisions, tool responses, and Redis state snapshots; select storage (Postgres/S3/append-only JSON) and document retention. | Ledger captures consistent replay records suited for diff analysis. |
| Recording pipeline | Replay events are not persisted, so parity drift cannot be investigated. | Build writer component (worker or orchestrator plugin) logging interactions with timestamps and correlation IDs. | Every replay session yields auditable records tied to input events. |
| Diff tooling | Manual comparison of sandbox vs. production is error-prone. | Implement tooling to compare ledger entries against production logs, flagging divergences in API responses, tool success, and latency. | Teams can quantify drift quickly and prioritize fixes. |
| Data governance | Ledger data may accumulate indefinitely or violate access policies. | Establish retention windows, access controls, and scrubbing/anonymization processes for stored artifacts. | Ledger remains compliant and maintainable over time. |

### 5. Replay Harness & Validation
| Requirement | Problem Being Solved | Implementation Details | Expected Outcome |
| --- | --- | --- | --- |
| Replay bundle export | Sandbox lacks reusable Discord sessions for regression testing. | Enhance Discord bot to package audio chunks, transcripts, and metadata into structured bundles (JSON manifest + blobs). | Engineers can capture and share canonical replay datasets. |
| Replay runner | No automated way exists to push bundles through the sandbox. | Develop CLI/service that feeds bundles into Redis queues, tracking completion and errors. | Replay jobs execute reproducibly and surface orchestration failures. |
| Acceptance criteria | Success metrics for replays are undefined. | Publish validation matrix covering happy paths, degraded STT, and tool failures with expected ledger outputs. | Teams know how to judge replay success and identify deviations. |
| Continuous validation | Sandbox may drift without ongoing checks. | Schedule nightly replay job using sample bundles and report results to telemetry/ledger dashboards. | Sandbox freshness is maintained and regressions are detected promptly. |

## Milestones & Sequencing
| Milestone | Target | Key Deliverables |
| --- | --- | --- |
| M1 — Sandbox Bootstrap | Week 1 | Compose/Makefile updates, Redis health checks, basic telemetry |
| M2 — Redis Runtime Integration | Week 2 | Redis schema, orchestrator integration, tests |
| M3 — Telemetry Dashboards | Week 3 | Metrics exporters, dashboards, runbooks |
| M4 — Parity Ledger MVP | Week 4 | Ledger schema, writer, storage automation |
| M5 — Replay Automation | Week 5 | Replay harness, validation matrix, nightly job |

## Risks & Mitigations
- **Redis resource contention**: Sandbox may require memory tuning; configure resource limits
  and eviction policies, and document scaling thresholds.
- **Replay data privacy**: Ensure captured Discord content is sanitized and access-restricted;
  introduce anonymization for external contributors.
- **Telemetry overhead**: Metrics collection could increase latency; sample selectively and
  benchmark before enabling in production.
- **Ledger divergence noise**: False positives may emerge; calibrate diff tooling with tolerance
  thresholds and whitelist acceptable variances.

## Exit Criteria
- Replay harness demonstrates parity within ±5% latency and success variance compared to
  production runs for at least three representative Discord sessions.
- Telemetry dashboards and parity ledger reports are reviewed and signed off by the platform
  lead prior to enabling production traffic routing through the adaptive runtime.
- Documentation updated with operational runbooks, configuration references, and troubleshooting
  guidance for the sandbox environment.
