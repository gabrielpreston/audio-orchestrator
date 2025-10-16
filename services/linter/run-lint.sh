#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 0 ]]; then
  exec "$@"
fi

# Run linting directly without make dependency
echo "Running Python linting..."

# Black formatting check
echo "Checking code formatting with black..."
black --check services

# Import sorting check
echo "Checking import sorting with isort..."
isort --check-only services

# Ruff linting
echo "Running ruff linting..."
ruff check services

# Type checking
echo "Running type checking with mypy..."
mypy services

# YAML linting
echo "Linting YAML files..."
yamllint docker-compose.yml

# Dockerfile linting
echo "Linting Dockerfiles..."
hadolint services/discord/Dockerfile
hadolint services/stt/Dockerfile
hadolint services/llm/Dockerfile
hadolint services/orchestrator/Dockerfile
hadolint services/tts/Dockerfile

# Markdown linting
echo "Linting Markdown files..."
markdownlint README.md AGENTS.md docs/*.md

echo "All linting checks passed!"
