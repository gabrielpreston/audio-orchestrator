#!/usr/bin/env python3
"""
Enhanced health check script with detailed error reporting.
"""

import sys
import argparse
import httpx
import json
from typing import Dict, Any

def check_health_detailed(url: str, timeout: int = 5) -> tuple[int, Dict[str, Any]]:
    """
    Perform detailed health check with comprehensive error reporting.

    Returns:
        Tuple of (exit_code, error_details)
    """
    error_details = {
        "url": url,
        "timeout": timeout,
        "error_type": None,
        "error_message": None,
        "response_status": None,
        "response_body": None
    }

    try:
        response = httpx.get(url, timeout=timeout)
        error_details["response_status"] = response.status_code

        if response.status_code == 200:
            try:
                error_details["response_body"] = response.json()
            except:
                error_details["response_body"] = response.text
            return 0, error_details
        else:
            error_details["error_type"] = "http_error"
            error_details["error_message"] = f"HTTP {response.status_code}"
            try:
                error_details["response_body"] = response.json()
            except:
                error_details["response_body"] = response.text
            return 1, error_details

    except httpx.TimeoutException as e:
        error_details["error_type"] = "timeout"
        error_details["error_message"] = f"Timeout after {timeout}s"
        return 1, error_details
    except httpx.ConnectError as e:
        error_details["error_type"] = "connection_error"
        error_details["error_message"] = "Connection refused"
        return 1, error_details
    except Exception as e:
        error_details["error_type"] = "unknown_error"
        error_details["error_message"] = str(e)
        return 1, error_details

def main() -> None:
    parser = argparse.ArgumentParser(description="Enhanced health check for Docker services")
    parser.add_argument("url", help="Health check endpoint URL")
    parser.add_argument("--timeout", type=int, default=5, help="Request timeout in seconds")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--json", action="store_true", help="Output error details as JSON")

    args = parser.parse_args()

    exit_code, error_details = check_health_detailed(args.url, args.timeout)

    if args.verbose or args.json:
        if args.json:
            print(json.dumps(error_details, indent=2))
        else:
            print(f"Health check for {args.url}: {'PASS' if exit_code == 0 else 'FAIL'}")
            if error_details["error_type"]:
                print(f"Error: {error_details['error_type']} - {error_details['error_message']}")
            if error_details["response_body"]:
                print(f"Response: {error_details['response_body']}")

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
