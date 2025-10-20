#!/usr/bin/env bash
set -euo pipefail

if [[ $# -eq 0 ]]; then
    echo "Usage: $0 <linter-name> [args...]"
    echo "Available linters: black, isort, ruff, mypy, yamllint, hadolint, checkmake, markdownlint, actionlint"
    exit 1
fi

LINTER=$1
shift

case "$LINTER" in
    black)
        if [[ $# -gt 0 ]]; then
            black "$@"
        else
            black --check services
        fi
        ;;
    isort)
        if [[ $# -gt 0 ]]; then
            isort "$@"
        else
            isort --check-only services
        fi
        ;;
    ruff)
        if [[ $# -gt 0 ]]; then
            ruff "$@"
        else
            ruff check services
        fi
        ;;
    mypy)
        if [[ $# -gt 0 ]]; then
            mypy "$@"
        else
            mypy services
        fi
        ;;
    yamllint)
        if [[ $# -gt 0 ]]; then
            yamllint "$@"
        else
            yamllint -c .yamllint docker-compose.yml .github/workflows/*.y*ml
        fi
        ;;
    hadolint)
        if [[ $# -gt 0 ]]; then
            hadolint "$@"
        else
            find services -type f -name 'Dockerfile' -exec hadolint {} \;
        fi
        ;;
    checkmake)
        if [[ $# -gt 0 ]]; then
            checkmake "$@"
        else
            checkmake --config .checkmake.yaml Makefile
        fi
        ;;
    markdownlint)
        if [[ $# -gt 0 ]]; then
            markdownlint "$@"
        else
            markdownlint --config .markdownlint.yaml README.md AGENTS.md 'docs/**/*.md'
        fi
        ;;
    actionlint)
        if [[ $# -gt 0 ]]; then
            actionlint "$@"
        else
            actionlint .github/workflows/*.y*ml
        fi
        ;;
    *)
        echo "Unknown linter: $LINTER" >&2
        echo "Available linters: black, isort, ruff, mypy, yamllint, hadolint, checkmake, markdownlint, actionlint" >&2
        exit 1
        ;;
esac
