#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

print_status "$CYAN" "Applying automatic fixes..."

# Apply Python formatting fixes
print_status "$BLUE" "Fixing Python code formatting with black..."
black services

print_status "$BLUE" "Fixing import sorting with isort..."
isort services

print_status "$BLUE" "Applying ruff fixes..."
ruff check --fix services

# Apply Markdown formatting fixes
print_status "$BLUE" "Fixing Markdown formatting..."
markdownlint --fix README.md AGENTS.md 'docs/**/*.md'

print_status "$GREEN" "✅ All automatic fixes applied!"
