"""Simple Cursor CI Fixer

A minimal wrapper around Cursor CLI for CI integration.
No complex analysis - just direct CLI calls.
"""

import subprocess
import sys
from typing import List, Optional


def run_cursor_fix(target: str = "all", dry_run: bool = False) -> bool:
    """Run Cursor fix-ci command.
    
    Args:
        target: Target to fix (lint, test, docker, all)
        dry_run: If True, only show what would be fixed
        
    Returns:
        True if fixes were applied successfully, False otherwise
    """
    cmd = ["cursor", "fix-ci", "--target", target]
    
    if dry_run:
        cmd.append("--dry-run")
    else:
        cmd.append("--auto-commit")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"Cursor fix output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Cursor fix failed: {e.stderr}")
        return False
    except FileNotFoundError:
        print("Cursor CLI not found. Install it first.")
        return False


def check_cursor_available() -> bool:
    """Check if Cursor CLI is available."""
    try:
        subprocess.run(["cursor", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def main():
    """Simple CLI interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple Cursor CI Fixer")
    parser.add_argument("--target", default="all", 
                       choices=["lint", "test", "docker", "all"],
                       help="Target to fix")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be fixed without applying")
    
    args = parser.parse_args()
    
    if not check_cursor_available():
        print("Error: Cursor CLI not found")
        sys.exit(1)
    
    success = run_cursor_fix(args.target, args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()