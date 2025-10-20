---
title: GitHub Actions Migration — Implementation Notes
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-20
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Reports ▸ GitHub Actions Migration — Implementation Notes

# GitHub Actions Migration — Implementation Notes

## Version History

- **2025-10-20** — Updated documentation references to correct CI optimization descriptions and remove misleading docker-build-ci target references.
- **2025-10-11** — Added YAML front matter, breadcrumbs, and metadata validation references for
  the CI migration notes.

The initial CI pipeline now lives at `.github/workflows/ci.yaml` and mirrors the
Makefile-first workflow for linting, testing, Docker validation, and security
scanning. This document captures the guardrails, local reproduction steps, and
artifact expectations that shaped the rollout.

## Workflow overview

- **Triggers:** `push` and `pull_request` events targeting `main`, plus an
  on-demand `workflow_dispatch` entrypoint for dry runs.
- **Permissions:** Workflow-level `permissions: contents: read` with job steps
  reusing the default read-only token.
- **Concurrency:** `concurrency: ci-${{ github.ref }}` with
  `cancel-in-progress: true` to collapse superseded branch runs.
- **Global environment:** disables pip version checks and bytecode writes so job
  logs stay deterministic.

## Change detection gates

The `changes` job uses `dorny/paths-filter` to categorize modifications across
Python, Docker, docs, workflow, and dependency surfaces. Downstream jobs run
only when their categories change or when the workflow is triggered manually.

| Category  | Representative paths                                          | Jobs unblocked            |
|-----------|----------------------------------------------------------------|---------------------------|
| python    | `services/**/*.py`, `pyproject.toml`, `Makefile`               | `Lint`, `Tests`           |
| docker    | `docker-compose.yml`, `services/**/Dockerfile`                | `Lint`, `Docker smoke`    |
| docs      | `README.md`, `docs/**`, `AGENTS.md`                           | `Lint`                    |
| workflows | `.github/workflows/**`                                        | All jobs                  |
| security  | `services/**/requirements.txt`, `pyproject.toml`              | `Security scan`           |

## Job breakdown

| Job            | Timeout | Key steps                                                                                     | Artifacts               |
|----------------|---------|-----------------------------------------------------------------------------------------------|-------------------------|
| `Lint`         | 15 min  | Install Black, isort, Ruff, MyPy, Yamllint, Hadolint, Checkmake, Markdownlint; run `make lint-local`. | —                       |
| `Tests`        | 20 min  | Install service + tester requirements, export `PYTHONPATH`, run `make test-local`.            | `pytest-log`            |
| `Docker smoke` | 30 min  | Enable Buildx, run `make docker-smoke`, capture `docker compose config`.                      | `docker-smoke-artifacts`|
| `Security scan`| 10 min  | Install `pip-audit`, scan each `services/*/requirements.txt`, store JSON reports per service. | `pip-audit-reports`     |

All jobs inherit the default GitHub-hosted Ubuntu runner with Docker enabled.

## Local reproduction checklist

1. Install the lint toolchain locally:
   - `pip install black isort ruff mypy yamllint`
   - Download the Hadolint binary to your `$PATH`
   - `go install github.com/checkmake/checkmake/cmd/checkmake@latest`
   - `npm install -g markdownlint-cli`
2. Install service dependencies: `pip install -r services/<service>/requirements.txt`
   for each service plus `services/tester/requirements.txt`.
3. Run `python scripts/prepare_env_files.py` to create any missing `.env`
   files consumed by `docker compose`. Pass `--force` to refresh files that
   already exist (the CI workflow invokes the script with this flag so every run
   starts from the sample defaults).
4. Run `make lint-local`, `make test-local`, and `make docker-smoke`.
5. When Docker validation fails, inspect `docker-smoke.log` and the rendered
   `docker-compose.config.yaml` artifact from the workflow run.
6. For security findings, review the JSON files in `pip-audit-reports` and
   remediate or accept as appropriate. Re-run `pip-audit --requirement` on the
   affected requirements files to verify fixes.

## Cache and artifact guidance

- `actions/setup-python` handles pip caching automatically keyed by the Python
  version and requirements content.
- Node and Go tooling are installed each run to keep version skew explicit; pin
  revisions in the workflow when ready to publish hardened versions.
- Artifact retention follows the repository default (90 days). Download logs
  while investigating failures to avoid re-running jobs unnecessarily.

## Troubleshooting quick hits

- **Lint job fails immediately:** confirm host tooling matches the versions in
  the workflow, especially Hadolint and Checkmake paths.
- **Docker smoke build flakes:** rerun with `DOCKER_BUILDKIT=0 make docker-smoke`
  locally to compare BuildKit vs. legacy builds, then clear dangling images via
  `make docker-clean-all`.
- **pip-audit reports vulnerabilities:** check whether a patched version exists
  and update the relevant `requirements.txt`. If no fix is available, document
  the rationale in the PR description before merging.

Keep this document in sync with workflow updates so the CI contract remains
obvious to future contributors.
