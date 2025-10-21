#!/usr/bin/env python3
"""
Health check script for Docker services.

This script performs HTTP health checks against service endpoints
and returns appropriate exit codes for Docker health checks.

Usage:
    python health_check.py <url> [--timeout <seconds>]

Examples:
    python health_check.py http://localhost:8000/health/ready
    python health_check.py http://localhost:9000/health/ready --timeout 10
"""

import sys
import argparse
import httpx
from typing import Optional


def check_health(url: str, timeout: int = 5) -> int:
    """
    Perform a health check against the specified URL.

    Args:
        url: The health check endpoint URL
        timeout: Request timeout in seconds

    Returns:
        0 if health check passes (HTTP 200), 1 otherwise
    """
    try:
        response = httpx.get(url, timeout=timeout)
        if response.status_code == 200:
            return 0
        else:
            print(f"Health check failed: HTTP {response.status_code}", file=sys.stderr)
            return 1
    except httpx.TimeoutException:
        print(f"Health check timeout after {timeout}s", file=sys.stderr)
        return 1
    except httpx.ConnectError:
        print("Health check failed: Connection refused", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Health check failed: {e}", file=sys.stderr)
        return 1


def main() -> None:
    """Main entry point for the health check script."""
    parser = argparse.ArgumentParser(
        description="Perform HTTP health checks for Docker services",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s http://localhost:8000/health/ready
  %(prog)s http://localhost:9000/health/ready --timeout 10
        """,
    )

    parser.add_argument("url", help="Health check endpoint URL")

    parser.add_argument(
        "--timeout", type=int, default=5, help="Request timeout in seconds (default: 5)"
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    if args.verbose:
        print(f"Checking health at: {args.url}")
        print(f"Timeout: {args.timeout}s")

    exit_code = check_health(args.url, args.timeout)

    if args.verbose:
        status = "PASS" if exit_code == 0 else "FAIL"
        print(f"Health check result: {status}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
