#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 0 ]]; then
  exec "$@"
fi

export PYTHONPATH="/workspace${PYTHONPATH:+:${PYTHONPATH}}"

cmd=(pytest)
if [[ -n "${PYTEST_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  extra_args=(${PYTEST_ARGS})
  cmd+=("${extra_args[@]}")
fi

if ! "${cmd[@]}"; then
  status=$?
  if [[ $status -eq 5 ]]; then
    echo "pytest reported that no tests were collected; treating this as success." >&2
    exit 0
  fi
  exit $status
fi
