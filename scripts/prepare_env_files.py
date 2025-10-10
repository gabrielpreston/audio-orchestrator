#!/usr/bin/env python3
"""Split `.env.sample` into the env files expected by docker-compose."""
from __future__ import annotations

import re
from pathlib import Path

HEADER_PATTERN = re.compile(r"#\s*\./\s*(.*?)\s*#$")
SAMPLE_PATH = Path(".env.sample")


def extract_sections(sample_path: Path) -> dict[str, list[str]]:
    if not sample_path.exists():
        raise FileNotFoundError(f"Missing environment sample: {sample_path}")

    sections: dict[str, list[str]] = {}
    current_key: str | None = None

    for raw_line in sample_path.read_text().splitlines():
        stripped = raw_line.strip()
        header_match = HEADER_PATTERN.match(stripped)
        if header_match:
            current_key = header_match.group(1).strip()
            sections[current_key] = []
            continue

        if stripped.startswith("#") or current_key is None:
            continue

        sections[current_key].append(raw_line)

    return sections


def write_sections(sections: dict[str, list[str]]) -> None:
    for relative_path, lines in sections.items():
        path = Path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(lines).rstrip() + "\n" if lines else ""
        path.write_text(content)


if __name__ == "__main__":
    write_sections(extract_sections(SAMPLE_PATH))
