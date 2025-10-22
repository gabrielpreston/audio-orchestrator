#!/usr/bin/env bash
set -euo pipefail

echo "Linting Markdown files..."
# Auto-discover all Markdown files
markdownlint --config .markdownlint.yaml README.md AGENTS.md 'docs/**/*.md'

echo "Markdown linting complete!"
