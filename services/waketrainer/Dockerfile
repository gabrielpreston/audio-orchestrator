# Wake Word Training Tool
# Multi-stage build for optimal caching of large dependencies
# Extends python-ml base (has PyTorch, transformers, librosa, etc.)
# hadolint ignore=DL3007

# Stage 1: Large dependencies (rarely change)
# These packages are large and change infrequently, cached separately
FROM ghcr.io/gabrielpreston/python-ml:latest AS deps-large

WORKDIR /workspace

# Copy and install large dependencies first
COPY services/waketrainer/requirements-large.txt /workspace/services/waketrainer/requirements-large.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /workspace/services/waketrainer/requirements-large.txt

# Stage 2: Medium dependencies
# Includes large dependencies and adds medium-sized packages
FROM deps-large AS deps-medium

WORKDIR /workspace

# Copy medium dependencies (requirements-large.txt already exists from previous stage)
COPY services/waketrainer/requirements-medium.txt /workspace/services/waketrainer/requirements-medium.txt
WORKDIR /workspace/services/waketrainer
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements-medium.txt

# Stage 3: System dependencies and git clone
FROM deps-medium AS deps-system

WORKDIR /workspace

# Install Piper TTS system dependencies (required for synthetic data generation)
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    libespeak-ng1 \
    && rm -rf /var/lib/apt/lists/*

# Clone dscripka fork of piper-sample-generator (required for openWakeWord training)
# This is the fork used by openWakeWord, not the upstream rhasspy version
# Use cache mount to avoid re-cloning on every build
RUN --mount=type=cache,target=/tmp/git-cache \
    if [ ! -d "/tmp/git-cache/piper-sample-generator" ]; then \
    git clone --depth 1 https://github.com/dscripka/piper-sample-generator /tmp/git-cache/piper-sample-generator || \
    (echo "Warning: Failed to clone piper-sample-generator. Synthetic data generation may not work." && exit 0); \
    fi && \
    cp -r /tmp/git-cache/piper-sample-generator /workspace/piper-sample-generator || \
    (echo "Warning: Failed to copy piper-sample-generator. Synthetic data generation may not work." && exit 0)

# Final stage: Base requirements and frequently-changing files
FROM deps-system

WORKDIR /workspace

# Install only base requirements (wake trainer deps already installed in previous stages)
# This avoids re-downloading large packages like TensorFlow that are already installed
COPY services/requirements-base.txt /workspace/services/requirements-base.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /workspace/services/requirements-base.txt

# Create openwakeword resources directory with proper permissions
# This directory is needed for adversarial text generation during training
# Must be created as root during build since container runs as non-root user
RUN python -c "import openwakeword; import os; \
    resources_dir = os.path.join(os.path.dirname(openwakeword.__file__), 'resources'); \
    os.makedirs(resources_dir, exist_ok=True); \
    os.chmod(resources_dir, 0o777)" || \
    echo "Warning: Could not create openwakeword resources directory"

# Copy Piper TTS model JSON config from local codebase to backup location
# This ensures the JSON file is available at runtime even when volume mount overrides models directory
# Using local codebase is more reliable than relying on cloned repo structure or GitHub downloads
# Place in /app (not /workspace) to avoid being overridden by workspace volume mount
COPY piper-sample-generator/models/en-us-libritts-high.pt.json /app/piper-json-backup.json

# Copy training script (changes most frequently, so last)
COPY services/waketrainer/run-train.sh /usr/local/bin/run-train.sh
RUN chmod +x /usr/local/bin/run-train.sh

# Set PYTHONPATH to include piper-sample-generator so generate_samples can be imported
ENV PYTHONPATH=/workspace/piper-sample-generator:${PYTHONPATH}

# No ENTRYPOINT - let Makefile specify exactly what to run
# Scripts are mounted as volumes at runtime from services/waketrainer/

