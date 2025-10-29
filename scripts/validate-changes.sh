#!/usr/bin/env bash
set -euo pipefail

# Colors (aligned with Makefile)
COLOR_OFF=${COLOR_OFF:-'\033[0m'}
COLOR_RED=${COLOR_RED:-'\033[31m'}
COLOR_GREEN=${COLOR_GREEN:-'\033[32m'}
COLOR_YELLOW=${COLOR_YELLOW:-'\033[33m'}
COLOR_BLUE=${COLOR_BLUE:-'\033[34m'}
COLOR_MAGENTA=${COLOR_MAGENTA:-'\033[35m'}
COLOR_CYAN=${COLOR_CYAN:-'\033[36m'}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VERBOSE=0

usage() {
  echo "Usage: $0 [--verbose]"
  echo "  --verbose      Echo commands as they run"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --verbose) VERBOSE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 2 ;;
  esac
done

if [[ "$VERBOSE" -eq 1 ]]; then
  set -x
fi

cd "$REPO_ROOT"

start_timer() { date +%s; }
elapsed() { local end; end=$(date +%s); echo $(( end - $1 )); }

banner() {
  printf "${COLOR_CYAN}%s${COLOR_OFF}\n" "=== $* ==="
}

section() {
  printf "${COLOR_BLUE}%s${COLOR_OFF}\n" "-- $*"
}

ok() {
  printf "${COLOR_GREEN}%s${COLOR_OFF}\n" "✓ $*"
}

warn() {
  printf "${COLOR_YELLOW}%s${COLOR_OFF}\n" "⚠ $*"
}

fail() {
  printf "${COLOR_RED}%s${COLOR_OFF}\n" "✗ $*"
}

SUMMARY_LINES=()

append_summary() {
  SUMMARY_LINES+=("$1")
}

print_summary() {
  echo
  banner "Validation Summary"
  for line in "${SUMMARY_LINES[@]}"; do
    echo "  - $line"
  done
}

OVERALL_RC=0
TOTAL_START=$(start_timer)

# 1) Git status + change summary
banner "Git Status"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  section "Porcelain"
  git status --porcelain=v1 || true
  section "Against HEAD"
  CHANGED_FILES=$(git diff --name-only HEAD || true)
  if [[ -z "$CHANGED_FILES" ]]; then
    echo "(no tracked diffs vs HEAD)"
  else
    echo "$CHANGED_FILES"
  fi
else
  warn "Not a git repository; skipping diff summary"
fi

# 2) Detect impacted services
banner "Changed Services"
if [[ -x "$SCRIPT_DIR/detect-changed-services.sh" ]]; then
  CHANGED_SERVICES=$("$SCRIPT_DIR/detect-changed-services.sh" "HEAD")
  echo "$CHANGED_SERVICES"
  append_summary "Changed services: ${CHANGED_SERVICES}"
else
  warn "scripts/detect-changed-services.sh not executable or missing"
  append_summary "Changed services: (unknown)"
fi

# 3) Lint-Fix
banner "Lint-Fix"
LINT_START=$(start_timer)
if make lint-fix; then
  append_summary "Lint-Fix: PASS ($(elapsed "$LINT_START")s)"
  ok "Lint-Fix passed"
else
  OVERALL_RC=1
  append_summary "Lint-Fix: FAIL ($(elapsed "$LINT_START")s)"
  fail "Lint-Fix failed"
fi

# 4) Lint
banner "Lint"
LINT_START=$(start_timer)
if make lint; then
  append_summary "Lint: PASS ($(elapsed "$LINT_START")s)"
  ok "Lint passed"
else
  OVERALL_RC=1
  append_summary "Lint: FAIL ($(elapsed "$LINT_START")s)"
  fail "Lint failed"
fi

# 5) Full Tests
banner "Full Tests"
FULL_START=$(start_timer)
if make test; then
  append_summary "Full tests: PASS ($(elapsed "$FULL_START")s)"
  ok "Full tests passed"
else
  OVERALL_RC=1
  append_summary "Full tests: FAIL ($(elapsed "$FULL_START")s)"
  fail "Full tests failed"
fi

DUR=$(elapsed "$TOTAL_START")
append_summary "Total time: ${DUR}s"

print_summary

exit "$OVERALL_RC"
