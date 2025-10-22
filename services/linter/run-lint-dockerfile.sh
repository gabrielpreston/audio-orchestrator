#!/usr/bin/env bash
set -euo pipefail

echo "Linting Dockerfiles..."
# Auto-discover all Dockerfiles in services/
find services -type f -name 'Dockerfile' -exec hadolint --config .hadolint.yaml {} \;

echo "Dockerfile linting complete!"
