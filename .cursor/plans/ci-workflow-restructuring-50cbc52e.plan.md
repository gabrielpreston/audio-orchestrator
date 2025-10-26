<!-- 50cbc52e-11c3-476f-b24d-2666cfa28484 88e73249-6666-4de6-bfec-b6db2e62467f -->
# CI/CD Workflow Restructuring Plan (Corrected)

## Overview

Transform the monolithic CI workflow into a modern multi-workflow architecture with specialized workflows for different change types, enhanced auto-fix capabilities, and integrated base image building. This plan has been validated against the current codebase and corrected for accuracy.

## Current State Analysis

### Existing Workflows

- `ci.yaml` (1100+ lines): Monolithic workflow with 10 jobs, complex dependencies, 15-30 minute runtime
- `base-images.yaml` (272 lines): Separate base image building, weekly schedule + path triggers
- `auto-analyze-ci-failures.yaml` (201 lines): Cursor Agent integration for CI failure analysis

### Current Service Architecture

**Runtime Services (9):**
- discord, stt, llm_flan, orchestrator_enhanced, tts_bark, audio_processor, guardrails, testing_ui, monitoring_dashboard

**Tooling Services (3):**
- linter, tester, security

**Base Images (9):**
- python-base, python-audio, python-ml, python-ml-audio, python-ml-compiled, python-ml-torch, python-ml-transformers, tools, mcp-toolchain

### Problems

- Poor parallelization - jobs gated unnecessarily
- Slow feedback - 15+ minutes for simple Python changes
- Complex dependencies - intricate needs relationships
- Redundant base image building between ci.yaml and base-images.yaml
- Auto-fix only monitors single CI workflow
- Monolithic structure makes maintenance difficult

## Implementation Plan

### Phase 1: Create Main Orchestrator Workflow

**File: `.github/workflows/main-ci.yaml`** (new file, ~150 lines)

Create orchestrator that routes changes to appropriate workflows:

```yaml
name: "Main CI"
on:
  push:
    branches: ["main"]
  pull_request:
    branches: ["main"]
  workflow_dispatch: {}

permissions:
  contents: "read"
  pull-requests: "read"
  packages: "write"

concurrency:
  group: "ci-${{ github.ref }}"
  cancel-in-progress: true

env:
  PIP_DISABLE_PIP_VERSION_CHECK: "1"
  PIP_NO_PYTHON_VERSION_WARNING: "1"
  PYTHONDONTWRITEBYTECODE: "1"

jobs:
  changes:
    name: "Detect affected areas"
    runs-on: "ubuntu-latest"
    environment: "discord-voice-lab"
    outputs:
      python: "${{ steps.filter.outputs.python }}"
      docker: "${{ steps.filter.outputs.docker }}"
      docs: "${{ steps.filter.outputs.docs }}"
      security-deps: "${{ steps.filter.outputs.security-deps }}"
      base: "${{ steps.filter.outputs.base }}"
    steps:
      - name: "Checkout repository"
        uses: "actions/checkout@v4.2.2"
        with:
          fetch-depth: 2
      - name: "Filter paths"
        id: "filter"
        uses: "dorny/paths-filter@v3"
        with:
          filters: |
            python:
              - 'services/**/*.py'
              - 'pyproject.toml'
            docker:
              - 'docker-compose.yml'
              - 'services/**/Dockerfile'
            docs:
              - 'README.md'
              - 'docs/**'
              - 'AGENTS.md'
            security-deps:
              - 'requirements-*.txt'
              - 'services/**/requirements.txt'
            base:
              - 'services/base/**'
              - 'requirements-base.txt'
      - name: "Generate change detection report"
        run: |
          echo "## Change Detection Report" >> $GITHUB_STEP_SUMMARY
          echo "- Python: ${{ steps.filter.outputs.python }}" >> $GITHUB_STEP_SUMMARY
          echo "- Docker: ${{ steps.filter.outputs.docker }}" >> $GITHUB_STEP_SUMMARY
          echo "- Docs: ${{ steps.filter.outputs.docs }}" >> $GITHUB_STEP_SUMMARY
          echo "- Security: ${{ steps.filter.outputs.security-deps }}" >> $GITHUB_STEP_SUMMARY
          echo "- Base: ${{ steps.filter.outputs.base }}" >> $GITHUB_STEP_SUMMARY
  
  core-ci:
    needs: ["changes"]
    if: needs.changes.outputs.python == 'true' || github.event_name == 'workflow_dispatch'
    uses: ./.github/workflows/core-ci.yaml
    with:
      python-changes: ${{ needs.changes.outputs.python == 'true' }}
  
  docker-ci:
    needs: ["changes"]
    if: |
      needs.changes.outputs.docker == 'true' ||
      needs.changes.outputs.base == 'true' ||
      github.event_name == 'workflow_dispatch'
    uses: ./.github/workflows/docker-ci.yaml
    with:
      docker-changes: ${{ needs.changes.outputs.docker == 'true' }}
      base-changes: ${{ needs.changes.outputs.base == 'true' }}
  
  docs-ci:
    needs: ["changes"]
    if: needs.changes.outputs.docs == 'true' || github.event_name == 'workflow_dispatch'
    uses: ./.github/workflows/docs-ci.yaml
  
  security-ci:
    needs: ["changes"]
    if: needs.changes.outputs.security-deps == 'true' || github.event_name == 'workflow_dispatch'
    uses: ./.github/workflows/security-ci.yaml
  
  workflow-status:
    needs: ["core-ci", "docker-ci", "docs-ci", "security-ci"]
    if: always()
    runs-on: "ubuntu-latest"
    steps:
      - name: "Report workflow status"
        run: |
          echo "## Workflow Status" >> $GITHUB_STEP_SUMMARY
          echo "- Core CI: ${{ needs.core-ci.result }}" >> $GITHUB_STEP_SUMMARY
          echo "- Docker CI: ${{ needs.docker-ci.result }}" >> $GITHUB_STEP_SUMMARY
          echo "- Docs CI: ${{ needs.docs-ci.result }}" >> $GITHUB_STEP_SUMMARY
          echo "- Security CI: ${{ needs.security-ci.result }}" >> $GITHUB_STEP_SUMMARY
```

### Phase 2: Create Core CI Workflow

**File: `.github/workflows/core-ci.yaml`** (new file, ~200 lines)

Fast Python feedback workflow using existing Make targets:

```yaml
name: "Core CI"
on:
  workflow_call:
    inputs:
      python-changes:
        required: true
        type: boolean

permissions:
  contents: "read"

jobs:
  lint:
    name: "Lint"
    runs-on: "ubuntu-latest"
    environment: "discord-voice-lab"
    timeout-minutes: 10
    steps:
      - name: "Checkout repository"
        uses: "actions/checkout@v4.2.2"
      - name: "Run linting"
        run: make lint
  
  test-unit:
    name: "Unit Tests"
    runs-on: "ubuntu-latest"
    environment: "discord-voice-lab"
    timeout-minutes: 10
    steps:
      - name: "Checkout repository"
        uses: "actions/checkout@v4.2.2"
      - name: "Run unit tests"
        run: make test-unit
  
  test-component:
    name: "Component Tests"
    runs-on: "ubuntu-latest"
    environment: "discord-voice-lab"
    timeout-minutes: 15
    steps:
      - name: "Checkout repository"
        uses: "actions/checkout@v4.2.2"
      - name: "Run component tests"
        run: make test-component
```

### Phase 3: Create Docker CI Workflow (CORRECTED)

**File: `.github/workflows/docker-ci.yaml`** (new file, ~400 lines)

Docker-specific CI with integrated base image building and all services:

```yaml
name: "Docker CI"
on:
  workflow_call:
    inputs:
      docker-changes:
        required: true
        type: boolean
      base-changes:
        required: true
        type: boolean

permissions:
  contents: "read"
  packages: "write"

jobs:
  build-base-images:
    name: "Build Base Images"
    if: inputs.base-changes
    runs-on: "ubuntu-latest"
    environment: "discord-voice-lab"
    timeout-minutes: 60
    strategy:
      matrix:
        image: [python-base, python-audio, python-ml, python-ml-audio, python-ml-compiled, python-ml-torch, python-ml-transformers, tools, mcp-toolchain]
    steps:
      - name: "Checkout repository"
        uses: "actions/checkout@v4.2.2"
      - name: "Set up Docker Buildx"
        uses: "docker/setup-buildx-action@v3"
        with:
          driver-opts: |
            image=moby/buildkit:latest
            network=host
          buildkitd-flags: --allow-insecure-entitlement network.host
      - name: "Log in to GHCR"
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: "Build and push ${{ matrix.image }}"
        run: |
          docker buildx build \
            --file services/base/Dockerfile.${{ matrix.image }} \
            --tag ghcr.io/${{ github.repository_owner }}/${{ matrix.image }}:latest \
            --cache-from type=gha,scope=base-images \
            --cache-to type=gha,mode=max,scope=base-images \
            --push .
  
  test-integration:
    name: "Integration Tests"
    needs: ["build-base-images"]
    if: always() && (needs.build-base-images.result == 'success' || needs.build-base-images.result == 'skipped')
    runs-on: "ubuntu-latest"
    environment: "discord-voice-lab"
    timeout-minutes: 20
    steps:
      - name: "Checkout repository"
        uses: "actions/checkout@v4.2.2"
      - name: "Prepare environment files"
        run: python scripts/prepare_env_files.py --force
      - name: "Run integration tests"
        run: make test-integration
  
  docker-smoke:
    name: "Docker Smoke Tests"
    needs: ["build-base-images", "test-integration"]
    if: always() && (needs.build-base-images.result == 'success' || needs.build-base-images.result == 'skipped')
    runs-on: "ubuntu-latest"
    environment: "discord-voice-lab"
    timeout-minutes: 30
    strategy:
      matrix:
        service: [discord, stt, llm_flan, orchestrator_enhanced, tts_bark, audio_processor, guardrails, testing_ui, monitoring_dashboard, linter, tester, security]
    steps:
      - name: "Checkout repository"
        uses: "actions/checkout@v4.2.2"
      - name: "Prepare environment files"
        run: python scripts/prepare_env_files.py --force
      - name: "Build and test ${{ matrix.service }}"
        run: |
          docker-compose build ${{ matrix.service }}
          docker-compose up -d ${{ matrix.service }}
          sleep 10
          docker-compose ps ${{ matrix.service }}
          docker-compose down
```

### Phase 4: Create Docs CI Workflow

**File: `.github/workflows/docs-ci.yaml`** (new file, ~100 lines)

Documentation validation workflow:

```yaml
name: "Documentation CI"
on:
  workflow_call: {}

permissions:
  contents: "read"

jobs:
  docs-verify:
    name: "Verify Documentation"
    runs-on: "ubuntu-latest"
    environment: "discord-voice-lab"
    timeout-minutes: 10
    steps:
      - name: "Checkout repository"
        uses: "actions/checkout@v4.2.2"
      - name: "Verify documentation"
        run: make docs-verify
```

### Phase 5: Create Security CI Workflow

**File: `.github/workflows/security-ci.yaml`** (new file, ~150 lines)

Security scanning workflow:

```yaml
name: "Security CI"
on:
  workflow_call: {}

permissions:
  contents: "read"

jobs:
  security-scan:
    name: "Security Scan"
    runs-on: "ubuntu-latest"
    environment: "discord-voice-lab"
    timeout-minutes: 15
    steps:
      - name: "Checkout repository"
        uses: "actions/checkout@v4.2.2"
      - name: "Run security scan"
        run: make security
```

### Phase 6: Enhance Auto-Fix CI (CORRECTED)

**File: `.github/workflows/auto-fix-ci.yaml`** (replaces auto-analyze-ci-failures.yaml)

Enhanced auto-fix with workflow-specific analysis:

Key changes from current implementation:

- Monitor new Main CI workflow instead of old CI workflow
- Add workflow-specific analysis prompts
- Enhanced error categorization
- Improved fix strategies per workflow type

Update line 10 from:
```yaml
workflows: ['CI']
```

To:
```yaml
workflows: ['Main CI']
```

Update Cursor Agent prompt (lines 143-166) to include workflow-specific guidance:

```yaml
- Failed Workflow: ${{ env.WORKFLOW_NAME }}

Workflow-specific analysis:
- Core CI failures: Focus on Python linting (ruff, mypy), unit tests, component tests. Use 'make lint-fix' for auto-fixes.
- Docker CI failures: Focus on Dockerfile syntax, base image builds, integration tests, docker-compose issues. Check environment files.
- Docs CI failures: Focus on documentation validation, markdown linting, metadata checks.
- Security CI failures: Focus on dependency vulnerabilities, secrets detection, security scanning results.
- Main CI failures: Analyze orchestration issues, workflow routing, change detection logic.

Available tools:
- gh api / gh run view / gh run download / gh pr view / gh pr list / gh pr diff
- git (commits/push to the fix branch)
- make test / make lint / make lint-fix / make test-unit / make test-component / make test-integration
- docker-compose commands (for Docker-related failures)
- python scripts/prepare_env_files.py --force (for environment setup issues)
```

### Phase 7: Deprecate Old Workflows

**File: `.github/workflows/ci.yaml`** (deprecate)

Add deprecation notice at top of file:

```yaml
# DEPRECATED: This workflow has been replaced by the multi-workflow architecture
# New workflows: main-ci.yaml, core-ci.yaml, docker-ci.yaml, docs-ci.yaml, security-ci.yaml
# This file is kept for reference only and should not be modified
# TODO: Remove after confirming new workflows work correctly
```

**File: `.github/workflows/base-images.yaml`** (deprecate)

Add deprecation notice:

```yaml
# DEPRECATED: Base image building has been integrated into docker-ci.yaml
# This workflow is kept for manual/scheduled builds only
# For PR-triggered builds, use docker-ci.yaml instead
```

Update trigger to only run on schedule and manual dispatch:

```yaml
on:
  schedule:
    - cron: "0 2 * * 0"
  workflow_dispatch: {}
  # Removed: push.paths trigger (now handled by docker-ci.yaml)
```

### Phase 8: Documentation Updates

**File: `README.md`** (update)

Update CI badge URL:
```markdown
[ci-badge]: https://github.com/gabrielpreston/audio-orchestrator/actions/workflows/main-ci.yaml/badge.svg
[ci-workflow]: https://github.com/gabrielpreston/audio-orchestrator/actions/workflows/main-ci.yaml
```

Add note about new CI architecture:
```markdown
## CI/CD Architecture

The project uses a modern multi-workflow CI architecture:
- **Main CI**: Orchestrates change detection and routes to specialized workflows
- **Core CI**: Fast Python feedback (lint, unit tests, component tests) - ~5-10 minutes
- **Docker CI**: Base image building and service smoke tests - ~20-30 minutes
- **Docs CI**: Documentation validation - ~2-3 minutes
- **Security CI**: Dependency vulnerability scanning - ~5-10 minutes

Each workflow runs independently based on detected changes, providing faster feedback and better resource utilization.
```

**File: `docs/README.md`** (update)

Add CI architecture section:
```markdown
## CI/CD Workflows

- **Multi-workflow Architecture**: Specialized workflows for different change types
- **Fast Feedback**: Python changes complete in ~5-10 minutes
- **Parallel Execution**: Independent workflows run simultaneously
- **Workflow-aware Auto-fix**: Targeted analysis and fixes per workflow type
```

**New File: `docs/operations/ci-workflows.md`**

Create comprehensive CI workflow documentation:
```markdown
# CI/CD Workflow Architecture

## Overview

The audio-orchestrator project uses a modern multi-workflow CI architecture designed for fast feedback and efficient resource utilization.

## Workflow Structure

### Main CI (Orchestrator)
- **Purpose**: Change detection and workflow routing
- **Triggers**: Push to main, pull requests, manual dispatch
- **Runtime**: ~2-3 minutes (change detection only)

### Core CI (Python Focus)
- **Purpose**: Fast Python feedback
- **Triggers**: Python file changes, pyproject.toml changes
- **Jobs**: lint, test-unit, test-component
- **Runtime**: ~5-10 minutes

### Docker CI (Infrastructure Focus)
- **Purpose**: Base image building and service validation
- **Triggers**: Dockerfile changes, base image changes
- **Jobs**: build-base-images (9 images), test-integration, docker-smoke (12 services)
- **Runtime**: ~20-30 minutes

### Docs CI (Documentation Focus)
- **Purpose**: Documentation validation
- **Triggers**: Documentation changes
- **Jobs**: docs-verify
- **Runtime**: ~2-3 minutes

### Security CI (Security Focus)
- **Purpose**: Dependency vulnerability scanning
- **Triggers**: Dependency file changes
- **Jobs**: security-scan
- **Runtime**: ~5-10 minutes

## Auto-Fix Integration

The auto-fix workflow monitors all new workflows and provides workflow-specific analysis and fixes.
```

## Validation Steps

After implementation, validate each workflow:

1. **Core CI validation**:
   - Create PR with Python-only changes
   - Verify core-ci runs in ~5-10 minutes
   - Confirm lint, test-unit, test-component all execute

2. **Docker CI validation**:
   - Create PR with Dockerfile changes
   - Verify all 9 base images build in parallel
   - Confirm integration tests and smoke tests run for all 12 services

3. **Docs CI validation**:
   - Create PR with docs-only changes
   - Verify docs-ci runs independently in ~2-3 minutes
   - Confirm docs-verify executes

4. **Security CI validation**:
   - Create PR with dependency changes
   - Verify security-ci runs
   - Confirm security scan executes

5. **Auto-fix validation**:
   - Trigger CI failure in each workflow type
   - Verify auto-fix analyzes with workflow-specific context
   - Confirm fix branches created with appropriate changes

6. **Integration validation**:
   - Create PR with mixed changes (Python + Docker + Docs)
   - Verify all relevant workflows run in parallel
   - Confirm workflow-status aggregates correctly

## Expected Benefits

- **Fast feedback**: Core CI completes in ~5-10 minutes vs 15-30 minutes
- **Parallel execution**: Independent workflows run simultaneously
- **Better maintainability**: ~200-400 lines per workflow vs 1100+ lines
- **Workflow-aware auto-fix**: Targeted analysis and fixes per workflow type
- **Resource efficiency**: Only build what's needed based on changes
- **Clear separation**: Each workflow has single responsibility
- **Complete coverage**: All 9 base images and 12 services properly tested

## Rollback Plan

If issues arise:

1. Re-enable old ci.yaml by removing deprecation notice
2. Re-enable base-images.yaml path triggers
3. Disable new workflows by adding `if: false` condition
4. Investigate and fix issues
5. Re-test new workflows before re-enabling

## Implementation Checklist

- [ ] Create main-ci.yaml orchestrator workflow with change detection and workflow routing
- [ ] Create core-ci.yaml for fast Python feedback (lint, unit tests, component tests)
- [ ] Create docker-ci.yaml with integrated base image building (9 images) and smoke tests (12 services)
- [ ] Create docs-ci.yaml for documentation validation
- [ ] Create security-ci.yaml for security scanning
- [ ] Enhance auto-fix-ci.yaml with workflow-specific analysis and monitoring
- [ ] Deprecate old ci.yaml and base-images.yaml with notices and trigger updates
- [ ] Update README.md with new CI badge URLs and architecture description
- [ ] Update docs/README.md with CI architecture section
- [ ] Create docs/operations/ci-workflows.md with comprehensive workflow documentation
- [ ] Validate all workflows with test PRs and confirm expected behavior