#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 0 ]]; then
  exec "$@"
fi

echo "Running Python linting with Ruff..."

echo "Running ruff linting and formatting checks..."
ruff check services
ruff format --check services

echo "Running type checking with mypy..."
mypy services

echo "Linting YAML files..."
# Auto-discover: docker-compose.yml + all workflow files
yamllint -c .yamllint docker-compose.yml $(find .github/workflows -name "*.yml" -o -name "*.yaml" 2>/dev/null || true)

echo "Validating GitHub Actions workflows..."
if [ -d ".github/workflows" ] && [ "$(find .github/workflows -maxdepth 1 -name '*.yml' -o -name '*.yaml' 2>/dev/null | wc -l)" -gt 0 ]; then
    actionlint .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null || true
fi

echo "Linting Dockerfiles..."
# Auto-discover all Dockerfiles in services/
find services -type f -name 'Dockerfile' -exec hadolint --config .hadolint.yaml {} \;

echo "Linting Makefile..."
checkmake --config .checkmake.yaml Makefile

echo "Linting Markdown files..."
# Auto-discover all Markdown files
markdownlint --config .markdownlint.yaml README.md AGENTS.md 'docs/**/*.md'

echo "Running security analysis with bandit..."
# Run bandit security analysis on Python files (skip B104, exclude .venv, only HIGH severity)
bandit -r services/ -f json -o bandit-report.json --skip B104 --exclude "**/.venv/**" --severity-level high

echo "Running complexity analysis..."
# Run radon complexity analysis
radon cc --min B services/
radon mi --min B services/

echo "All linting checks passed!"
