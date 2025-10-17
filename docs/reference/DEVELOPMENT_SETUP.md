# Development Environment Setup

This document describes the multi-virtual environment setup for the `discord-voice-lab` project, designed to provide optimal development experience with Cursor/VS Code.

## 🏗️ Architecture Overview

The project uses a **hybrid virtual environment approach**:

- **Global `.venv`**: Contains shared dependencies and `services.common` library
- **Service-specific `.venv`**: Each service has its own environment for unique dependencies
- **Multi-root workspace**: Cursor/VS Code configuration for seamless development

## 📁 Directory Structure

```
discord-voice-lab/
├── .venv/                           # Global environment (shared deps + services.common)
├── .vscode/settings.json           # Root workspace settings
├── discord-voice-lab.code-workspace # Multi-root workspace file
├── services/
│   ├── common/                     # Shared library (no .venv needed)
│   ├── discord/
│   │   ├── .venv/                  # Discord-specific environment
│   │   └── .vscode/settings.json   # Service-specific settings
│   ├── stt/
│   │   ├── .venv/                  # STT-specific environment
│   │   └── .vscode/settings.json   # Service-specific settings
│   ├── llm/
│   │   ├── .venv/                  # LLM-specific environment
│   │   └── .vscode/settings.json   # Service-specific settings
│   ├── orchestrator/
│   │   ├── .venv/                  # Orchestrator-specific environment
│   │   └── .vscode/settings.json   # Service-specific settings
│   └── tts/
│       ├── .venv/                  # TTS-specific environment
│       └── .vscode/settings.json   # Service-specific settings
```

## 🚀 Getting Started

### 1. Open the Multi-Root Workspace

```bash
# Open the workspace file in Cursor/VS Code
cursor discord-voice-lab.code-workspace
```

This will open all services as separate workspace folders with their own Python interpreters.

### 2. Service-Specific Development

When working on a specific service:

1. **Navigate to the service directory** (e.g., `services/discord/`)
2. **Cursor will automatically use the service's virtual environment**
3. **Imports will work correctly** for both service-specific and shared dependencies

### 3. Global Development

When working on shared code or running the full stack:

1. **Use the root workspace** (`.vscode/settings.json`)
2. **Global `.venv` contains all dependencies**
3. **All services can be imported and tested**

## 🔧 Environment Details

### Global Environment (`.venv/`)

**Purpose**: Shared dependencies and `services.common` library

**Contains**:
- Base requirements (`requirements-base.txt`)
- Development tools (`requirements-dev.txt`)
- All service dependencies (for full-stack development)

**Usage**: Root workspace, full-stack testing, shared library development

### Service-Specific Environments

Each service has its own `.venv/` with:

**Discord Service** (`services/discord/.venv/`):
- Base requirements + Discord-specific deps
- `discord.py[voice]`, `discord-ext-voice_recv`, `PyNaCl`, `rapidfuzz`, `webrtcvad`

**STT Service** (`services/stt/.venv/`):
- Base requirements + STT-specific deps
- `faster-whisper`, `python-multipart`

**LLM Service** (`services/llm/.venv/`):
- Base requirements + LLM-specific deps
- `llama-cpp-python`

**Orchestrator Service** (`services/orchestrator/.venv/`):
- Base requirements + Orchestrator-specific deps
- `mcp`, `instructor`

**TTS Service** (`services/tts/.venv/`):
- Base requirements + TTS-specific deps
- `piper-tts`, `prometheus_client`

## 🎯 Development Workflows

### Working on a Single Service

```bash
# Navigate to service directory
cd services/discord/

# Activate service environment
source .venv/bin/activate

# Run service-specific tests
python -m pytest

# Run service
python app.py
```

### Working on Shared Library

```bash
# Use global environment
cd /path/to/discord-voice-lab
source .venv/bin/activate

# Edit services/common/ files
# Cursor will provide full IntelliSense
```

### Full-Stack Development

```bash
# Use global environment
cd /path/to/discord-voice-lab
source .venv/bin/activate

# Run all services
make run

# Run tests
make test
```

## 🔍 Cursor/VS Code Configuration

### Multi-Root Workspace

The `discord-voice-lab.code-workspace` file provides:

- **Separate workspace folders** for each service
- **Service-specific Python interpreters**
- **Proper import resolution** for each service
- **Unified settings** across all services

### Service-Specific Settings

Each service has its own `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "./.venv/bin/python",
    "python.terminal.activateEnvironment": true,
    "python.analysis.extraPaths": [
        "../common",
        "../../services/common",
        "../../"
    ],
    "python.analysis.autoImportCompletions": true,
    "python.analysis.typeCheckingMode": "basic"
}
```

## 🧪 Testing the Setup

### Test Service Imports

```bash
# Test Discord service
cd services/discord/
source .venv/bin/activate
PYTHONPATH="../../" python -c "import services.common.logging; import discord; print('Discord service imports working!')"

# Test STT service
cd services/stt/
source .venv/bin/activate
PYTHONPATH="../../" python -c "import services.common.logging; import faster_whisper; print('STT service imports working!')"
```

### Test Global Environment

```bash
# Test global environment
cd /path/to/discord-voice-lab
source .venv/bin/activate
python -c "import services.common.logging; import fastapi; import discord; print('Global environment working!')"
```

## 🛠️ Troubleshooting

### Import Errors

If you get `ModuleNotFoundError: No module named 'services'`:

1. **Check PYTHONPATH**: Ensure the project root is in PYTHONPATH
2. **Verify virtual environment**: Make sure you're using the correct `.venv`
3. **Check Cursor settings**: Ensure the Python interpreter is set correctly

### Service-Specific Issues

If a service can't import its dependencies:

1. **Check service environment**: `source .venv/bin/activate`
2. **Verify dependencies**: `pip list` to see installed packages
3. **Reinstall if needed**: `pip install -r requirements.txt`

### Cursor/VS Code Issues

If IntelliSense isn't working:

1. **Reload window**: `Ctrl+Shift+P` → "Developer: Reload Window"
2. **Select Python interpreter**: `Ctrl+Shift+P` → "Python: Select Interpreter"
3. **Check workspace**: Ensure you're in the correct workspace folder

## 📋 Benefits

### ✅ Advantages

- **Complete isolation** between services
- **Service-specific dependencies** without conflicts
- **Full IntelliSense** for each service
- **Independent development** of services
- **Shared library access** via `services.common`
- **Docker compatibility** maintained

### 🎯 Use Cases

- **Service development**: Work on one service without affecting others
- **Dependency management**: Each service manages its own dependencies
- **Testing**: Test services independently
- **Debugging**: Isolate issues to specific services
- **Team development**: Different developers can work on different services

## 🔄 Maintenance

### Adding New Dependencies

**For a specific service**:
```bash
cd services/[service-name]/
source .venv/bin/activate
pip install [new-package]
pip freeze > requirements.txt
```

**For shared dependencies**:
```bash
cd /path/to/discord-voice-lab
source .venv/bin/activate
pip install [new-package]
# Update requirements-base.txt
```

### Updating Dependencies

**Service-specific**:
```bash
cd services/[service-name]/
source .venv/bin/activate
pip install --upgrade [package]
```

**Global**:
```bash
cd /path/to/discord-voice-lab
source .venv/bin/activate
pip install --upgrade [package]
```

This setup provides the best of both worlds: complete service isolation with shared library access, optimized for the `discord-voice-lab` project architecture.

