<!-- 3d4a700f-c0cf-4c5a-890a-963e12f20976 cb5a4676-c46b-4c09-8c8b-d98735234bd9 -->
# Consolidate Virtual Environments to Single Root Environment

## Problem Statement

The project currently has multiple virtual environments causing Python interpreter confusion in Cursor IDE:

- Root `.venv` (working, but missing some service dependencies)
- `services/stt/.venv` (exists but redundant)
- `services/discord/.venv` (exists but redundant)
- `services/common/.venv` (missing, causing errors)

This multi-environment setup conflicts with the Docker-first architecture and creates IDE configuration issues.

## Solution Overview

Adopt industry best practice for microservices monorepos: **single root virtual environment** for development, with Docker containers handling production runtime isolation.

## Implementation Steps

### 1. Remove Service-Specific Virtual Environments

**Files to delete:**

- `services/stt/.venv/` - Remove entire directory
- `services/discord/.venv/` - Remove entire directory
- Any other service-specific `.venv` directories found

**Rationale:** Services run in Docker containers with their own Python environments. Local development only needs one consolidated environment for linting, testing, and IDE support.

### 2. Update IDE Configuration

**File: `audio-orchestrator.code-workspace`**

Change line 57 from:

```json
"python.languageServer": "None",
```

To:

```json
"python.languageServer": "Pylance",
```

**Rationale:** Enable Pylance language server for proper Python IntelliSense, type checking, and error detection. The current "None" setting causes "Editor support is inactive" messages.

### 3. Update .gitignore (Verification Only)

**File: `.gitignore`**

Verify lines 21-24 already exclude service-specific virtual environments:

```
# Virtual Environments
.venv/
.venv-*/
.tmpvenv/
```

**Note:** Current configuration already ignores `.venv/` and `.venv-*/` patterns, which covers both root and service-specific virtual environments. This is correct and no changes needed.

### 4. Update .dockerignore (Already Correct)

**File: `.dockerignore`**

Verify lines 13-15 already exclude all virtual environments:

```
.venv
.venv-*
venv
```

**Status:** Already correct - no changes needed.

### 5. Update Documentation

**File: `docs/getting-started/local-development.md`**

Add new section after "Tips" section (after line 40):

````markdown
## Python Development Environment

The project uses a **single root virtual environment** (`.venv`) for all local development:

```bash
# Create and activate virtual environment (first time only)
python3 -m venv .venv
source .venv/bin/activate

# Install all development dependencies
pip install -r services/requirements-dev.txt
pip install -r services/requirements-base.txt

# Install all service-specific dependencies
pip install -r services/discord/requirements.txt
pip install -r services/stt/requirements.txt
pip install -r services/orchestrator_enhanced/requirements.txt
pip install -r services/guardrails/requirements.txt
pip install -r services/tts_bark/requirements.txt
pip install -r services/audio_processor/requirements.txt
pip install -r services/testing_ui/requirements.txt
pip install -r services/monitoring_dashboard/requirements.txt
pip install -r services/security/requirements.txt
pip install -r services/linter/requirements.txt
pip install -r services/tester/requirements.txt
```

**Why single environment?**

- Services run in Docker containers (each with isolated Python environments)
- Local `.venv` is for development tools: linting, testing, IDE support
- Eliminates virtual environment confusion in IDEs
- Matches industry best practices for microservices monorepos

**PYTHONPATH Configuration:**

The workspace automatically configures `PYTHONPATH` to include `services/` and `services/common/` so all imports resolve correctly.

````

### 6. Verify Root Virtual Environment Completeness

**Action:** Install ALL missing dependencies and verify completeness

Run these commands to install all dependencies:
```bash
source .venv/bin/activate

# Install base and dev dependencies first
pip install -r services/requirements-dev.txt
pip install -r services/requirements-base.txt

# Install ALL service-specific dependencies
for req_file in services/*/requirements.txt; do
    echo "Installing from $req_file"
    pip install -r "$req_file"
done

# Verify critical dependencies are present
pip list | grep -E "(fastapi|discord|faster-whisper|langchain|bark|piper|structlog|httpx)"
```

**Expected:** All core service dependencies should be present. If any are missing, the installation loop above will install them.

### 7. Update Cursor Settings

**File: `.cursor/settings.json`**

Verify lines 25-32 already point to root virtual environment:

```json
"python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
"python.terminal.activateEnvironment": true,
```

**Status:** Already correct - no changes needed.

## Validation Steps

1. **Remove old environments:** Verify `services/stt/.venv` and `services/discord/.venv` are deleted
2. **IDE verification:** Open Cursor, check Python interpreter path shows `/.venv/bin/python`
3. **Language server:** Verify Pylance is active (no "Editor support is inactive" messages)
4. **Import resolution:** Open any service file, verify imports resolve correctly
5. **Dependency verification:** Run `pip list | grep -E "(fastapi|discord|faster-whisper|langchain|bark)"` to confirm all dependencies installed
6. **Linting:** Run `make lint` - should complete without interpreter errors
7. **Testing:** Run `make test-unit` - should execute using root environment

## Benefits

- **Single source of truth:** One virtual environment to manage
- **Faster setup:** New developers run `python -m venv .venv && pip install -r services/requirements-dev.txt`
- **IDE clarity:** No more interpreter confusion or missing Python errors
- **Docker alignment:** Local development matches production containerized approach
- **Industry standard:** Follows microservices monorepo best practices (Google, Microsoft, Netflix patterns)

## Files Modified

1. `audio-orchestrator.code-workspace` - Enable Pylance language server
2. `docs/getting-started/local-development.md` - Add comprehensive virtual environment setup guide
3. `services/stt/.venv/` - Delete directory
4. `services/discord/.venv/` - Delete directory (was missing from original plan)

## No Changes Needed

- `.gitignore` - Already configured correctly
- `.dockerignore` - Already configured correctly
- `.cursor/settings.json` - Already points to root environment
- `pyproject.toml` - Tool configuration unchanged
- `Makefile` - Uses Docker containers, not affected

### To-dos

- [ ] Remove service-specific virtual environment directories (services/stt/.venv and services/discord/.venv)
- [ ] Update workspace configuration to enable Pylance language server
- [ ] Add comprehensive Python virtual environment setup guide to local development documentation
- [ ] Install all service-specific dependencies in root .venv
- [ ] Test IDE integration, imports, linting, and unit tests with consolidated environment

## Plan Corrections Applied

This plan has been updated with the following corrections based on codebase analysis:

### Critical Issues Fixed

1. **Added Missing Virtual Environment**: `services/discord/.venv` was discovered and added to removal list
2. **Corrected Documentation Insertion Point**: Changed from line 27 to after line 40 (after "Tips" section)
3. **Enhanced Dependency Installation**: Added comprehensive installation of all 10+ service-specific requirements files
4. **Updated .gitignore Assessment**: Corrected to show that service-specific `.venv` directories are already ignored
5. **Improved Validation Steps**: Added dependency verification step and updated commands

### Confidence Scores

| Step | Confidence | Notes |
|------|------------|-------|
| Remove service venvs | **95%** | Clear action, low risk |
| Enable Pylance | **100%** | Exact line change identified |
| Update docs | **90%** | Corrected insertion point and content |
| Install dependencies | **85%** | Comprehensive installation loop provided |
| Validation | **95%** | Clear test steps with dependency verification |

### Files Modified (Corrected)

1. `audio-orchestrator.code-workspace` - Enable Pylance language server
2. `docs/getting-started/local-development.md` - Add comprehensive virtual environment setup guide
3. `services/stt/.venv/` - Delete directory
4. `services/discord/.venv/` - Delete directory (was missing from original plan)

The plan is now **ready for implementation** with all critical issues resolved.
