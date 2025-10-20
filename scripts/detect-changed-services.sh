#!/usr/bin/env bash
# Detect which services changed based on git diff
# Returns: space-separated service list, "all", "base-images", or "none"

set -euo pipefail

# Configuration
SERVICES="discord stt llm orchestrator tts"

# Default: compare working directory + staged changes against HEAD
# Can override with argument: ./detect-changed-services.sh origin/main
COMPARE_REF="${1:-HEAD}"

# Check if git repo exists
if [ ! -d ".git" ]; then
    echo "all"  # Fallback: no git history
    exit 0
fi

# Get changed files (working dir, staged, and untracked)
CHANGED_FILES=$(git diff --name-only "$COMPARE_REF" 2>/dev/null || echo "")
STAGED_FILES=$(git diff --name-only --cached 2>/dev/null || echo "")
UNTRACKED_FILES=$(git ls-files --others --exclude-standard 2>/dev/null || echo "")
ALL_CHANGED="$CHANGED_FILES $STAGED_FILES $UNTRACKED_FILES"

# If no changes, return none
if [ -z "$ALL_CHANGED" ]; then
    echo "none"
    exit 0
fi

# Check for build context changes
if echo "$ALL_CHANGED" | grep -q "\.dockerignore\|docker-compose\.yml"; then
    echo "all"
    exit 0
fi

# Check for changes that affect ALL services
if echo "$ALL_CHANGED" | grep -q "services/common/\|requirements-base.txt\|services/requirements-"; then
    echo "all"
    exit 0
fi

# Check for base image changes
if echo "$ALL_CHANGED" | grep -q "services/base/"; then
    echo "base-images"
    exit 0
fi

# Check for service-specific changes
CHANGED_SERVICES=""
for service in $SERVICES; do
    if echo "$ALL_CHANGED" | grep -q "services/$service/"; then
        CHANGED_SERVICES="$CHANGED_SERVICES $service"
    fi
done

# Return result
if [ -z "$CHANGED_SERVICES" ]; then
    echo "none"
else
    echo "$CHANGED_SERVICES" | xargs  # trim whitespace
fi
