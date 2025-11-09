#!/usr/bin/env python3
"""Analyze audio quality metrics from wake detection logs.

This script parses wake detection logs and generates quality reports
to help diagnose audio quality issues affecting wake word detection.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def parse_log_line(line: str) -> dict[str, Any] | None:
    """Parse a single log line and extract wake detection data.

    Args:
        line: Log line (JSON format expected)

    Returns:
        Dictionary with parsed data or None if not a wake detection log
    """
    try:
        # Skip non-JSON lines
        if not line.strip().startswith("{"):
            return None

        # Try to find JSON part (logs may have timestamps/prefixes)
        json_start = line.find("{")
        if json_start == -1:
            return None

        log_entry = json.loads(line[json_start:])

        # Check if this is a wake detection log
        event = log_entry.get("event", "")
        if "wake_detection" not in event and "wake.detection" not in event:
            return None

        # Extract relevant data
        result = {
            "event": event,
            "timestamp": log_entry.get("timestamp"),
            "user_id": log_entry.get("user_id"),
            "correlation_id": log_entry.get("correlation_id"),
        }

        # Extract quality metrics if present
        # Prefer rms_int16 for threshold comparisons, fall back to rms (normalized)
        if "rms_int16" in log_entry:
            result["rms_int16"] = log_entry["rms_int16"]
            result["rms"] = log_entry.get("rms", 0.0)  # Also capture normalized if present
        elif "rms" in log_entry:
            result["rms"] = log_entry["rms"]
        if "snr_db" in log_entry:
            result["snr_db"] = log_entry["snr_db"]
        if "clarity_score" in log_entry:
            result["clarity_score"] = log_entry["clarity_score"]

        # Extract wake detection results if present
        if "wake_confidence" in log_entry:
            result["wake_confidence"] = log_entry["wake_confidence"]
        if "wake_phrase" in log_entry:
            result["wake_phrase"] = log_entry["wake_phrase"]
        if "max_score" in log_entry:
            result["max_score"] = log_entry["max_score"]
        if "above_threshold" in log_entry:
            result["above_threshold"] = log_entry["above_threshold"]

        return result

    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def analyze_logs(log_file: Path | None) -> dict[str, Any]:
    """Analyze wake detection logs and generate quality report.

    Args:
        log_file: Path to log file, or None for stdin

    Returns:
        Dictionary with analysis results
    """
    quality_stats = defaultdict(list)  # Will contain "rms", "rms_int16", "snr_db", "clarity_score"
    low_quality_detections = []
    successful_detections = []
    failed_detections = []

    # Read from file or stdin
    if log_file and log_file.exists():
        lines = log_file.read_text(encoding="utf-8").splitlines()
    elif log_file:
        print(f"Error: Log file not found: {log_file}", file=sys.stderr)
        return {"error": f"Log file not found: {log_file}"}
    else:
        lines = sys.stdin.readlines()

    total_lines = 0
    parsed_entries = 0

    for line in lines:
        total_lines += 1
        entry = parse_log_line(line)
        if not entry:
            continue

        parsed_entries += 1

        # Collect quality metrics
        # Prefer rms_int16 for threshold comparisons (int16 domain), fall back to rms (normalized)
        if "rms_int16" in entry:
            quality_stats["rms_int16"].append(entry["rms_int16"])
            # Also collect normalized RMS if present
            if "rms" in entry:
                quality_stats["rms"].append(entry["rms"])
        elif "rms" in entry:
            quality_stats["rms"].append(entry["rms"])
        if "snr_db" in entry:
            quality_stats["snr_db"].append(entry["snr_db"])
        if "clarity_score" in entry:
            quality_stats["clarity_score"].append(entry["clarity_score"])

        # Categorize detections
        if entry.get("above_threshold") is True or entry.get("wake_confidence"):
            successful_detections.append(entry)
        elif entry.get("event") == "audio_processor_wrapper.wake_detection_no_result":
            failed_detections.append(entry)

        # Flag low quality detections
        # Use rms_int16 for threshold comparison (int16 domain, threshold 100.0)
        # If only normalized rms is available, convert it (rms * 32768.0)
        snr = entry.get("snr_db", 0)
        rms_int16 = entry.get("rms_int16", 0)
        if rms_int16 == 0 and "rms" in entry:
            # Convert normalized RMS to int16 domain for threshold comparison
            rms_int16 = entry["rms"] * 32768.0
        if snr < 10.0 or rms_int16 < 100.0:
            low_quality_detections.append(entry)

    # Calculate statistics
    report = {
        "summary": {
            "total_log_lines": total_lines,
            "parsed_wake_detection_entries": parsed_entries,
            "successful_detections": len(successful_detections),
            "failed_detections": len(failed_detections),
            "low_quality_detections": len(low_quality_detections),
        },
        "quality_metrics": {},
        "low_quality_samples": low_quality_detections[:10],  # First 10 examples
    }

    # Calculate averages
    # Prefer rms_int16 for reporting (int16 domain is more intuitive for thresholds)
    if quality_stats["rms_int16"]:
        report["quality_metrics"]["rms_int16"] = {
            "avg": sum(quality_stats["rms_int16"]) / len(quality_stats["rms_int16"]),
            "min": min(quality_stats["rms_int16"]),
            "max": max(quality_stats["rms_int16"]),
            "count": len(quality_stats["rms_int16"]),
        }
    if quality_stats["rms"]:
        report["quality_metrics"]["rms"] = {
            "avg": sum(quality_stats["rms"]) / len(quality_stats["rms"]),
            "min": min(quality_stats["rms"]),
            "max": max(quality_stats["rms"]),
            "count": len(quality_stats["rms"]),
        }

    if quality_stats["snr_db"]:
        report["quality_metrics"]["snr_db"] = {
            "avg": sum(quality_stats["snr_db"]) / len(quality_stats["snr_db"]),
            "min": min(quality_stats["snr_db"]),
            "max": max(quality_stats["snr_db"]),
            "count": len(quality_stats["snr_db"]),
        }

    if quality_stats["clarity_score"]:
        report["quality_metrics"]["clarity_score"] = {
            "avg": sum(quality_stats["clarity_score"]) / len(quality_stats["clarity_score"]),
            "min": min(quality_stats["clarity_score"]),
            "max": max(quality_stats["clarity_score"]),
            "count": len(quality_stats["clarity_score"]),
        }

    return report


def main() -> int:
    """Main entry point for audio quality analysis script."""
    parser = argparse.ArgumentParser(
        description="Analyze audio quality metrics from wake detection logs"
    )
    parser.add_argument(
        "log_file",
        nargs="?",
        type=Path,
        default=None,
        help="Path to log file (default: read from stdin)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output file for JSON report (default: stdout)",
    )

    args = parser.parse_args()

    # Analyze logs
    report = analyze_logs(args.log_file)

    if "error" in report:
        print(json.dumps(report, indent=2), file=sys.stderr)
        return 1

    # Output report
    output_json = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(output_json, encoding="utf-8")
        print(f"Report written to: {args.output}", file=sys.stderr)
    else:
        print(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())

