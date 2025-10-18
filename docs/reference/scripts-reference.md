---
title: Scripts Reference
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-16
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Reference ▸ Scripts Reference

# Scripts Reference

This document provides comprehensive reference information for the utility scripts included in the discord-voice-lab project.

## Environment Management

### `scripts/prepare_env_files.py`

Splits the canonical `.env.sample` file into the environment files expected by docker-compose.

**Usage:**

```bash
# Generate all environment files from .env.sample
python3 scripts/prepare_env_files.py

# Force regeneration of existing files
python3 scripts/prepare_env_files.py --force
```

**What it does:**

- Reads `.env.sample` and parses section headers (e.g., `# ./services/discord/.env.service #`)
- Creates the corresponding environment files in the correct locations
- Preserves comments and maintains the canonical source of truth
- Supports dry-run mode for validation

**Generated files:**

- `.env.common` — Shared logging defaults
- `.env.docker` — Container-specific overrides
- `services/discord/.env.service` — Discord bot configuration
- `services/stt/.env.service` — STT service configuration
- `services/llm/.env.service` — LLM service configuration
- `services/orchestrator/.env.service` — Orchestrator service configuration
- `services/tts/.env.service` — TTS service configuration

## Security Management

### `scripts/rotate_auth_tokens.py`

Automated token rotation for AUTH_TOKEN values across all environment files.

**Usage:**

```bash
# Rotate all AUTH_TOKENs
make rotate-tokens

# Preview changes without modifying files
make rotate-tokens-dry-run

# Validate token consistency across all environment files
make validate-tokens

# Rotate only specific tokens
python3 scripts/rotate_auth_tokens.py --tokens ORCH_AUTH_TOKEN

# Use custom token length
python3 scripts/rotate_auth_tokens.py --length 64
```

**Features:**

- Generates cryptographically secure random tokens (32 characters by default)
- Updates all relevant environment files (`.env.sample`, service-specific `.env.service` files)
- Validates token consistency after rotation
- Supports dry-run mode for safe testing
- Can rotate specific tokens or all tokens at once
- Maintains token format consistency across services

**Affected tokens:**

- `LLM_AUTH_TOKEN` — LLM service authentication
- `ORCH_AUTH_TOKEN` — Orchestrator service authentication  
- `TTS_AUTH_TOKEN` — TTS service authentication

## Documentation Management

### `scripts/verify_last_updated.py`

Validates documentation `last-updated` metadata consistency.

**Usage:**

```bash
# Verify all documentation metadata
make docs-verify

# Allow intentional date divergences
make docs-verify ARGS="--allow-divergence"

# Run verification script directly
python3 scripts/verify_last_updated.py
```

**Validation checks:**

- Every Markdown file under `docs/` must have YAML front matter with ISO-8601 `last-updated` field
- Index table dates must align with referenced document front matter
- Version history entries must match page `last-updated` values
- `last-updated` values must be within a day of most recent commit
- Surfaces all working tree modifications for reviewer confirmation

**Error handling:**

- Reports missing front matter
- Identifies date mismatches in tables and version history
- Flags stale documentation (outdated `last-updated` values)
- Provides specific file and line number references for fixes

## Makefile Integration

All scripts are integrated into the Makefile for consistent workflow:

```bash
# Environment setup
make run                    # Uses prepare_env_files.py automatically

# Security maintenance  
make rotate-tokens          # Rotate all tokens
make rotate-tokens-dry-run  # Preview changes
make validate-tokens        # Check consistency


# Documentation validation
make docs-verify            # Verify all documentation metadata
```

## Best Practices

### Environment Management Best Practices

- Always use `prepare_env_files.py` when adding new environment variables
- Update `.env.sample` first, then regenerate service files
- Test environment changes with `make run` before committing

### Security Management Best Practices

- Rotate tokens regularly (quarterly recommended)
- Use `--dry-run` to preview changes before applying
- Validate token consistency after rotation
- Document token rotation in security procedures

### Documentation Management Best Practices

- Run `make docs-verify` before committing documentation changes
- Update `last-updated` dates when making substantive changes
- Use `--allow-divergence` only when intentionally keeping old dates
- Maintain consistent front matter across all documentation files

## Troubleshooting

### Common Issues

**Environment files not generated:**

- Verify `.env.sample` exists and has proper section headers
- Check file permissions in target directories
- Use `--force` to overwrite existing files

**Token rotation failures:**

- Ensure all environment files are writable
- Check for syntax errors in environment files
- Validate token format requirements

**Documentation verification failures:**

- Check YAML front matter syntax
- Verify date format (YYYY-MM-DD)
- Ensure all referenced files exist
- Update stale `last-updated` values

### Getting Help

For script-specific help:

```bash
python3 scripts/script_name.py --help
```

For Makefile integration:

```bash
make help
```

For documentation issues:

```bash
make docs-verify ARGS="--verbose"
```
