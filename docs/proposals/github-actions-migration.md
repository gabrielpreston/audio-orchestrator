---
title: GitHub Actions Migration
author: Discord Voice Lab Team
status: draft
last-updated: 2025-10-19
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Proposals ▸ GitHub Actions Migration

# Proposal: GitHub Actions Migration for Discord Voice Lab

## Executive Summary

- **Status:** ✅ **IMPLEMENTED** - GitHub Actions CI/CD with Docker build optimizations achieving 80-90% build time reduction via shared base images, parallel builds, and GitHub Actions cache integration.

- Stand up a `ci.yaml` workflow that mirrors the Makefile-driven lint, test, and Docker checks
  you already rely on while baking in GitHub Actions guardrails (least-privilege permissions,
  concurrency cancellation, reproducible environments).
- Normalize Docker and docker-compose assets so GitHub-hosted runners can build and smoke-test
  the stack without pulling large models or fighting UID/GID drift.
- Capture the migration journey in repo-native docs, templates, and checklists so future you
  (and eventual collaborators) can retrace decisions and extend automation safely.

## Current State Reconnaissance

- Monorepo with Python services: Discord bot (`services/discord`), STT FastAPI (`services/stt`),
  LLM orchestrator FastAPI (`services/llm`), Piper-based TTS (`services/tts`), and shared
  utilities (`services/common`).
- Tooling standardized via `Makefile`: containerized lint (`make lint`) running Black, isort,
  Ruff, MyPy, Hadolint, Yamllint, Checkmake, Markdownlint; containerized tests (`make test`)
  wrapping pytest with a custom runner.
- Docker-first workflow (`docker-compose.yml`) orchestrates services using `.env.common`,
  service-specific `.env.service`, and `.env.docker`; build context is the repository root.
- Python tooling configured through `pyproject.toml`; no existing CI definitions, and pytest
  currently passes when no tests are collected.
- Service images mix Python 3.11 and 3.12 bases, creating divergence between lint/test
  containers and runtime services.
  【F:services/discord/Dockerfile†L1-L27】【F:services/stt/Dockerfile†L1-L33】【F:services/llm/Dockerfile†L1-L21】
  【F:services/tts/Dockerfile†L1-L33】【F:services/linter/Dockerfile†L1-L36】【F:services/tester/Dockerfile†L1-L40】

## Automation Goals

1. Provide automated validation (linting, testing, Docker build checks) on feature branches so
   regressions surface without manual spot checks.
2. Reuse existing Makefile targets to preserve parity with the local workflow and avoid
   fragmenting command surfaces.
3. Optimize for solo iteration speed with clear logs, caching, and deterministic environments so
   automation accelerates experimentation.
4. Lay groundwork for future deployments by standardizing artifact naming, environment handling,
   and Docker baselines.

## High-Value Quick Wins

- **Change-based triggers**: add `paths` / `paths-ignore` filters so doc-only updates skip Docker-heavy jobs while keeping Markdown linters enabled.
- **Least-privilege defaults**: declare workflow-level `permissions: contents: read` and elevate scopes only on jobs that upload artifacts or build/push images.
- **Concurrency cancellation**: use `concurrency: ci-${{ github.ref }}` with `cancel-in-progress: true` to stop superseded runs automatically.
- **Pinned actions**: lock third-party actions to commit SHAs once the workflow stabilizes to mitigate supply-chain risk.
- **Setup caching**: lean on `actions/setup-python@v5` with `cache: 'pip'`, plus targeted caches for Node/Go tooling and Docker BuildKit layers.
- **Deterministic timeouts**: specify `timeout-minutes` per job so lint/test failures surface quickly instead of hanging on upstream downloads.
- **Security scanning**: run `pip-audit` and container scanning (e.g., Trivy) alongside functional checks to catch vulnerable dependencies early.
- **Scheduled cache warmers**: add a weekly cron that rebuilds base images, refreshes tool caches, and reports drift before you encounter it interactively.
- **Reusable bootstrap**: centralize tool installation in a composite action or `setup` job artifact so lint/test jobs share the same pinned toolchain.
- **Diagnostics artifacts**: always capture `docker compose config`, pytest logs, and scanner reports via `actions/upload-artifact` to make postmortems painless.

## Recommended Workflows

### `ci.yaml` — Lint, Test, Security, and Docker Smoke

Runs on `pull_request` and `push` to the default branch with change-based filters for code, Docker, and configuration directories.

#### Workflow defaults

- `permissions: contents: read` at the top level; override with `actions: write` only on jobs uploading artifacts.
- `concurrency: ci-${{ github.ref }}` plus `cancel-in-progress: true` to cancel superseded branch runs.
- Global environment flags such as `PIP_DISABLE_PIP_VERSION_CHECK=1` and `PYTHONDONTWRITEBYTECODE=1` for deterministic output.
- `timeout-minutes` values tuned per job (e.g., 10 for lint, 20 for tests, 30 for Docker smoke).

#### Job: bootstrap (optional but recommended)

- Checkout repository via `actions/checkout@v4` (pin to commit SHA when finalizing) with `fetch-depth: 1` and `persist-credentials: false`.
- Install Python 3.11 with `actions/setup-python@v5` using built-in pip caching.
- Install shared tooling (Black, isort, Ruff, MyPy, Yamllint, Markdownlint, Hadolint, Checkmake) via pip/npm/go.
- Upload the prepared virtualenv and lint binaries as an artifact for downstream jobs, or expose them via job outputs.

#### Job: lint

- Needs tooling artifact from `bootstrap` (or repeats installation if you keep jobs self-contained).
- Run `make lint-local` (or a dedicated `lint-ci` target) to mirror local Makefile behavior and ensure Docker, YAML, Markdown, and Python linters stay consistent.
- Fail fast on formatting issues and upload linter logs as artifacts when available.

#### Job: test

- Choose between host execution (`make test-local`) or Docker parity (`make test`) depending on how closely you want to mirror production containers.
- When running Docker, enable `docker/setup-buildx-action@v3`, configure BuildKit cache, and guard against missing models by stubbing assets.
- Upload pytest output (including the “no tests collected” case) so you can confirm the runner behavior matches expectations.

#### Job: docker-smoke

- Build images defined in `docker-compose.yml` (Discord, STT, LLM, TTS) using BuildKit caching and optional matrix for architectures.
- Run `make docker-smoke` (new target) to execute `docker compose config --services`, start profile-scoped services, and hit health endpoints with curl.
- Publish `docker compose config` and container logs as artifacts for debugging.

#### Job: security-scan

- Run `pip-audit` against Python dependencies and upload the SBOM/vulnerability report.
- When Docker images are built, run Trivy or Grype against the resulting tarballs; fail on high/critical vulnerabilities.

Jobs run in parallel once prerequisites are ready, with artifacts providing shared context without relaxing job isolation.

### `docker-build.yaml` — Optional Release Validation

Triggered on pushes to `main`, tags, or manual dispatch.

- Set up QEMU (if multi-arch), Buildx, and GHCR authentication as needed.
- Build and optionally push tagged images for each service, reusing cache from scheduled warmers.
- Invoke the same smoke tests used in `ci.yaml` to keep parity between PR checks and release builds.
- Schedule a weekly cron run to rebuild base layers and surface dependency drift.

### `cache-warm.yaml` — Scheduled Maintenance (Optional)

- Nightly or weekly job that restores caches, pre-downloads models, and runs lightweight validations so day-to-day pushes benefit from warm caches and recent base images.

## Docker & Compose Alignment for CI

### Normalize Container Baselines

- Introduce a shared base image (e.g., `discord-voice-lab/python-audio:3.11`) that preinstalls
  FFmpeg, build tools, and Python dependencies, then reuse it across Discord, STT, LLM, TTS,
  lint, and tester images to reduce rebuild churn.
  【F:services/discord/Dockerfile†L1-L27】【F:services/stt/Dockerfile†L1-L33】【F:services/llm/Dockerfile†L1-L21】
  【F:services/tts/Dockerfile†L1-L33】【F:services/linter/Dockerfile†L1-L36】【F:services/tester/Dockerfile†L1-L40】
- Freeze dependency versions (with hashes) and centralize the `pip install --upgrade pip
  setuptools wheel` bootstrap so Docker layer caching stays deterministic.

### Slim Lint/Test Toolchain

- Split the linter/tester Dockerfiles into a published `tools-base` stage plus a thin runtime stage that only copies project code, letting CI pull prebuilt tool images instead of compiling per run.
- Provide non-Docker Makefile targets (`lint-local`, `test-local`) that install matching tools directly on GitHub-hosted runners when Docker is unavailable or too slow.

### Compose Profiles and Overrides

- Add Compose `profiles` to start only the services required for each test scenario (e.g., `core`, `bot`, `full`).【F:docker-compose.yml†L1-L50】
- Expose profile-aware Makefile targets (`make run-core`, `make run-bot`) and use them inside workflows to minimize resource usage.
- Create a `docker-compose.ci.yml` override that disables unused ports, shrinks volumes, and replaces heavy models with stubs.

### Asset & Volume Handling

- Local development mounts `./models` into TTS and orchestrator containers; provide a `make
  models-download` target (or CI step) that fetches minimal models and stores them in a cache
  artifact.【F:docker-compose.yml†L29-L42】
- Parameterize model paths through `.env.docker` so CI can swap in lightweight fixtures without
  editing Compose.
- Ensure services exit gracefully when secrets like `DISCORD_BOT_TOKEN` are absent to avoid
  accidental live Discord connections.【F:.env.sample†L9-L76】

### UID/GID and Filesystem Permissions

- Expose `PUID`/`PGID` as build arguments in each Dockerfile and create the runtime user during
  image build, matching `.env.docker` defaults while staying compatible with GitHub runner UID
  1001.【F:.env.sample†L69-L74】
- Update Makefile Docker invocations to pass the host UID/GID so generated artifacts remain
  writable across jobs.

### Compose Diagnostics

- Extend `make docker-config` to output the rendered Compose config and upload it as a workflow artifact, capturing environment interpolation.
- Implement `make docker-smoke` to list services, run container health checks, and emit concise logs suitable for CI debugging.

## Implementation Playbook

### Tool Bootstrap Strategy

- Python linters: `pip install black isort ruff mypy yamllint`.
- Dockerfile lint: download Hadolint binary via `HADOLINT_URL`.
- Makefile lint: `go install github.com/checkmake/checkmake/cmd/checkmake@latest` (pin version when finalizing).
- Markdown lint: `npm install -g markdownlint-cli`.
- Consolidate these steps inside a reusable workflow or composite action so you maintain version pins in one place.

### Workflow Security & Hygiene

- Pin every third-party action to a commit SHA once stable.
- Keep job-level `permissions` minimal, granting `actions: write` only when uploading artifacts or caches.
- Reuse the workflow-level concurrency block across future workflows to prevent parallel runs from racing on shared resources.
- Pass explicit tokens (`token: ${{ secrets.GITHUB_TOKEN }}`) to checkout or registry steps as needed while keeping defaults read-only.

### Environment & Secrets

- Lint/test jobs should not require runtime secrets; mock external services and guard network calls behind feature flags.
- Document in README which `.env.*` files are necessary for Docker smoke tests versus local development.
- When integration tests eventually use Discord or OpenAI credentials, store them as GitHub secrets and gate the jobs behind `if` conditions.

### Caching & Artifacts

- Let `actions/setup-python` handle pip caching; add explicit caches for Node, Go, and Docker layers keyed on OS plus lockfile hashes.
- Upload `docker compose config`, pytest logs, lint reports, and scanner output to `actions/upload-artifact` for easy retrieval.
- Purge caches proactively via scheduled jobs if dependency drift causes flaky builds.

## Migration Roadmap (Solo Developer)

1. **Seed the automation foundation** — capture the initial workflow intent in-repo so progress is visible and reversible.
   1.1. Create a dedicated feature branch for the migration to isolate revisions.
       - *Goal*: Preserve a clean undo path while you experiment with workflow layouts or caching strategies.
   1.2. Draft `.github/workflows/ci.yaml` (and supporting composite actions) covering lint, test, docker-smoke, and security scan jobs.
       - *Goal*: Translate trusted Makefile routines into CI-equivalent jobs with guardrails (permissions, concurrency, timeouts).
       1.2.1. Map each Makefile target (`lint`, `test`, `docker-smoke`) to a job stub with matching names.
           - *Goal*: Keep CI job labels synchronized with local commands for intuitive branch protection rules.
       1.2.2. Decide whether each job runs via Docker or directly on the runner and record the rationale in comments.
           - *Goal*: Document execution strategy so future adjustments preserve intent.
       1.2.3. Add placeholders for artifact uploads (logs, SBOMs, Compose config) even if disabled initially.
           - *Goal*: Make it trivial to enable richer diagnostics without reworking job order later.
   1.3. Commit workflow defaults (`permissions`, `concurrency`, shared env, timeouts) alongside explanatory comments.
       - *Goal*: Bake in community best practices before the workflow grows.
   1.4. Open a draft pull request gated behind `workflow_dispatch` to use the PR thread as a migration journal.
       - *Goal*: Capture TODOs, experiment results, and follow-ups in a single discoverable place.

2. **Align documentation and onboarding** — ensure future you can rediscover how automation works.
   2.1. Update the README Quickstart with a GitHub Actions status badge and summary of required checks.
       - *Goal*: Surface CI signals in the most visible location.
   2.2. Add a changelog or release note entry summarizing workflow scope, guardrails, and known limitations.
       - *Goal*: Preserve context for when and why automation was introduced.
   2.3. Refresh onboarding docs (`docs/` proposals, roadmap) with “How CI runs locally” snippets referencing Makefile targets.
       - *Goal*: Provide a ready-made troubleshooting script for reproducing CI locally.
       2.3.1. Link to the Makefile section that mirrors each CI job (`lint-local`, `test-local`, `docker-smoke`).
           - *Goal*: Prevent doc drift between commands and automation.
       2.3.2. Add a collapsible checklist for reproducing failures (pull latest main, run target, inspect logs).
           - *Goal*: Reduce triage time when failures occur.
       2.3.3. Document cache locations (pip, Docker layers, models) locally versus CI.
           - *Goal*: Clarify when to purge or seed caches.

3. **Institutionalize expectations & templates** — encode the workflow contract so solo maintenance stays consistent.
   3.1. Author pull request and issue templates prompting you to run matching Makefile targets and paste CI run links.
       - *Goal*: Embed CI-ready habits into your own workflow.
   3.2. Extend README or `CONTRIBUTING.md` with a troubleshooting checklist and workflow links tailored for a single maintainer.
       - *Goal*: Provide a self-serve runbook that survives context switches.
       3.2.1. Include triage steps ordered by effort (rerun job, tail `make logs`, rebuild affected image).
           - *Goal*: Reduce decision fatigue during incidents.
       3.2.2. Template GitHub Actions run URLs and artifact locations for quick navigation.
           - *Goal*: Jump straight to diagnostics without manual URL assembly.
       3.2.3. Capture known transient issues (rate limits, cache misses) with your preferred mitigation.
           - *Goal*: Turn debugging lessons into durable breadcrumbs.
   3.3. Maintain a proposal appendix or changelog table logging workflow purpose, last update, and queued enhancements.
       - *Goal*: Keep institutional knowledge in-repo without needing additional tools.

4. **Validate behavior before enforcement** — confirm automation behaves predictably before gating merges.
   4.1. Enable the workflow on the feature branch via `workflow_dispatch` or branch protection dry runs.
       - *Goal*: Verify bootstrap steps succeed without impacting `main`.
   4.2. Trigger positive and negative scenarios (passing lint, failing lint, skipped tests) and observe notifications.
       - *Goal*: Ensure failure output is actionable and alerts reach you.
       4.2.1. Commit a deliberate lint failure to confirm tooling reports exact files and rules.
           - *Goal*: Validate signal quality before relying on the job.
       4.2.2. Simulate `pytest -k` skips or xfail cases to ensure workflow treats them as expected.
           - *Goal*: Catch misconfigured pytest flags that hide failures.
       4.2.3. Review GitHub emails/mobile alerts generated by each failure.
           - *Goal*: Confirm your monitoring channel surfaces issues promptly.
   4.3. Log fixes (cache tweaks, path corrections) directly in the PR description or changelog.
       - *Goal*: Preserve a running checklist for future tuning.

5. **Enforce and iterate** — let automation guard merges and drive continuous improvement.
   5.1. Enable GitHub Actions for the repository and verify personal token scopes allow workflow runs.
       - *Goal*: Remove blockers that would prevent jobs from running on your pushes or schedules.
   5.2. Apply branch protection requiring `lint`, `test`, and `docker-smoke` jobs before merging to `main`.
       - *Goal*: Hold yourself to the same guardrails a larger team would depend on.
   5.3. Monitor the first week of runs for flakes, duration spikes, or cache misses; note metrics in the PR journal.
       - *Goal*: Identify optimizations or documentation gaps while context is fresh.
   5.4. Close the migration proposal with a retrospective section listing lessons learned and queued enhancements.
       - *Goal*: Mark the milestone complete and keep a roadmap for the next iteration.

## Risks & Mitigations

- **Tool installation overhead**: mitigate via shared bootstrap artifacts, caching, and published base images.
- **Docker availability limits**: prefer host-based lint/test paths when Docker is disabled; when required, run on Ubuntu runners with `docker/setup-buildx-action`.
- **External dependency flakes**: ensure tests do not require network access; gate integration flows behind feature flags or optional jobs.
- **Secrets exposure**: keep workflows secret-free until integration tests need them; scope permissions tightly when secrets are introduced.
- **Model asset size**: rely on stub models and cache artifacts to avoid repeatedly downloading large voice assets.

## Future Enhancements

- Expand test matrix to include additional Python versions or operating systems once coverage grows.
- Publish container images to GitHub Container Registry on tags and reuse them for deployments.
- Integrate Bandit, Trivy, and dependency-review once the baseline CI proves stable.
- Add MCP contract tests when automation around tool integrations matures.
- Layer in notifications (Slack, email digests) if collaboration expands beyond a single maintainer.

### Explicitly Out of Scope for the Initial Migration

- Automated deploys or release publishing; keep the first iteration focused on verification-only workflows before pushing artifacts anywhere.
- Secrets-backed integration tests (Discord, OpenAI) until mockable interfaces and secret management patterns are defined.
- Multi-environment branching strategies or required review policies; defer governance until the project has additional maintainers.
