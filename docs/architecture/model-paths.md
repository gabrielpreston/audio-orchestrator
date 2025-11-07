# Model Path Resolution Pattern

This document describes the consistent path resolution pattern used across all services for automatic model downloads.

## Core Principle

**Environment variables are always priority** - they point to local disk paths that containers mount. Services automatically download models on startup using the `BackgroundModelLoader` pattern, respecting environment variables for path resolution.

## Path Resolution Priority

The path resolution follows this priority order:

1.  **Priority 1**: Service-specific environment variable (if set)

   -  Example: `WAKE_MODEL_PATHS`, `FASTER_WHISPER_MODEL_PATH`
   -  These point to local disk paths that containers mount

1.  **Priority 2**: Library-specific environment variables (for libraries that require them)

   -  Example: `HF_HOME`, `TRANSFORMERS_CACHE`, `METRICGAN_MODEL_SAVEDIR`
   -  Some libraries (Transformers, HuggingFace Hub, SpeechBrain) require specific env vars
   -  These cannot be removed or changed

1.  **Priority 3**: Default directory (`./services/models/{service}/`)

   -  Used when no env vars are set
   -  Ensures consistent behavior across environments

## Service-Specific Patterns

### Wake Detection

**Pattern**: `WAKE_MODEL_PATHS` (comma-separated) → extract directory from first path → default: `./services/models/wake/`

**Implementation**:

-  Parse `WAKE_MODEL_PATHS` as comma-separated list
-  Use first path from list
-  If path is a file, use parent directory
-  If path is a directory, use directly
-  Fallback to `./services/models/wake/` if not set

**Model Filtering**:

The wake detection service automatically filters discovered model files to only include actual wake word models:

-  **Infrastructure models excluded**: `embedding_model`, `melspectrogram`, `silero_vad` are automatically filtered out
-  **Format preference**: ONNX format is preferred over TFLite (required on Linux x86_64)
-  **Deduplication**: When both `.onnx` and `.tflite` versions of the same model exist, only the ONNX version is used
-  **Universal filtering**: Filtering applies to both user-provided paths (`WAKE_MODEL_PATHS`) and auto-discovered models

**Why filtering is needed**:

`openwakeword.utils.download_models()` downloads all model files including infrastructure models (embedding, melspectrogram, VAD) that are not wake word models.

Passing these infrastructure models to `WakeWordModel()` causes TensorFlow Lite errors. The filtering ensures only compatible wake word models are loaded.

**Example**:

```bash
# Single file path - uses parent directory
WAKE_MODEL_PATHS=/custom/path/model.onnx
# Resolves to: /custom/path/
# Note: Infrastructure models in this directory are automatically excluded

# Directory path - uses directly
WAKE_MODEL_PATHS=/custom/models
# Resolves to: /custom/models
# Note: Only wake word models (ONNX preferred) are loaded from this directory

# Multiple paths - uses first
WAKE_MODEL_PATHS=/path1/model.onnx,/path2/model2.onnx
# Resolves to: /path1/
# Note: All paths are filtered to exclude infrastructure models
```

### STT (Faster-Whisper)

**Pattern**: `FASTER_WHISPER_MODEL_PATH` → default: `./services/models/stt/medium.en/`

**Implementation**:

-  Check `FASTER_WHISPER_MODEL_PATH` env var first
-  Fallback to `./services/models/stt/medium.en/` if not set

**Note**: Runtime services use config system (`ServiceConfig.faster_whisper.model_path`), but download scripts must prioritize env vars since containers mount local disk paths specified by env vars.

**Example**:

```bash
# Custom path
FASTER_WHISPER_MODEL_PATH=/custom/models/whisper
# Resolves to: /custom/models/whisper

# Default (if not set)
# Resolves to: ./services/models/stt/medium.en/
```

### FLAN-T5 (Transformers)

**Pattern**: `HF_HOME` or `TRANSFORMERS_CACHE` → default: `./services/models/flan-t5/`

**Implementation**:

-  Check `HF_HOME` or `TRANSFORMERS_CACHE` env vars (library requirement)
-  Libraries require these env vars, so they take precedence
-  Fallback to `./services/models/flan-t5/` if not set

**Example**:

```bash
# Custom HuggingFace cache
HF_HOME=/custom/huggingface
# Resolves to: /custom/huggingface

# Transformers cache
TRANSFORMERS_CACHE=/custom/transformers
# Resolves to: /custom/transformers

# Default (if neither set)
# Resolves to: ./services/models/flan-t5/
```

## Runtime Services

Runtime services use:

-  Config system (`ServiceConfig`) for configuration
-  Environment variable overrides where applicable
-  Library-specific env vars for library requirements
-  **BackgroundModelLoader** for automatic model downloads on service startup

**Note**: Services automatically download models when they start using the `BackgroundModelLoader` pattern. No pre-download scripts are needed.

## Implementation Guidelines

### For New Download Scripts

1.  **Check service-specific env var first** (if applicable)
2.  **Check library-specific env vars** (if library requires them)
3.  **Fallback to default directory** (`./services/models/{service}/`)

### Example Implementation (Python)

```python
import os
from pathlib import Path

def resolve_model_directory(service_name: str, env_var: str | None = None, library_env_vars: list[str] | None = None) -> Path:
    """Resolve model directory using consistent pattern."""
    # Priority 1: Service-specific env var
    if env_var:
        env_value = os.getenv(env_var)
        if env_value:
            return Path(env_value)

    # Priority 2: Library-specific env vars
    if library_env_vars:
        for lib_env_var in library_env_vars:
            lib_value = os.getenv(lib_env_var)
            if lib_value:
                return Path(lib_value)

    # Priority 3: Default directory
    return Path(f"./services/models/{service_name}")
```

### Example Implementation (Shell)

```bash
# Priority 1: Service-specific env var
if [ -n "${SERVICE_MODEL_PATH:-}" ]; then
    MODEL_DIR="${SERVICE_MODEL_PATH}"
# Priority 2: Library-specific env vars
elif [ -n "${HF_HOME:-}" ]; then
    MODEL_DIR="${HF_HOME}"
elif [ -n "${TRANSFORMERS_CACHE:-}" ]; then
    MODEL_DIR="${TRANSFORMERS_CACHE}"
# Priority 3: Default directory
else
    MODEL_DIR="./services/models/${SERVICE_NAME}"
fi
```

## Migration Guide for Future Services

When adding a new service that requires model downloads:

1.  **Determine service-specific env var name** (if needed)

   -  Pattern: `{SERVICE}_MODEL_PATH` or `{SERVICE}_MODEL_PATHS`
   -  Use `_PATH` for single directory, `_PATHS` for comma-separated list

1.  **Check library requirements**

   -  If library requires specific env vars (e.g., `HF_HOME`), respect them
   -  Document library requirements in service documentation

1.  **Implement BackgroundModelLoader**

   -  Use the `BackgroundModelLoader` pattern for automatic model downloads
   -  Follow the priority order: service env var → library env vars → default
   -  Use consistent pattern as documented above

1.  **Update documentation**

   -  Add service to this document
   -  Document env var names and default paths
   -  Provide examples
