# Docker Log Analysis: Model Loading Improvements

**Date**: 2025-10-31
**Analysis**: Deep log analysis with systematic fixes for permission issues, logging improvements, and warning suppression

## Executive Summary

Analysis of docker logs revealed:

1.  **Critical Permission Issues**: Root-owned model directories preventing non-root containers from writing
2.  **Bark Cache Path Issues**: Bark trying to write to `/app/models/suno` without proper permissions
3.  **Deprecation Warning Noise**: TRANSFORMERS_CACHE and pkg_resources warnings cluttering logs
4.  **Excellent Logging Foundation**: Enhanced logging from previous work is working well

## Timeline Overview

### Service Startup Sequence

1.  **Infrastructure** (0-2s): Jaeger, OTEL Collector, Prometheus start
2.  **Core Services** (2-3s): STT, Audio, Monitoring, Orchestrator start
3.  **Model Services** (3-5s): FLAN, Guardrails, Bark start model loading
4.  **Discord & Testing** (4-6s): Final services start

### Key Events Observed

-  **STT**: Cache load successful (1.68s total, 214ms model init)
-  **FLAN**: Cache load successful (445ms total, 293ms model, 153ms tokenizer)
-  **Guardrails**: Permission error during model load (returned None)
-  **Bark**: Permission denied when creating `/app/models/suno` (65ms before failure)
-  **Audio**: Permission warning for `/app/models` (non-fatal, MetricGAN lazy-loaded)

## Issues Identified

### 1. Host Directory Permissions (CRITICAL)

**Problem**: Model directories created by Docker are owned by root (UID 0), but containers run as UID 1000.

**Evidence**:

```json
audio-1: {"diagnostics": {"exists": true, "readable": true, "writable": false, "user_id": 0, "group_id": 0, "permissions": "755"}}
bark-1: PermissionError: [Errno 13] Permission denied: '/app/models/suno'
guardrails-1: cache_directory_not_writable
```

**Root Cause**: When Docker creates host directories that don't exist, they're owned by root. Containers with `user: "${PUID:-1000}"` can't write to them.

**Fix**: Added `models-fix-permissions` Makefile target that:

-  Creates directories if missing
-  Checks ownership and fixes if root-owned
-  Sets correct permissions (755)
-  Runs automatically before `make run`

### 2. Bark Cache Directory Structure

**Problem**: Bark library hardcodes cache to `~/.cache/suno/bark_v0`, but `/app` isn't writable.

**Evidence**:

```json
bark-1: {"error": "[Errno 13] Permission denied: '/app/models/suno'"}
```

**Root Cause**: Bark doesn't fully respect `XDG_CACHE_HOME`. It falls back to `HOME/.cache` when creating subdirectories.

**Fix**:

-  Mount separate volume: `./services/models/bark/.cache:/app/.cache`
-  Ensure `/app/.cache/suno` exists and is writable at startup
-  Added to `models-fix-permissions` target

### 3. Deprecation Warning Noise

**Problem**: TRANSFORMERS_CACHE and pkg_resources warnings appear in logs despite migration to HF_HOME.

**Evidence**:

```text
flan-1: /usr/local/lib/python3.11/site-packages/transformers/utils/hub.py:110: FutureWarning: Using `TRANSFORMERS_CACHE` is deprecated
```

**Root Cause**: Transformers library checks for `TRANSFORMERS_CACHE` env var during import, even if `HF_HOME` is set. Base Dockerfile still sets `TRANSFORMERS_CACHE` for backward compatibility.

**Fix**:

-  Added warning suppression in `services/common/model_utils.py` (before transformers import)
-  Added warning suppression in `services/common/app_factory.py` (for all services)
-  Filters target `FutureWarning` from `transformers.utils.hub` and `transformers` modules

## Log Hygiene Analysis

### Excellent Structured Logging (Keep)

✅ **Phase Tracking**: All model loading logs include `phase` field

-  Examples: `"phase": "cache_check"`, `"phase": "download_start"`, `"phase": "load_complete"`

✅ **Timing Metrics**: Duration tracking at multiple levels

-  Examples: `cache_check_duration_ms`, `total_duration_ms`, `download_duration_ms`

✅ **Error Context**: Comprehensive error information

-  Examples: `error_type`, `duration_ms`, `exc_info=True`, permission diagnostics

✅ **Status Visibility**: Clear indication of cache hit/miss, download progress

### Areas for Improvement (Implemented)

✅ **Permission Diagnostics**: Added detailed permission checking with ownership info
✅ **Startup Permission Checks**: Services now verify directories are writable and log warnings
✅ **Bark Cache Path**: Explicit logging for `/app/.cache/suno` creation and permissions

## Implementation Details

### 1. Makefile: `models-fix-permissions` Target

```makefile
models-fix-permissions: ## Fix host model directory permissions
 @for dir in stt flan-t5 guardrails bark audio; do
  # Create if missing, fix ownership if root-owned
 done
 # Special handling for Bark .cache subdirectory
```

**Usage**: Automatically runs before `make run`. Can also be run manually:

```bash
make models-fix-permissions
```

### 2. Docker Compose: Bark Cache Volume

```yaml
volumes:
  - ./services/models/bark:/app/models
  - ./services/models/bark/.cache:/app/.cache  # NEW
```

### 3. Warning Suppression

**Location**: `services/common/model_utils.py` (before transformers import)

```python
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module="transformers.utils.hub",
    message=".*TRANSFORMERS_CACHE.*",
)
```

## Testing Recommendations

1.  **Clean Start Test**:

   ```bash
   make stop
   sudo rm -rf ./services/models/{audio,bark,guardrails}
   make run
   # Verify: make logs | grep -i permission
   ```

1.  **Permission Fix Test**:

   ```bash
   sudo chown -R root:root ./services/models/{audio,bark,guardrails}
   make models-fix-permissions
   make run
   ```

1.  **Bark Model Download Test**:

   ```bash
   make models-force-download-service SERVICE=bark
   make logs SERVICE=bark
   # Verify: Should see successful model download without permission errors
   ```

## Expected Log Improvements

### Before

```json
guardrails-1: {"error": "cache_directory_not_writable", ...}
bark-1: {"error": "[Errno 13] Permission denied: '/app/models/suno'", ...}
flan-1: FutureWarning: Using `TRANSFORMERS_CACHE` is deprecated...
```

### After

```json
# Permission warnings only if truly unfixable
guardrails-1: {"event": "guardrails.model_load_start", "phase": "load_start"}
bark-1: {"event": "bark.cache_subdirectory_ready", "cache_subdir": "/app/.cache/suno"}
# No TRANSFORMERS_CACHE warnings
```

## Success Metrics

✅ Model directories created with correct ownership before containers start
✅ Bark can write to `/app/.cache/suno/bark_v0`
✅ No TRANSFORMERS_CACHE deprecation warnings in logs
✅ Permission errors include detailed diagnostics for troubleshooting
✅ Enhanced logging provides clear visibility into model loading phases

## Files Modified

1.  `Makefile`: Added `models-fix-permissions` target, integrated into `run` target
2.  `docker-compose.yml`: Added Bark `.cache` volume mount
3.  `services/common/app_factory.py`: Added transformers warning suppression
4.  `services/common/model_utils.py`: Added transformers warning suppression (before import)
5.  `services/bark/app.py`: Added `.cache/suno` directory creation and permission check

## Next Steps (Future Enhancements)

1.  **Entrypoint Script**: Consider adding `fix-model-permissions.sh` as Docker entrypoint for services that need it
2.  **Health Check**: Add model directory permissions to health checks (non-blocking warnings)
3.  **Documentation**: Update setup docs to mention permission requirements
4.  **CI/CD**: Add permission check as pre-startup validation step
