#!/bin/bash
# Authenticate Docker to GHCR (extracted for shell scripts)
# Priority: GHCR_TOKEN > GitHub CLI

set -euo pipefail

# Resolve script directory for reliable path handling
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if already authenticated
REGISTRY="${REGISTRY:-ghcr.io/gabrielpreston}"
CACHE_TEST_REF="${REGISTRY}/cache:services"

if ! (docker pull "${CACHE_TEST_REF}" >/dev/null 2>&1 && \
      docker push "${CACHE_TEST_REF}" >/dev/null 2>&1) 2>/dev/null; then
    echo "Authenticating Docker to GHCR..."
    if [ -n "${GHCR_TOKEN:-}" ]; then
        GHCR_USER="${GHCR_USERNAME:-$(gh api user --jq .login 2>/dev/null || echo $(whoami))}"
        echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USER}" --password-stdin || \
            { echo "Error: Failed to authenticate Docker to GHCR using GHCR_TOKEN" >&2; exit 1; }
    elif command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
        echo "$(gh auth token)" | docker login ghcr.io -u "$(gh api user --jq .login 2>/dev/null || echo $(whoami))" --password-stdin || \
            { echo "Error: Failed to authenticate Docker to GHCR" >&2; exit 1; }
    else
        echo "Error: Cannot authenticate to GHCR. Either:" >&2
        echo "  1. Set GHCR_TOKEN environment variable (with write:packages scope)" >&2
        echo "  2. Authenticate GitHub CLI: gh auth login --scopes write:packages" >&2
        exit 1
    fi
fi

