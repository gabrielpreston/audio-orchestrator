#!/usr/bin/env python3
"""Service naming migration script for Pattern A implementation.

This script migrates from hyphen/underscore naming to single-name model:
- orchestrator_enhanced/orchestrator-enhanced -> orchestrator
- llm_flan/llm-flan -> flan
- tts_bark/tts-bark -> bark
- audio_processor/audio-processor -> audio
- monitoring_dashboard/monitoring-dashboard -> monitoring
- testing_ui/testing-ui -> testing
"""

import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

# Service mapping: (old_directory, old_docker, new_name)
SERVICE_MAPPING = [
    ("orchestrator", "orchestrator", "orchestrator"),
    ("flan", "flan", "flan"),
    ("bark", "bark", "bark"),
    ("audio", "audio", "audio"),
    ("monitoring", "monitoring", "monitoring"),
    ("testing", "testing", "testing"),
]

def create_service_mapping_dict() -> Dict[str, str]:
    """Create a comprehensive mapping dictionary."""
    mapping = {}
    for old_dir, old_docker, new_name in SERVICE_MAPPING:
        mapping[old_dir] = new_name
        mapping[old_docker] = new_name
        # Also map common variations
        mapping[old_dir.replace("_", "-")] = new_name
        mapping[old_docker.replace("-", "_")] = new_name
    return mapping

def migrate_file_content(content: str, mapping: Dict[str, str]) -> str:
    """Migrate service references in file content."""
    original_content = content

    for old_name, new_name in mapping.items():
        # Replace in URLs (http://service-name:port)
        content = re.sub(
            rf"http://{re.escape(old_name)}:(\d+)",
            rf"http://{new_name}:\1",
            content
        )

        # Replace in environment variables (SERVICE_NAME_URL)
        env_var_old = old_name.upper().replace("-", "_")
        env_var_new = new_name.upper()
        content = re.sub(
            rf"({env_var_old}_URL)",
            rf"{env_var_new}_URL",
            content
        )

        # Replace in service names in JSON/YAML
        content = re.sub(
            rf'"(service|name)":\s*"{re.escape(old_name)}"',
            rf'"\1": "{new_name}"',
            content
        )

        # Replace in Python strings
        content = re.sub(
            rf'"{re.escape(old_name)}"',
            f'"{new_name}"',
            content
        )

        # Replace in comments
        content = re.sub(
            rf"# {re.escape(old_name)}",
            f"# {new_name}",
            content
        )

        # Replace in markdown links and references
        content = re.sub(
            rf"`{re.escape(old_name)}`",
            f"`{new_name}`",
            content
        )

    return content

def migrate_file(file_path: Path, mapping: Dict[str, str]) -> bool:
    """Migrate a single file."""
    try:
        if not file_path.is_file():
            return False

        # Skip binary files and certain patterns
        if file_path.suffix in ['.pyc', '.so', '.dll', '.exe']:
            return False

        if file_path.name.startswith('.'):
            return False

        content = file_path.read_text(encoding='utf-8', errors='ignore')
        migrated_content = migrate_file_content(content, mapping)

        if migrated_content != content:
            file_path.write_text(migrated_content, encoding='utf-8')
            return True
        return False
    except Exception as e:
        print(f"Error migrating {file_path}: {e}")
        return False

def rename_directories(project_root: Path, mapping: Dict[str, str]) -> List[Tuple[str, str]]:
    """Rename service directories."""
    renamed = []
    services_dir = project_root / "services"

    if not services_dir.exists():
        print("Services directory not found!")
        return renamed

    for old_dir, new_name in mapping.items():
        old_path = services_dir / old_dir
        new_path = services_dir / new_name

        if old_path.exists() and not new_path.exists():
            print(f"Renaming {old_path} -> {new_path}")
            shutil.move(str(old_path), str(new_path))
            renamed.append((old_dir, new_name))
        elif old_path.exists() and new_path.exists():
            print(f"Warning: Both {old_path} and {new_path} exist. Skipping rename.")
        else:
            print(f"Directory {old_path} not found. Skipping.")

    return renamed

def migrate_files(project_root: Path, mapping: Dict[str, str]) -> int:
    """Migrate all files in the project."""
    migrated_count = 0

    # File patterns to migrate
    patterns = [
        "**/*.py",
        "**/*.yml",
        "**/*.yaml",
        "**/*.md",
        "**/*.json",
        "**/*.sh",
        "**/Makefile",
        "**/Dockerfile",
        "**/*.txt",
        "**/*.toml"
    ]

    for pattern in patterns:
        for file_path in project_root.glob(pattern):
            if file_path.is_file() and not file_path.name.startswith('.'):
                if migrate_file(file_path, mapping):
                    print(f"Migrated: {file_path}")
                    migrated_count += 1

    return migrated_count

def main():
    """Run the migration."""
    project_root = Path(".")
    mapping = create_service_mapping_dict()

    print("Starting service name migration...")
    print(f"Mapping: {mapping}")

    # Step 1: Rename directories
    print("\n1. Renaming service directories...")
    renamed_dirs = rename_directories(project_root, mapping)
    print(f"Renamed {len(renamed_dirs)} directories")

    # Step 2: Migrate file contents
    print("\n2. Migrating file contents...")
    migrated_files = migrate_files(project_root, mapping)
    print(f"Migrated {migrated_files} files")

    print("\nMigration complete!")
    print(f"Renamed directories: {renamed_dirs}")
    print(f"Migrated files: {migrated_files}")

if __name__ == "__main__":
    main()
