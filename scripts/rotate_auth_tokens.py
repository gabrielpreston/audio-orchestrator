#!/usr/bin/env python3
"""Rotate AUTH_TOKEN values across all environment files.

This script generates new secure tokens and updates all relevant environment files
to maintain consistency across the discord-voice-lab services.
"""
from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Token configuration
TOKEN_LENGTH = 32
TOKEN_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"

# Environment file paths (excluding .env.sample as it's a template)
ENV_FILES = {
    ".env.common": "Shared configuration for all services",
    ".env.docker": "Docker-specific configuration",
    "services/discord/.env.service": "Discord service configuration",
    "services/stt/.env.service": "STT service configuration",
    "services/llm/.env.service": "LLM service configuration",
    "services/orchestrator/.env.service": "Orchestrator service configuration",
    "services/tts/.env.service": "TTS service configuration",
}

# AUTH_TOKEN variables to rotate
AUTH_TOKENS = {
    "ORCH_AUTH_TOKEN": "Bearer token for orchestrator APIs",
    "LLM_AUTH_TOKEN": "Bearer token for LLM service APIs",
    "TTS_AUTH_TOKEN": "Bearer token required for synthesis calls",
}


def generate_secure_token() -> str:
    """Generate a cryptographically secure random token."""
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(TOKEN_LENGTH))


def read_env_file(file_path: Path) -> List[str]:
    """Read an environment file and return its lines."""
    if not file_path.exists():
        return []

    try:
        return file_path.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return []


def write_env_file(file_path: Path, lines: List[str]) -> None:
    """Write lines to an environment file."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(lines).rstrip() + "\n" if lines else ""
        file_path.write_text(content, encoding="utf-8")
    except Exception as e:
        print(f"Error writing {file_path}: {e}", file=sys.stderr)
        raise


def update_token_in_lines(lines: List[str], token_name: str, new_value: str) -> List[str]:
    """Update a token value in environment file lines."""
    updated_lines = []
    token_found = False

    for line in lines:
        if line.strip().startswith(f"{token_name}="):
            updated_lines.append(f"{token_name}={new_value}")
            token_found = True
        else:
            updated_lines.append(line)

    # If token not found, add it at the end
    if not token_found:
        updated_lines.append(f"{token_name}={new_value}")

    return updated_lines


def rotate_tokens_in_file(
    file_path: Path, new_tokens: Dict[str, str], dry_run: bool = False
) -> bool:
    """Rotate tokens in a specific environment file."""
    if not file_path.exists():
        print(f"  ⚠️  File {file_path} does not exist, skipping")
        return True

    lines = read_env_file(file_path)
    if not lines:
        print(f"  ⚠️  File {file_path} is empty, skipping")
        return True

    updated_lines = lines
    changes_made = False

    for token_name, new_value in new_tokens.items():
        original_lines = updated_lines
        updated_lines = update_token_in_lines(updated_lines, token_name, new_value)
        if updated_lines != original_lines:
            changes_made = True

    if changes_made:
        if dry_run:
            print(f"  📝 Would update {file_path}")
            # Show the changes that would be made
            for i, (old_line, new_line) in enumerate(zip(lines, updated_lines)):
                if old_line != new_line:
                    print(f"    Line {i+1}: {old_line}")
                    print(f"    Line {i+1}: {new_line}")
        else:
            write_env_file(file_path, updated_lines)
            print(f"  ✅ Updated {file_path}")
    else:
        print(f"  ℹ️  No changes needed for {file_path}")

    return True


def validate_token_consistency() -> bool:
    """Validate that all AUTH_TOKENs are consistent across environment files."""
    print("🔍 Validating token consistency...")

    token_values = {}
    all_consistent = True

    for file_path_str, description in ENV_FILES.items():
        file_path = Path(file_path_str)
        if not file_path.exists():
            continue

        lines = read_env_file(file_path)
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            for token_name in AUTH_TOKENS:
                if line.startswith(f"{token_name}="):
                    value = line.split("=", 1)[1]
                    if token_name in token_values:
                        if token_values[token_name] != value:
                            print(f"  ❌ Inconsistent {token_name} in {file_path}")
                            print(f"    Expected: {token_values[token_name]}")
                            print(f"    Found:    {value}")
                            all_consistent = False
                    else:
                        token_values[token_name] = value

    if all_consistent:
        print("  ✅ All tokens are consistent across environment files")
    else:
        print("  ❌ Token inconsistencies found")

    return all_consistent


def main() -> int:
    """Main entry point for the token rotation script."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making actual modifications",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate token consistency without rotating",
    )
    parser.add_argument(
        "--tokens",
        nargs="+",
        choices=list(AUTH_TOKENS.keys()),
        default=list(AUTH_TOKENS.keys()),
        help="Specific tokens to rotate (default: all)",
    )
    parser.add_argument(
        "--length",
        type=int,
        default=TOKEN_LENGTH,
        help=f"Length of generated tokens (default: {TOKEN_LENGTH})",
    )

    args = parser.parse_args()

    if args.validate_only:
        return 0 if validate_token_consistency() else 1

    print("🔄 AUTH_TOKEN Rotation Script")
    print("=" * 50)

    # Generate new tokens
    new_tokens = {}
    for token_name in args.tokens:
        new_tokens[token_name] = generate_secure_token()
        print(f"Generated new {token_name}: {new_tokens[token_name]}")

    print()

    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be modified")
        print()

    # Rotate tokens in each environment file
    success = True
    for file_path_str, description in ENV_FILES.items():
        file_path = Path(file_path_str)
        print(f"Processing {file_path_str} ({description})")

        try:
            if not rotate_tokens_in_file(file_path, new_tokens, args.dry_run):
                success = False
        except Exception as e:
            print(f"  ❌ Error processing {file_path}: {e}")
            success = False

        print()

    if not args.dry_run and success:
        print("🔍 Validating token consistency after rotation...")
        if not validate_token_consistency():
            print("❌ Token rotation completed but validation failed")
            return 1
        print("✅ Token rotation completed successfully")
    elif args.dry_run:
        print("✅ Dry run completed - no changes made")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
