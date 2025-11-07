#!/usr/bin/env bash
set -euo pipefail

# Check Python syntax by compiling Python files
# Usage: check-syntax.sh [TARGET]
#   TARGET: Optional file or directory path (default: check all services/)

TARGET="${1:-}"

check_file() {
    local file="$1"
    if ! python3 -m py_compile "$file" 2>/dev/null; then
        echo "→ Syntax error in: $file"
        python3 -m py_compile "$file" 2>&1 | head -5 | sed "s/^/  /"
        return 1
    fi
    return 0
}

errors=0

if [ -z "$TARGET" ]; then
    # Check all services
    echo "→ Checking Python syntax for all services"
    while IFS= read -r -d '' pyfile; do
        if ! check_file "$pyfile"; then
            errors=$((errors + 1))
        fi
    done < <(find services -type f -name "*.py" ! -path "*/__pycache__/*" ! -path "*/.venv/*" -print0)
else
    # Check specific target
    echo "→ Checking Python syntax for: $TARGET"
    if [ -f "$TARGET" ]; then
        if [ "${TARGET##*.}" != "py" ]; then
            echo "→ Error: $TARGET is not a Python file"
            exit 1
        fi
        if ! check_file "$TARGET"; then
            errors=$((errors + 1))
        fi
    elif [ -d "$TARGET" ]; then
        while IFS= read -r -d '' pyfile; do
            if ! check_file "$pyfile"; then
                errors=$((errors + 1))
            fi
        done < <(find "$TARGET" -type f -name "*.py" ! -path "*/__pycache__/*" ! -path "*/.venv/*" -print0 2>/dev/null)
    else
        echo "→ Error: $TARGET does not exist"
        exit 1
    fi
fi

if [ $errors -eq 0 ]; then
    echo "→ All Python files compile successfully"
    exit 0
else
    echo "→ Found $errors file(s) with syntax errors"
    exit 1
fi

