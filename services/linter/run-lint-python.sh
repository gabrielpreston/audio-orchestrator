#!/usr/bin/env bash
set -euo pipefail

echo "Running Python linting with Ruff..."

echo "Running ruff linting and formatting checks..."
ruff check services
ruff format --check services

echo "Running type checking with mypy..."
mypy services

echo "Python linting complete!"
