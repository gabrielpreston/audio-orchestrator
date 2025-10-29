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
        "response_body": None,
        "diagnostics": {}
    }

    try:
        # Add request timing
        import time
        start_time = time.time()

        response = httpx.get(url, timeout=timeout)
        response_time = time.time() - start_time

        error_details["response_status"] = response.status_code
        error_details["diagnostics"]["response_time_ms"] = round(response_time * 1000, 2)

        if response.status_code == 200:
            try:
                response_data = response.json()
                error_details["response_body"] = response_data

                # Extract service-specific health information
                if isinstance(response_data, dict):
                    error_details["diagnostics"]["service_status"] = response_data.get("status", "unknown")
                    error_details["diagnostics"]["service_name"] = response_data.get("service", "unknown")
                    error_details["diagnostics"]["startup_complete"] = response_data.get("startup_complete", None)

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
        error_details["diagnostics"]["timeout_seconds"] = timeout
        return 1, error_details
    except httpx.ConnectError as e:
        error_details["error_type"] = "connection_error"
        error_details["error_message"] = "Connection refused"
        error_details["diagnostics"]["connection_error"] = str(e)
        return 1, error_details
    except httpx.HTTPError as e:
        error_details["error_type"] = "http_error"
        error_details["error_message"] = f"HTTP error: {str(e)}"
        error_details["diagnostics"]["http_error"] = str(e)
        return 1, error_details
    except Exception as e:
        error_details["error_type"] = "unknown_error"
        error_details["error_message"] = str(e)
        error_details["diagnostics"]["exception_type"] = type(e).__name__
        return 1, error_details

def main() -> None:
    parser = argparse.ArgumentParser(description="Enhanced health check for Docker services")
    parser.add_argument("url", help="Health check endpoint URL")
    parser.add_argument("--timeout", type=int, default=5, help="Request timeout in seconds")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--json", action="store_true", help="Output error details as JSON")
    parser.add_argument("--ci", action="store_true", help="CI-optimized output format")

    args = parser.parse_args()

    exit_code, error_details = check_health_detailed(args.url, args.timeout)

    if args.json:
        print(json.dumps(error_details, indent=2))
    elif args.ci:
        # CI-optimized output format
        if exit_code == 0:
            print(f"✅ Health check PASSED for {args.url}")
            if error_details["diagnostics"].get("response_time_ms"):
                print(f"   Response time: {error_details['diagnostics']['response_time_ms']}ms")
            if error_details["diagnostics"].get("service_status"):
                print(f"   Service status: {error_details['diagnostics']['service_status']}")
        else:
            print(f"❌ Health check FAILED for {args.url}")
            print(f"   Error: {error_details['error_type']} - {error_details['error_message']}")
            if error_details["diagnostics"]:
                print(f"   Diagnostics: {json.dumps(error_details['diagnostics'], indent=2)}")
    elif args.verbose:
        print(f"Health check for {args.url}: {'PASS' if exit_code == 0 else 'FAIL'}")
        if error_details["error_type"]:
            print(f"Error: {error_details['error_type']} - {error_details['error_message']}")
        if error_details["response_body"]:
            print(f"Response: {error_details['response_body']}")
        if error_details["diagnostics"]:
            print(f"Diagnostics: {json.dumps(error_details['diagnostics'], indent=2)}")
    else:
        # Default output - just pass/fail
        if exit_code == 0:
            print(f"✅ Health check PASSED for {args.url}")
        else:
            print(f"❌ Health check FAILED for {args.url}: {error_details['error_message']}")

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
