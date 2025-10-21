---
name: Bug report
about: File a reproducible defect with supporting CI evidence
labels: bug
---

## Summary

<!-- Describe the observed behavior and the expected outcome. -->

## Reproduction steps

1. <!-- Step-by-step instructions -->
2.
3.

## CI context

- Latest failing Actions run: <!-- paste URL -->
- Relevant artifacts downloaded: <!-- pytest-log, docker-smoke-artifacts, pip-audit-reports, etc. -->

## Local verification

- [ ] `make lint` (unified linting via Docker)
- [ ] `make test-unit` (fast unit tests)
- [ ] `make test-component` (component tests)
- [ ] `make test-integration` (integration tests)
- [ ] `make docker-smoke` (Docker smoke tests)
- Notes:

## Additional details

- Branch / commit:
- Environment tweaks or feature flags:
- Logs, screenshots, or payloads:
