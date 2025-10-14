#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 0 ]]; then
  exec "$@"
fi

echo "Running Python linters..."
make lint-python

echo "Running Dockerfile linters..."
make lint-dockerfiles

echo "Running Docker Compose linters..."
make lint-compose

echo "Running Makefile linters..."
make lint-makefile

echo "Running Markdown linters..."
make lint-markdown

echo "Running mobile app linters..."
make lint-mobile

echo "Running TypeScript linters..."
make lint-typescript

echo "All linters completed successfully!"
