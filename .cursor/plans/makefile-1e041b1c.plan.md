<!-- 1e041b1c-ad22-4abd-bf9f-04b859a5a3a2 459b07a6-a41b-45d7-91e2-0b5d9ed43685 -->
# Makefile Cleanup Plan

## Overview

Reduce Makefile from 81 targets to 28 essential targets by removing unused bloat while maintaining full CI/CD compatibility and local development workflows. Consolidate on `build-incremental.sh` as the default build strategy.

## Current State Analysis

**Makefile**: 784 lines, 81 targets

**CI Dependencies**: 4 targets (`lint`, `security`, `test`, `docs-verify`)

**Local Development**: ~20 core targets needed

**Bloat**: 53+ targets that are unused or over-engineered

## Changes to Make

### 1. Remove Over-Engineered Build Targets (13 targets)

Remove these build variants and consolidate on `docker-build` using `build-incremental.sh`:

```makefile
# REMOVE lines 180-243
docker-build-full
docker-build-nocache
docker-build-incremental
docker-build-smart
docker-build-optimized
docker-build-services
cache-warm
monitor-build-performance
optimize-builds
base-images
base-images-python-base
base-images-python-audio
base-images-python-ml
base-images-tools
base-images-mcp-toolchain
```

**Keep**: `docker-build`, `docker-build-service` (lines 175, 197-208) which calls `build-incremental.sh`

### 2. Remove Excessive Testing Targets (10 targets)

Remove specialized testing targets, keep essential ones:

```makefile
# REMOVE lines 369-478
test-all
test-fast
test-interface
test-contract
test-hot-swap
test-all-contracts
test-coverage
test-watch
test-debug
test-specific
test-e2e
```

**Keep**: `test`, `test-unit`, `test-component`, `test-integration`, `test-image` (lines 367, 380-386, 388-411)

### 3. Remove Over-Granular Linting Targets (9 targets)

Remove specialized lint variants:

```makefile
# REMOVE lines 505-511, 714-783
lint-%  # Wildcard target for individual linters
lint-python
lint-yaml
lint-markdown
lint-security
lint-complexity
lint-dockerfile
lint-makefile
lint-quick
lint-comprehensive
```

**Keep**: `lint`, `lint-fix`, `lint-image` (lines 487-503)

### 4. Remove CI/CD Bloat Targets (6 targets)

Remove workflow validation and smoke test targets (handled by GitHub Actions):

```makefile
# REMOVE lines 292-331, 357-361
docker-smoke
docker-smoke-ci
docker-validate
workflows-validate
workflows-validate-syntax
workflows-validate-actionlint
validate-all
docker-prune-cache
```

### 5. Simplify Security Targets (2 targets)

Keep security scanning (used by CI), remove baseline management:

```makefile
# REMOVE lines 512-517, 531-548
update-secrets-baseline
security-clean
security-reports
```

**Keep**: `security`, `security-image` (lines 523-529)

### 6. Remove Model Management Targets (2 targets)

Remove manual model download/cleanup:

```makefile
# REMOVE lines 610-678
models-download
models-clean
```

### 7. Remove Evaluation Targets (4 targets)

Remove specialized STT evaluation system:

```makefile
# REMOVE lines 686-705
eval-stt
eval-wake
eval-stt-all
clean-eval
```

### 8. Remove Token Management Targets (3 targets)

Remove manual token rotation utilities:

```makefile
# REMOVE lines 597-607
rotate-tokens
rotate-tokens-dry-run
validate-tokens
```

### 9. Update RUNTIME_SERVICES Variable

Fix mismatch between Makefile and docker-compose.yml (core runtime services only):

```makefile
# UPDATE line 128
# OLD:
RUNTIME_SERVICES := discord stt llm orchestrator tts common

# NEW (core runtime services only):
RUNTIME_SERVICES := discord stt llm-flan orchestrator-enhanced tts-bark audio-processor
```

### 10. Simplify docker-clean-all Target

Remove docker-compose dependency check (line 567-583):

```makefile
# SIMPLIFY lines 567-583
docker-clean-all: ## Nuclear cleanup: stop compose stack, remove ALL images/volumes/networks
	@printf "$(COLOR_RED)⚠️  WARNING: Aggressive cleanup - removes ALL images and volumes$(COLOR_OFF)\n"
	@$(DOCKER_COMPOSE) down --rmi all -v --remove-orphans || true
	@docker system prune -a -f --volumes || true
```

### 11. Update Documentation Files

Remove references to deleted targets from documentation:

**Update `docs/getting-started/local-development.md`:**
- Remove references to: `lint-local`, `test-local`, `workflows-validate*`, `validate-all`
- Add references to: `docker-build-service`, `test-integration`
- Update target table to show 28 targets instead of current 10

**Update `AGENTS.md`:**
- Update Makefile target list (lines 195-199)
- Remove references to removed targets
- Update to reflect new 28-target structure

**Verify `README.md`:**
- Check for any references to removed targets and update if needed

### 12. Validate No External References

Search for references to removed targets in other files:

```bash
# Search for removed target references
grep -r "docker-build-full\|test-all\|lint-python\|workflows-validate" scripts/ .github/ docs/
```

**Files to check:**
- `scripts/` directory for any hardcoded target references
- `.github/workflows/` for any workflow references
- `docs/` for any documentation references
- Other build files or configuration files

### 13. Manual Target Count Validation

Before implementation, manually count targets to verify plan accuracy:

```bash
# Count targets with help descriptions
grep -c "^[a-zA-Z0-9_-]*:.*##" Makefile

# Count all targets (including those without descriptions)  
grep -c "^[a-zA-Z0-9_-]*:" Makefile
```

**Expected results:**
- Current: ~81 targets
- After cleanup: 28 targets
- Reduction: ~65%

## Final Makefile Structure (28 targets)

### Application Lifecycle (4 targets)

- `run`, `stop`, `logs`, `docker-status`

### Docker Management (4 targets)

- `docker-build`, `docker-build-service`, `docker-restart`, `docker-shell`

### Testing (5 targets)

- `test`, `test-unit`, `test-component`, `test-integration`, `test-image`

### Linting (3 targets)

- `lint`, `lint-fix`, `lint-image`

### Security (2 targets)

- `security`, `security-image`

### Documentation (1 target)

- `docs-verify`

### Cleanup (3 targets)

- `clean`, `docker-clean`, `docker-clean-all`

### Configuration (2 targets)

- `docker-config`, `logs-dump`

### Meta (3 targets)

- `help`, `all`, `.DEFAULT_GOAL`

## Pre-Implementation Checklist

1. **Manual Target Count Validation**
   - Count current targets: `grep -c "^[a-zA-Z0-9_-]*:" Makefile`
   - Verify plan claims 81 → 28 targets

2. **External Reference Check**
   - Search for removed target references: `grep -r "docker-build-full\|test-all\|lint-python\|workflows-validate" scripts/ .github/ docs/`
   - Ensure no external dependencies on removed targets

3. **Prerequisite Validation**
   - Confirm `build-incremental.sh` exists and works
   - Confirm `docker-compose.test.yml` exists for test-integration
   - Verify CI workflows use only: `lint`, `security`, `test`, `docs-verify`

## Validation Steps

1. Verify CI workflows still work with remaining targets (`lint`, `security`, `test`, `docs-verify`)
2. Test local development workflow (run, stop, logs, docker-build, docker-restart)
3. Confirm `build-incremental.sh` is properly called by `docker-build`
4. Validate RUNTIME_SERVICES matches core services in docker-compose.yml
5. Test `docker-build-service SERVICE=discord` works for selective builds
6. Test `test-integration` still works locally
7. Verify documentation is updated and accurate
8. Run `make help` to confirm target list is clean
9. **Count final targets**: `grep -c "^[a-zA-Z0-9_-]*:" Makefile` (should be 28)

## Files Modified

- `Makefile` (784 lines → ~350 lines, 81 targets → 28 targets)
- `docs/getting-started/local-development.md` (update target references)
- `AGENTS.md` (update Makefile target list)

## Breaking Changes

None for CI/CD. Local developers using removed targets will need to:

- Use `docker-build` instead of build variants
- Use `test` instead of specialized test targets
- Use `lint` instead of granular lint targets
- Manually manage models, tokens, and evaluations if needed

## Rollback Plan

If issues arise during implementation:

1. **Git Revert**: `git revert <commit-hash>` for Makefile changes
2. **Restore Documentation**: Revert changes to `docs/getting-started/local-development.md` and `AGENTS.md`
3. **Verify CI**: Confirm CI workflows still work after rollback
4. **Test Local**: Run `make help` to confirm all targets restored

## Risk Mitigation

- **Low Risk**: CI workflows use only 4 targets, all preserved
- **Medium Risk**: Documentation updates may need manual review
- **Low Risk**: Local development workflows maintained with 28 targets
- **Zero Risk**: No breaking changes to core functionality

### To-dos

**Pre-Implementation:**
- [ ] **CRITICAL**: Count current targets: `grep -c "^[a-zA-Z0-9_-]*:" Makefile` (should be ~81)
- [ ] **CRITICAL**: Search for external references: `grep -r "docker-build-full\|test-all\|lint-python\|workflows-validate" scripts/ .github/ docs/`
- [ ] **CRITICAL**: Verify prerequisites: `build-incremental.sh`, `docker-compose.test.yml` exist
- [ ] **CRITICAL**: Confirm CI uses only: `lint`, `security`, `test`, `docs-verify`

**Implementation:**
- [ ] Remove 13 over-engineered build targets (docker-build-full, base-images*, etc.) - KEEP docker-build-service
- [ ] Remove 10 excessive testing targets (test-all, test-interface, test-e2e, etc.) - KEEP test-integration
- [ ] Remove 9 over-granular linting targets (lint-python, lint-yaml, lint-*, etc.)
- [ ] Remove 6 CI/CD bloat targets (docker-smoke, workflows-validate*, etc.)
- [ ] Remove 3 security management targets, keep security and security-image
- [ ] Remove 9 targets for model management, evaluation, and token rotation
- [ ] Update RUNTIME_SERVICES variable to core runtime services only (discord, stt, llm-flan, orchestrator-enhanced, tts-bark, audio-processor)
- [ ] Simplify docker-clean-all target to remove unnecessary checks
- [ ] Update documentation files (local-development.md, AGENTS.md) to remove references to deleted targets

**Post-Implementation Validation:**
- [ ] **CRITICAL**: Count final targets: `grep -c "^[a-zA-Z0-9_-]*:" Makefile` (should be 28)
- [ ] **CRITICAL**: Verify CI workflows still work with cleaned Makefile (lint, security, test, docs-verify)
- [ ] Test local development workflow (run, stop, logs, docker-build, docker-restart)
- [ ] Test `docker-build-service SERVICE=discord` works for selective builds
- [ ] Test `test-integration` still works locally
- [ ] Run `make help` to confirm target list is clean
- [ ] Verify documentation is updated and accurate