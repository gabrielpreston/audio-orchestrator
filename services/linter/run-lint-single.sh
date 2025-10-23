#!/usr/bin/env bash
set -euo pipefail

# Run a single linter based on the argument passed
# Usage: run-lint-single.sh <linter-name>
# Example: run-lint-single.sh black

LINTER_NAME="${1:-}"

if [ -z "$LINTER_NAME" ]; then
    echo "Error: No linter name provided"
    echo "Usage: $0 <linter-name>"
    echo "Available linters: black, ruff, mypy, yamllint, markdownlint, hadolint, checkmake, bandit, detect-secrets, radon"
    exit 1
fi

case "$LINTER_NAME" in
    "black")
        echo "Running Black formatting check..."
        black --check services
        ;;
    "ruff")
        echo "Running Ruff linting and formatting checks..."
        ruff check services
        ruff format --check services
        ;;
    "mypy")
        echo "Running type checking with mypy..."
        mypy services
        ;;
    "yamllint")
        echo "Running YAML linting..."
        yamllint -c .yamllint docker-compose.yml .github/workflows/*.yaml
        ;;
    "markdownlint")
        echo "Running Markdown linting..."
        markdownlint README.md AGENTS.md docs/*.md
        ;;
    "hadolint")
        echo "Running Dockerfile linting..."
        hadolint services/*/Dockerfile
        ;;
    "checkmake")
        echo "Running Makefile linting..."
        checkmake Makefile
        ;;
    "bandit")
        echo "Running security analysis with bandit..."
        bandit -r services -f json -o bandit-report.json
        ;;
    "detect-secrets")
        echo "Running secret detection..."
        detect-secrets scan --baseline .secrets.baseline
        ;;
    "radon")
        echo "Running complexity analysis with radon..."
        radon cc services -a
        ;;
    *)
        echo "Error: Unknown linter '$LINTER_NAME'"
        echo "Available linters: black, ruff, mypy, yamllint, markdownlint, hadolint, checkmake, bandit, detect-secrets, radon"
        exit 1
        ;;
esac

echo "Linting with $LINTER_NAME complete!"
