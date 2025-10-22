#!/usr/bin/env python3
"""Validate documentation `last-updated` metadata consistency.

This script enforces the guardrails captured in the documentation freshness
playbook:

- Every Markdown file under ``docs/`` must expose a YAML front matter block with
  an ISO-8601 ``last-updated`` field.
- If a page lists entries in a table that advertises a "Last Updated" column,
  those dates must align with the referenced document's front matter.
- When a page carries a "Version History" section, the most recent bullet must
  mirror the page's ``last-updated`` value.
- ``last-updated`` values must stay within a day of the most recent commit that
  touched the page (or within a day of "today" when the file currently has
  unstaged/staged modifications). Divergences require the ``--allow-divergence``
  override flag.
- The script surfaces all working tree modifications to ``last-updated`` fields
  so reviewers can quickly confirm that only intended files changed.
"""

from __future__ import annotations

import argparse
import dataclasses
import re
import subprocess  # nosec B404
import sys
from datetime import date, datetime
from pathlib import Path
from collections.abc import Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "docs"
FRONT_MATTER_BOUNDARY = "---"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
INDEX_ROW_PATTERN = re.compile(
    r"^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*([^|]+?)\|\s*(\d{4}-\d{2}-\d{2})\s*\|$"
)
VERSION_HISTORY_HEADER = re.compile(r"^##\s+Version History\s*$", re.MULTILINE)
VERSION_HISTORY_ENTRY = re.compile(r"^-\s+\*\*(\d{4}-\d{2}-\d{2})\*\*")


@dataclasses.dataclass
class FrontMatter:
    raw: dict[str, str]
    last_updated: date


@dataclasses.dataclass
class ValidationIssue:
    path: Path
    message: str

    def format(self) -> str:
        return f"{self.path}: {self.message}"


def load_front_matter(path: Path) -> FrontMatter:
    text = path.read_text(encoding="utf-8")
    if not text.startswith(f"{FRONT_MATTER_BOUNDARY}\n"):
        raise ValueError("missing YAML front matter")

    end_idx = text.find(f"\n{FRONT_MATTER_BOUNDARY}\n", len(FRONT_MATTER_BOUNDARY) + 1)
    if end_idx == -1:
        raise ValueError("unterminated YAML front matter")

    block = text[len(FRONT_MATTER_BOUNDARY) + 1 : end_idx]
    entries: dict[str, str] = {}
    for line in block.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"invalid front matter line: {line!r}")
        key, value = line.split(":", 1)
        entries[key.strip()] = value.strip()

    last_updated_value: str | None = entries.get("last-updated")
    if last_updated_value is None:
        raise ValueError("missing last-updated field")
    if not DATE_PATTERN.fullmatch(last_updated_value):
        raise ValueError("last-updated must be YYYY-MM-DD")
    try:
        parsed_date = datetime.fromisoformat(last_updated_value).date()
    except ValueError as exc:  # pragma: no cover - defensive fallback
        raise ValueError(f"invalid last-updated date: {last_updated_value!r}") from exc

    return FrontMatter(raw=entries, last_updated=parsed_date)


def parse_version_history_date(_path: Path, content: str) -> date | None:
    header_match = VERSION_HISTORY_HEADER.search(content)
    if not header_match:
        return None

    after_header = content[header_match.end() :]
    for line in after_header.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            break
        entry_match = VERSION_HISTORY_ENTRY.match(stripped)
        if entry_match:
            return datetime.fromisoformat(entry_match.group(1)).date()
    return None


def iter_index_rows(
    source_path: Path, content: str
) -> Iterable[tuple[str, Path, str, date]]:
    base_dir = source_path.parent
    for line in content.splitlines():
        match = INDEX_ROW_PATTERN.match(line.strip())
        if not match:
            continue
        title, target, status, date_str = match.groups()
        target_path = Path(target)
        if not target_path.is_absolute():
            resolved = (base_dir / target_path).resolve()
        else:
            resolved = target_path.resolve()
        if DOCS_ROOT not in resolved.parents and resolved != DOCS_ROOT:
            # Fall back to interpreting the path relative to docs/ when the
            # table row uses a shorthand like "architecture/..." from a nested
            # directory (e.g., docs/proposals/README.md).
            resolved = (DOCS_ROOT / target_path).resolve()
        yield title, resolved, status.strip(), datetime.fromisoformat(date_str).date()


def run_git_command(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603, B607
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        check=False,
        capture_output=True,
    )


def collect_git_status() -> dict[Path, str]:
    result = run_git_command(["status", "--porcelain"])
    status_map: dict[Path, str] = {}
    for line in result.stdout.splitlines():
        if not line:
            continue
        status = line[:2]
        rel_path = line[3:]
        status_map[(REPO_ROOT / rel_path).resolve()] = status
    return status_map


def latest_commit_date(path: Path) -> date | None:
    result = run_git_command(
        ["log", "-1", "--format=%cs", "--", str(path.relative_to(REPO_ROOT))]
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return datetime.fromisoformat(result.stdout.strip()).date()


def list_date_modifications() -> dict[Path, list[str]]:
    result = run_git_command(["diff", "HEAD", "--unified=0", "--", "docs"])
    modifications: dict[Path, list[str]] = {}
    current_file: Path | None = None
    for line in result.stdout.splitlines():
        if line.startswith("diff --git"):
            parts = line.split()
            if len(parts) >= 4:
                # diff --git a/path b/path
                raw_path = parts[3][2:]  # strip leading b/
                current_file = (REPO_ROOT / raw_path).resolve()
            else:
                current_file = None
            continue
        if current_file is None:
            continue
        if line.startswith("@@"):
            continue
        if "last-updated:" in line and line.startswith(("+", "-")):
            modifications.setdefault(current_file, []).append(line)
    return modifications


def validate(
    paths: Iterable[Path],
    allow_divergence: bool,
    status_map: dict[Path, str],
    recency_paths: Iterable[Path],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    recency_set = {path.resolve() for path in recency_paths}
    for path in paths:
        try:
            front_matter = load_front_matter(path)
        except ValueError as exc:
            issues.append(ValidationIssue(path, str(exc)))
            continue

        content = path.read_text(encoding="utf-8")
        version_history_date = parse_version_history_date(path, content)
        if version_history_date and version_history_date != front_matter.last_updated:
            issues.append(
                ValidationIssue(
                    path,
                    (
                        "version history latest entry ("
                        f"{version_history_date}) does not match last-updated"
                        f" ({front_matter.last_updated})"
                    ),
                )
            )

        for title, target_path, _status, table_date in iter_index_rows(path, content):
            try:
                target_front_matter = load_front_matter(target_path)
            except ValueError as exc:
                issues.append(
                    ValidationIssue(
                        path,
                        (
                            f"index row '{title}' references {target_path.relative_to(REPO_ROOT)} "
                            f"without valid front matter: {exc}"
                        ),
                    )
                )
                continue
            if target_front_matter.last_updated != table_date:
                issues.append(
                    ValidationIssue(
                        path,
                        (
                            f"index row '{title}' lists {table_date} but front matter for "
                            f"{target_path.relative_to(REPO_ROOT)} reports "
                            f"{target_front_matter.last_updated}"
                        ),
                    )
                )

        if path.resolve() in recency_set:
            git_status = status_map.get(path.resolve())
            if git_status:
                reference_date = datetime.now().date()
            else:
                reference_date = latest_commit_date(path) or datetime.now().date()
            delta_days = abs((front_matter.last_updated - reference_date).days)
            if delta_days > 1 and not allow_divergence:
                issues.append(
                    ValidationIssue(
                        path,
                        (
                            "last-updated value diverges from reference date by "
                            f"{delta_days} days (reference={reference_date}); use "
                            "--allow-divergence if this is intentional"
                        ),
                    )
                )

    return issues


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-divergence",
        action="store_true",
        help="Permit last-updated dates to diverge from git history / today checks.",
    )
    args = parser.parse_args(argv)

    markdown_files = sorted(
        path for path in DOCS_ROOT.rglob("*.md") if ".templates" not in path.parts
    )
    status_map = collect_git_status()
    modifications = list_date_modifications()
    recency_paths = set(status_map.keys()) | set(modifications.keys())
    issues = validate(
        markdown_files,
        allow_divergence=args.allow_divergence,
        status_map=status_map,
        recency_paths=recency_paths,
    )

    if issues:
        for issue in issues:
            print(issue.format(), file=sys.stderr)

    if modifications:
        print("\nDetected last-updated changes:")
        for path, lines in modifications.items():
            rel = path.relative_to(REPO_ROOT)
            print(f"  {rel}")
            for line in lines:
                print(f"    {line}")
    else:
        print("No last-updated changes relative to HEAD.")

    if issues:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
