"""CI Failure Analyzer

Analyzes CI failures and determines if Cursor can automatically fix them.
"""

import re
import json
import subprocess
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class FixableType(Enum):
    """Types of issues that can be automatically fixed."""
    LINTING = "linting"
    FORMATTING = "formatting"
    IMPORT_SORTING = "import_sorting"
    TYPE_HINTS = "type_hints"
    SYNTAX_ERROR = "syntax_error"
    DOCKERFILE = "dockerfile"
    YAML_FORMAT = "yaml_format"
    MARKDOWN = "markdown"


@dataclass
class FixableIssue:
    """Represents a fixable issue found in CI logs."""
    issue_type: FixableType
    file_path: str
    line_number: Optional[int]
    description: str
    confidence: float  # 0.0 to 1.0
    fix_command: Optional[str] = None


class CIFailureAnalyzer:
    """Analyzes CI failures and determines fixability."""
    
    def __init__(self):
        self.fixable_patterns = {
            FixableType.LINTING: [
                r"black.*would reformat",
                r"isort.*would change",
                r"ruff.*error",
                r"mypy.*error",
                r"flake8.*error",
            ],
            FixableType.FORMATTING: [
                r"black.*would reformat",
                r"indentation.*error",
                r"trailing.*whitespace",
            ],
            FixableType.IMPORT_SORTING: [
                r"isort.*would change",
                r"import.*not.*sorted",
                r"unused.*import",
            ],
            FixableType.TYPE_HINTS: [
                r"mypy.*error",
                r"type.*annotation",
                r"missing.*type.*hint",
            ],
            FixableType.SYNTAX_ERROR: [
                r"syntax.*error",
                r"invalid.*syntax",
                r"indentation.*error",
            ],
            FixableType.DOCKERFILE: [
                r"hadolint.*error",
                r"dockerfile.*error",
                r"docker.*build.*error",
            ],
            FixableType.YAML_FORMAT: [
                r"yamllint.*error",
                r"yaml.*syntax.*error",
                r"invalid.*yaml",
            ],
            FixableType.MARKDOWN: [
                r"markdownlint.*error",
                r"markdown.*format.*error",
            ],
        }
        
        self.fix_commands = {
            FixableType.LINTING: "black {file} && isort {file} && ruff check --fix {file}",
            FixableType.FORMATTING: "black {file}",
            FixableType.IMPORT_SORTING: "isort {file}",
            FixableType.TYPE_HINTS: "mypy {file}",
            FixableType.SYNTAX_ERROR: "python -m py_compile {file}",
            FixableType.DOCKERFILE: "hadolint {file}",
            FixableType.YAML_FORMAT: "yamllint {file}",
            FixableType.MARKDOWN: "markdownlint --fix {file}",
        }
    
    def analyze_logs(self, job_name: str, logs: str) -> List[FixableIssue]:
        """Analyze CI job logs and identify fixable issues."""
        issues = []
        
        for issue_type, patterns in self.fixable_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, logs, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    issue = self._create_issue_from_match(
                        issue_type, match, logs, job_name
                    )
                    if issue:
                        issues.append(issue)
        
        return issues
    
    def _create_issue_from_match(
        self, 
        issue_type: FixableType, 
        match: re.Match, 
        logs: str, 
        job_name: str
    ) -> Optional[FixableIssue]:
        """Create a FixableIssue from a regex match."""
        try:
            # Extract file path and line number from context
            file_path = self._extract_file_path(match, logs)
            line_number = self._extract_line_number(match, logs)
            description = match.group(0).strip()
            
            # Calculate confidence based on pattern match quality
            confidence = self._calculate_confidence(issue_type, match, logs)
            
            # Get fix command if available
            fix_command = None
            if file_path and issue_type in self.fix_commands:
                fix_command = self.fix_commands[issue_type].format(file=file_path)
            
            return FixableIssue(
                issue_type=issue_type,
                file_path=file_path or "unknown",
                line_number=line_number,
                description=description,
                confidence=confidence,
                fix_command=fix_command
            )
        except Exception as e:
            print(f"Error creating issue from match: {e}")
            return None
    
    def _extract_file_path(self, match: re.Match, logs: str) -> Optional[str]:
        """Extract file path from log context around the match."""
        # Look for file paths in the surrounding context
        context_start = max(0, match.start() - 200)
        context_end = min(len(logs), match.end() + 200)
        context = logs[context_start:context_end]
        
        # Common file path patterns
        file_patterns = [
            r'([a-zA-Z0-9_/.-]+\.py)',
            r'([a-zA-Z0-9_/.-]+\.yml)',
            r'([a-zA-Z0-9_/.-]+\.yaml)',
            r'([a-zA-Z0-9_/.-]+Dockerfile)',
            r'([a-zA-Z0-9_/.-]+\.md)',
        ]
        
        for pattern in file_patterns:
            file_matches = re.findall(pattern, context)
            if file_matches:
                return file_matches[0]
        
        return None
    
    def _extract_line_number(self, match: re.Match, logs: str) -> Optional[int]:
        """Extract line number from log context around the match."""
        context_start = max(0, match.start() - 100)
        context_end = min(len(logs), match.end() + 100)
        context = logs[context_start:context_end]
        
        # Look for line number patterns
        line_patterns = [
            r'line (\d+)',
            r':(\d+):',
            r'\(line (\d+)\)',
        ]
        
        for pattern in line_patterns:
            line_matches = re.findall(pattern, context)
            if line_matches:
                try:
                    return int(line_matches[0])
                except ValueError:
                    continue
        
        return None
    
    def _calculate_confidence(
        self, 
        issue_type: FixableType, 
        match: re.Match, 
        logs: str
    ) -> float:
        """Calculate confidence score for a fixable issue."""
        base_confidence = 0.7
        
        # Increase confidence for specific patterns
        if "would reformat" in match.group(0).lower():
            base_confidence += 0.2
        if "would change" in match.group(0).lower():
            base_confidence += 0.2
        if "error" in match.group(0).lower():
            base_confidence += 0.1
        
        # Decrease confidence for ambiguous patterns
        if "warning" in match.group(0).lower():
            base_confidence -= 0.2
        if "note" in match.group(0).lower():
            base_confidence -= 0.3
        
        return min(1.0, max(0.0, base_confidence))
    
    def should_apply_fixes(self, issues: List[FixableIssue]) -> bool:
        """Determine if automated fixes should be applied."""
        if not issues:
            return False
        
        # Only apply fixes if we have high-confidence issues
        high_confidence_issues = [
            issue for issue in issues 
            if issue.confidence >= 0.8
        ]
        
        if not high_confidence_issues:
            return False
        
        # Check for critical issues that should not be auto-fixed
        critical_patterns = [
            "security",
            "vulnerability",
            "critical",
            "breaking",
            "api",
        ]
        
        for issue in high_confidence_issues:
            if any(pattern in issue.description.lower() 
                   for pattern in critical_patterns):
                return False
        
        return True
    
    def get_fix_strategy(self, issues: List[FixableIssue]) -> Dict[str, Any]:
        """Get the recommended fix strategy for the issues."""
        if not issues:
            return {"strategy": "none", "commands": []}
        
        # Group issues by type
        issues_by_type = {}
        for issue in issues:
            if issue.issue_type not in issues_by_type:
                issues_by_type[issue.issue_type] = []
            issues_by_type[issue.issue_type].append(issue)
        
        # Generate fix commands
        commands = []
        for issue_type, type_issues in issues_by_type.items():
            if issue_type in self.fix_commands:
                # Get unique file paths
                file_paths = list(set(issue.file_path for issue in type_issues 
                                    if issue.file_path != "unknown"))
                
                if file_paths:
                    if issue_type in [FixableType.LINTING, FixableType.FORMATTING]:
                        # Use directory-level commands for formatting
                        commands.append(f"black {' '.join(file_paths)}")
                        commands.append(f"isort {' '.join(file_paths)}")
                        commands.append(f"ruff check --fix {' '.join(file_paths)}")
                    else:
                        # Use file-level commands
                        for file_path in file_paths:
                            commands.append(
                                self.fix_commands[issue_type].format(file=file_path)
                            )
        
        return {
            "strategy": "automated",
            "commands": commands,
            "issue_count": len(issues),
            "issue_types": list(issues_by_type.keys()),
        }


def analyze_ci_failure(job_name: str, logs: str) -> Dict[str, Any]:
    """Convenience function to analyze a CI failure."""
    analyzer = CIFailureAnalyzer()
    issues = analyzer.analyze_logs(job_name, logs)
    should_fix = analyzer.should_apply_fixes(issues)
    strategy = analyzer.get_fix_strategy(issues)
    
    return {
        "job_name": job_name,
        "issues": [
            {
                "type": issue.issue_type.value,
                "file_path": issue.file_path,
                "line_number": issue.line_number,
                "description": issue.description,
                "confidence": issue.confidence,
                "fix_command": issue.fix_command,
            }
            for issue in issues
        ],
        "should_fix": should_fix,
        "fix_strategy": strategy,
    }