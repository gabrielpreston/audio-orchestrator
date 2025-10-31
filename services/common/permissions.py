"""Utilities for checking and fixing model directory permissions."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from services.common.structured_logging import get_logger

logger = get_logger(__name__)


def check_directory_permissions(directory: str) -> dict[str, Any]:
    """Check directory permissions and return diagnostic information.

    Args:
        directory: Path to directory to check

    Returns:
        Dictionary with permission diagnostics:
        - exists: bool
        - readable: bool
        - writable: bool
        - user_id: int | None
        - group_id: int | None
        - permissions: str | None (octal)
    """
    diagnostics: dict[str, Any] = {
        "exists": False,
        "readable": False,
        "writable": False,
        "user_id": None,
        "group_id": None,
        "permissions": None,
    }

    if not os.path.exists(directory):
        return diagnostics

    diagnostics["exists"] = True

    try:
        path = Path(directory)
        stat_info = path.stat()
        diagnostics["user_id"] = stat_info.st_uid
        diagnostics["group_id"] = stat_info.st_gid
        diagnostics["permissions"] = oct(stat_info.st_mode)[-3:]

        # Check readability (owner/group/others can read)
        diagnostics["readable"] = os.access(directory, os.R_OK)
        # Check writability (owner/group/others can write)
        diagnostics["writable"] = os.access(directory, os.W_OK)
    except OSError:
        pass  # Diagnostics already indicate failure

    return diagnostics


def ensure_model_directory(directory: str, mode: int = 0o755) -> bool:
    """Ensure model directory exists and is writable.

    Args:
        directory: Path to model directory
        mode: Permissions mode (default 0o755)

    Returns:
        True if directory is writable, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        path = Path(directory)
        path.mkdir(mode=mode, parents=True, exist_ok=True)

        # Check if writable
        if os.access(directory, os.W_OK):
            return True

        # Try to fix permissions (only works if we're owner)
        try:
            path.chmod(mode)
            return os.access(directory, os.W_OK)
        except OSError:
            diagnostics = check_directory_permissions(directory)
            logger.warning(
                "permissions.cannot_fix_directory",
                directory=directory,
                diagnostics=diagnostics,
            )
            return False

    except OSError as e:
        diagnostics = check_directory_permissions(directory)
        logger.error(
            "permissions.cannot_create_directory",
            directory=directory,
            error=str(e),
            diagnostics=diagnostics,
        )
        return False


__all__ = ["check_directory_permissions", "ensure_model_directory"]
