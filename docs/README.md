---
title: Documentation Hub
author: Audio Orchestrator Team
status: active
last-updated: 2025-10-16
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Index

# Audio Orchestrator Documentation Hub

This hub orients contributors, operators, and integrators around the voice-first Discord
assistant. Use the navigation table to jump into onboarding, architecture, operations,
and reference content aligned with the current repository layout.

## Navigation

| Lifecycle Phase | Start Here | Highlights |
| --- | --- | --- |
| Evaluate the project | [Project overview](../README.md) | Goals, stack summary, quickstart. |
| Onboard & configure | [Getting started index](getting-started/README.md) | Environment setup, local workflows, troubleshooting. |
| Understand the system | [Architecture overview](architecture/system-overview.md) | Service relationships, audio and transcript flows. |
| Base images | [Base image architecture](architecture/base-images.md) | Base image strategy, service mapping, optimization. |
| Build optimization | [Build optimization guide](operations/build-optimization.md) | Performance tuning, caching, wheel management. |
| Shared utilities | [Shared utilities](architecture/shared-utilities.md) | Common libraries, configuration, debug management. |
| Operate the stack | [Operations landing page](operations/README.md) | Runbooks, observability, security posture. |
| Extend & integrate | [Reference catalog](reference/configuration-catalog.md) | Environment variables, API endpoints, manifests. |
| Access services | [Service URLs Reference](reference/service-urls.md) | Complete list of all browser-accessible service URLs. |
| Scripts & tools | [Scripts reference](reference/scripts-reference.md) | Utility scripts, maintenance procedures. |
| Track strategy | [Roadmap index](roadmaps/README.md) | Active plans, historical revisions. |
| Review research | [Reports index](reports/README.md) | Implementation notes, evaluation findings. |
| Propose changes | [Proposal index](proposals/README.md) | Submission rules, lifecycle states. |

## CI/CD Workflows

-  **Multi-workflow Architecture**: Specialized workflows for different change types
-  **Fast Feedback**: Python changes complete in ~5-10 minutes
-  **Parallel Execution**: Independent workflows run simultaneously
-  **Workflow-aware Auto-fix**: Targeted analysis and fixes per workflow type

## Version History

-  **2025-10-16** — Updated documentation to reflect current codebase state, including 5-service
  architecture, shared utilities, configuration library, and operational tooling.
-  **2025-10-11** — Added automated `last-updated` validation (`make docs-verify`) covering
  front matter, index tables, version history bullets, and commit recency checks.
-  **2024-07-05** — Adopted the documentation restructure proposal, centralizing onboarding,
  architecture, operations, and governance guides under this hub.

## Contribution Guidelines

-  Add breadcrumbs (`Docs ▸ Section ▸ Page`) to the top of every Markdown file in `docs/`.
-  Include YAML front matter (title, author, status, last-updated) for new guides.
-  Update the relevant index page whenever you add or relocate documentation.
-  Run `make lint` or `make lint-local` to exercise `markdownlint` before committing.
-  Validate metadata freshness with `make docs-verify`; pass `--allow-divergence` to the
   underlying script only when a deliberate date offset is justified.
-  Submit proposals under `docs/proposals/` using the template provided in
   `docs/.templates/` (create one if you need a new format).

## Related Assets

-  `Makefile` — Supported workflows (`make run`, `make lint`, `make test`, etc.).
-  `.env.sample` — Canonical environment variable defaults referenced by the configuration catalog.
-  `docker-compose.yml` — Container orchestration wiring for the Discord, STT, LLM, and TTS services.

## Feedback Loop

File issues or PRs referencing the affected documentation section. For larger reorganizations,
create a proposal that outlines the desired taxonomy changes and cross-link updates.
