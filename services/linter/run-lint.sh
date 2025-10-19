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
yamllint -c .yamllint docker-compose.yml .github/workflows/*.y*ml 2>/dev/null

echo "Linting Dockerfiles..."
# Auto-discover all Dockerfiles in services/
find services -type f -name 'Dockerfile' -exec hadolint --config .hadolint.yaml {} \;

echo "Linting Makefile..."
checkmake --config .checkmake.yaml Makefile

echo "Linting Markdown files..."
# Auto-discover all Markdown files
markdownlint --config .markdownlint.yaml README.md AGENTS.md 'docs/**/*.md'

echo "All linting checks passed!"