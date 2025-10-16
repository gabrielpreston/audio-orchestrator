#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 0 ]]; then
  exec "$@"
fi

echo "Running Python linting..."

echo "Checking code formatting with black..."
black --check services

echo "Checking import sorting with isort..."
isort --check-only services

echo "Running ruff linting..."
ruff check services

echo "Running type checking with mypy..."
mypy services

echo "Linting YAML files..."
# Auto-discover: docker-compose.yml + all workflow files
yamllint docker-compose.yml .github/workflows/*.yaml .github/workflows/*.yml 2>/dev/null || true

echo "Linting Dockerfiles..."
# Auto-discover all Dockerfiles in services/
find services -type f -name 'Dockerfile' -exec hadolint {} \;

echo "Linting Makefile..."
checkmake Makefile

echo "Linting Markdown files..."
# Auto-discover all Markdown files
markdownlint README.md AGENTS.md 'docs/**/*.md'

echo "All linting checks passed!"