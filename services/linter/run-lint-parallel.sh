#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to run a linter and capture its output
run_linter() {
    local name=$1
    shift
    local command="$@"
    local output_file="/tmp/lint_${name}.log"
    local error_file="/tmp/lint_${name}_error.log"
    
    print_status "$BLUE" "Starting $name linter..."
    
    if $command > "$output_file" 2> "$error_file"; then
        print_status "$GREEN" "✓ $name passed"
        return 0
    else
        local exit_code=$?
        print_status "$RED" "✗ $name failed (exit code: $exit_code)"
        
        # Store failure info for later reporting
        echo "$name:$exit_code" >> /tmp/lint_failures.txt
        
        # Capture output for aggregation
        {
            echo "=== $name OUTPUT ==="
            cat "$output_file" 2>/dev/null || true
            echo "=== $name ERRORS ==="
            cat "$error_file" 2>/dev/null || true
            echo ""
        } >> /tmp/lint_aggregated_output.log
        
        return $exit_code
    fi
}

# Clean up any previous run artifacts
rm -f /tmp/lint_*.log /tmp/lint_failures.txt /tmp/lint_aggregated_output.log

print_status "$CYAN" "Running all linters in parallel..."

# Start all linters in parallel
(
    run_linter "black" black --check services
) &
BLACK_PID=$!

(
    run_linter "isort" isort --check-only services
) &
ISORT_PID=$!

(
    run_linter "ruff" ruff check services
) &
RUFF_PID=$!

(
    run_linter "mypy" mypy services
) &
MYPY_PID=$!

(
    run_linter "yamllint" yamllint docker-compose.yml .github/workflows/*.y*ml 2>/dev/null
) &
YAMLLINT_PID=$!

(
    run_linter "hadolint" find services -type f -name 'Dockerfile' -exec hadolint {} \;
) &
HADOLINT_PID=$!

(
    run_linter "checkmake" checkmake Makefile
) &
CHECKMAKE_PID=$!

(
    run_linter "markdownlint" markdownlint README.md AGENTS.md 'docs/**/*.md'
) &
MARKDOWNLINT_PID=$!

# Wait for all linters to complete and collect their exit codes
wait $BLACK_PID
BLACK_EXIT=$?

wait $ISORT_PID
ISORT_EXIT=$?

wait $RUFF_PID
RUFF_EXIT=$?

wait $MYPY_PID
MYPY_EXIT=$?

wait $YAMLLINT_PID
YAMLLINT_EXIT=$?

wait $HADOLINT_PID
HADOLINT_EXIT=$?

wait $CHECKMAKE_PID
CHECKMAKE_EXIT=$?

wait $MARKDOWNLINT_PID
MARKDOWNLINT_EXIT=$?

# Calculate overall exit code
OVERALL_EXIT=0
if [ $BLACK_EXIT -ne 0 ] || [ $ISORT_EXIT -ne 0 ] || [ $RUFF_EXIT -ne 0 ] || [ $MYPY_EXIT -ne 0 ] || [ $YAMLLINT_EXIT -ne 0 ] || [ $HADOLINT_EXIT -ne 0 ] || [ $CHECKMAKE_EXIT -ne 0 ] || [ $MARKDOWNLINT_EXIT -ne 0 ]; then
    OVERALL_EXIT=1
fi

echo ""
print_status "$CYAN" "=== LINTING SUMMARY ==="

# Show individual results
if [ $BLACK_EXIT -eq 0 ]; then
    print_status "$GREEN" "✓ black: passed"
else
    print_status "$RED" "✗ black: failed"
fi

if [ $ISORT_EXIT -eq 0 ]; then
    print_status "$GREEN" "✓ isort: passed"
else
    print_status "$RED" "✗ isort: failed"
fi

if [ $RUFF_EXIT -eq 0 ]; then
    print_status "$GREEN" "✓ ruff: passed"
else
    print_status "$RED" "✗ ruff: failed"
fi

if [ $MYPY_EXIT -eq 0 ]; then
    print_status "$GREEN" "✓ mypy: passed"
else
    print_status "$RED" "✗ mypy: failed"
fi

if [ $YAMLLINT_EXIT -eq 0 ]; then
    print_status "$GREEN" "✓ yamllint: passed"
else
    print_status "$RED" "✗ yamllint: failed"
fi

if [ $HADOLINT_EXIT -eq 0 ]; then
    print_status "$GREEN" "✓ hadolint: passed"
else
    print_status "$RED" "✗ hadolint: failed"
fi

if [ $CHECKMAKE_EXIT -eq 0 ]; then
    print_status "$GREEN" "✓ checkmake: passed"
else
    print_status "$RED" "✗ checkmake: failed"
fi

if [ $MARKDOWNLINT_EXIT -eq 0 ]; then
    print_status "$GREEN" "✓ markdownlint: passed"
else
    print_status "$RED" "✗ markdownlint: failed"
fi

# Show aggregated output if there were failures
if [ $OVERALL_EXIT -ne 0 ]; then
    echo ""
    print_status "$RED" "=== DETAILED FAILURE OUTPUT ==="
    if [ -f /tmp/lint_aggregated_output.log ]; then
        cat /tmp/lint_aggregated_output.log
    fi
    echo ""
    print_status "$RED" "=== END OF FAILURE OUTPUT ==="
fi

# Clean up temporary files
rm -f /tmp/lint_*.log /tmp/lint_failures.txt /tmp/lint_aggregated_output.log

if [ $OVERALL_EXIT -eq 0 ]; then
    print_status "$GREEN" "🎉 All linting checks passed!"
else
    print_status "$RED" "❌ Some linting checks failed. See details above."
fi

exit $OVERALL_EXIT