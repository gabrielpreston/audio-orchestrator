---
title: Documentation Restructure Proposal
author: Discord Voice Lab Team
status: accepted
last-updated: 2024-07-05
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Proposals ▸ Documentation Restructure Proposal

# Documentation Restructure Proposal

## Purpose

Deliver an information architecture that lets contributors and operators locate onboarding,
architecture, operations, and research material without scanning multiple Markdown trees. This plan
realigns the `docs/` directory, README surfaces, and service-specific guides so they share a single
navigational spine while preserving existing content.

## Guiding Principles

1. **Role-targeted navigation** — Segment content for newcomers, operators, voice-orchestrator
   developers, and MCP tool integrators with dedicated entry points.
2. **Lifecycle alignment** — Arrange documentation around evaluate → onboard → build → operate →
   extend workflows so every phase has a canonical starting location.
3. **Single source of truth** — Consolidate duplicated instructions (environment setup, logging,
   Makefile usage) and redirect supplemental files to the authoritative guide.
4. **Change traceability** — Track conceptual docs (roadmaps, proposals, postmortems) under
   time-ordered directories and reference them from a living index.
5. **Automation-first governance** — Add lightweight CI checks (lint, link validation) so
   structural drift is caught automatically instead of during ad-hoc reviews.
6. **Low-friction contribution** — Provide templates and consistent metadata so new Markdown
   assets can be landed without negotiating placement or format per PR.

## Proposed Directory Layout

| Path | Description | Primary Audience | Notes |
| --- | --- | --- | --- |
| `README.md` | High-level overview, quickstart, and navigation pointers into deeper guides. | New contributors | Add "Documentation Index" section linking to `docs/index.md`. |
| `docs/index.md` | Entry hub describing documentation taxonomy and cross-linking major sections. | All roles | New file consolidating table of contents, version history, and contribution rules. |
| `docs/getting-started/` | Environment setup, service bootstrap, make targets, troubleshooting. | New contributors, platform engineers | Fold core README setup plus future onboarding guides here. |
| `docs/architecture/` | System diagrams, service descriptions, messaging contracts. | Developers, architects | Rehome README architecture sections, `docs/MCP_MANIFEST.md`, and new service diagrams. |
| `docs/operations/` | Runbooks, observability guides, deployment procedures, incident response. | Operators, SREs | Include structured logging, metrics, health endpoints, TTS/STT tuning. |
| `docs/reference/` | API schemas, configuration catalogs, manifest specifications. | Integrators, platform engineers | Collect env var tables, service endpoints, and manifest specs. |
| `docs/roadmaps/` | Strategic plans and execution waves with changelog anchors. | Leadership, planners | Migrate `docs/ROADMAP.md` and future planning docs, include index by date. |
| `docs/reports/` | Implementation reviews, retrospectives, performance evaluations. | Stakeholders, QA | Relocate `docs/implemented/tts_service_evaluation.md` and similar artifacts. |
| `docs/proposals/` | In-flight and historical proposals, each with status metadata. | Architects, reviewers | Maintain existing proposal files with front matter summarizing decision state. |
| `services/*/README.md` | Service-scoped quickstart, configuration overrides, and local tips. | Service owners | Link back to canonical setup/operations guides to avoid drift. |

## Content Migration Plan

1. **Create `docs/index.md`** summarizing the voice lab purpose, documentation taxonomy, change
   log, and contribution conventions (including proposal location rules from `AGENTS.md`).
2. **Refactor `README.md`** into three sections: overview, "Run the Stack" (linking into
   `docs/getting-started/runtime.md`), and "Documentation Index" referencing the new hub.
3. **Establish `docs/getting-started/`** with:
   - `environment.md` covering `.env` management currently described in `README.md`.
   - `local-development.md` aggregating lint/test instructions and Makefile workflows.
   - `troubleshooting.md` cataloging common Docker, audio, and permission issues.
4. **Construct `docs/architecture/`** with:
   - `system-overview.md` diagramming service relationships and audio/transcript flows.
   - `service-deep-dives/discord.md`, `stt.md`, `llm.md`, `tts.md` capturing pipeline behavior,
     wake-word handling, STT contracts, orchestrator routes, and TTS streaming behavior. Relocate
     technical prose from `services/tts/README.md` while leaving an abridged summary behind.
   - `integration/mcp.md` rehoming `docs/MCP_MANIFEST.md` as a specification appendix.
5. **Launch `docs/operations/`** to cover:
   - `runbooks/discord-voice.md` for day-to-day bot operations and alert response.
   - `observability.md` summarizing structured logging, Prometheus endpoints, and `make logs` usage.
   - `security.md` centralizing authentication, token handling, and rate-limiting guidance.
6. **Move planning documents** by:
   - Relocating `docs/ROADMAP.md` to `docs/roadmaps/2024-integrated-voice-devops.md` with front
     matter specifying authorship, date, and status.
   - Adding `docs/roadmaps/index.md` listing active and archived roadmaps with revision history.
7. **Rehome implementation reviews** by converting `docs/implemented/tts_service_evaluation.md` into
   `docs/reports/tts-service-evaluation.md` and creating an index page summarizing lessons learned.
8. **Standardize proposals** by:
   - Adding YAML front matter (title, author, status, last-updated) to each file in
     `docs/proposals/` and inserting a table that links them from a new `docs/proposals/index.md`.
   - Adding guidelines for proposal lifecycle (draft → review → accepted/rejected) within the index.
9. **Centralize configuration references** by compiling environment variables from `.env.sample` and
   service READMEs into `docs/reference/configuration-catalog.md` with per-service tables and
   cross-links back to operations runbooks.
10. **Embed navigation breadcrumbs** at the top of each Markdown file (e.g., `Docs ▸ Architecture ▸
    Orchestrator`) to reinforce the hierarchy and improve GitHub readability.

## Maintenance Workflows

- Add a documentation checklist to `CONTRIBUTING.md` (or create one if absent) that requires
  updating relevant `docs/` sections whenever new services, MCP tools, or environment variables are
  introduced.
- During PR review, confirm links to the documentation hub are added for any new Markdown asset.
- Schedule quarterly audits to reconcile service READMEs with their authoritative architecture and
  operations guides, updating cross-links or extracting divergent content.
- Stand up CI automation that runs `markdownlint` (format), `markdown-link-check` (links), and a
  lightweight table-of-contents validator on every PR touching Markdown files.
- Publish short-form templates (front matter skeletons, migration checklist) in `docs/.templates/`
  so authors can bootstrap new guides without copying from unrelated files.

## Risks & Mitigations

- **Link rot during migration** — Use automated link check (e.g., `markdown-link-check`) in CI and
  include redirects (`docs/legacy/README.md` with pointers) for heavily referenced paths.
- **Contributor confusion** — Publish the restructuring plan in `docs/index.md` and announce the
  taxonomy in the README plus team channels before moving files.
- **Drift between service READMEs and canonical docs** — Keep service READMEs scoped to quickstart
  steps and surface deeper detail exclusively from architecture/operations guides.
