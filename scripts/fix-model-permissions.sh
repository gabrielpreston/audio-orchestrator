#!/bin/bash
# Fix model directory permissions for non-root container users
# This script ensures model directories are writable by the container user

set -euo pipefail

MODEL_DIR="${MODEL_DIR:-/app/models}"
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

# Only fix permissions if running as non-root
if [ "$(id -u)" != "0" ]; then
    # Ensure model directory exists
    mkdir -p "${MODEL_DIR}"

    # Try to fix ownership (may fail if not root, but will work if directory is mounted)
    chown -R "${PUID}:${PGID}" "${MODEL_DIR}" 2>/dev/null || true

    # Ensure directory is writable
    chmod -R 755 "${MODEL_DIR}" 2>/dev/null || true

    # Remove any stale lock files from previous runs
    find "${MODEL_DIR}" -name "*.lock" -type f -delete 2>/dev/null || true

    echo "Model directory permissions checked: ${MODEL_DIR}"
fi

# Execute the original command
exec "$@"

