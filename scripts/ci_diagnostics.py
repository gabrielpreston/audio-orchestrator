#!/usr/bin/env python3
"""
CI Diagnostics Script

This script provides comprehensive diagnostics for CI smoke test failures,
including service status, logs, and system information.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional


def run_command(cmd: List[str], capture_output: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    try:
        return subprocess.run(cmd, capture_output=capture_output, text=True, check=False)
    except Exception as e:
        print(f"Error running command {' '.join(cmd)}: {e}")
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def get_docker_info() -> Dict[str, Any]:
    """Get Docker system information."""
    info = {}

    # Docker version
    result = run_command(["docker", "--version"])
    info["docker_version"] = result.stdout.strip() if result.returncode == 0 else "Unknown"

    # Docker compose version
    result = run_command(["docker", "compose", "version"])
    info["docker_compose_version"] = result.stdout.strip() if result.returncode == 0 else "Unknown"

    # Docker system info
    result = run_command(["docker", "system", "df"])
    info["docker_disk_usage"] = result.stdout if result.returncode == 0 else "Unknown"

    # Docker images
    result = run_command(["docker", "images", "--format", "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"])
    info["docker_images"] = result.stdout if result.returncode == 0 else "Unknown"

    return info


def get_service_status(service_name: str) -> Dict[str, Any]:
    """Get detailed status for a specific service."""
    status = {
        "service_name": service_name,
        "container_status": "unknown",
        "health_status": "unknown",
        "logs": [],
        "resource_usage": {},
        "network_info": {}
    }

    # Get container status
    result = run_command(["docker", "compose", "-f", "docker-compose.ci.yml", "ps", service_name])
    if result.returncode == 0:
        status["container_status"] = result.stdout.strip()

    # Get health status
    result = run_command(["docker", "compose", "-f", "docker-compose.ci.yml", "ps", "--format", "json", service_name])
    if result.returncode == 0:
        try:
            ps_data = json.loads(result.stdout)
            if ps_data and len(ps_data) > 0:
                container_info = ps_data[0]
                status["health_status"] = container_info.get("Health", "unknown")
                status["state"] = container_info.get("State", "unknown")
        except json.JSONDecodeError:
            pass

    # Get recent logs (last 50 lines)
    result = run_command(["docker", "compose", "-f", "docker-compose.ci.yml", "logs", "--tail", "50", service_name])
    if result.returncode == 0:
        status["logs"] = result.stdout.split('\n')[-50:]  # Last 50 lines

    # Get resource usage
    result = run_command(["docker", "stats", "--no-stream", "--format", "json", service_name])
    if result.returncode == 0:
        try:
            stats_data = json.loads(result.stdout)
            if stats_data:
                status["resource_usage"] = {
                    "cpu_percent": stats_data.get("CPUPerc", "unknown"),
                    "memory_usage": stats_data.get("MemUsage", "unknown"),
                    "memory_percent": stats_data.get("MemPerc", "unknown")
                }
        except json.JSONDecodeError:
            pass

    return status


def get_network_info() -> Dict[str, Any]:
    """Get Docker network information."""
    info = {}

    # List networks
    result = run_command(["docker", "network", "ls"])
    info["networks"] = result.stdout if result.returncode == 0 else "Unknown"

    # Get network details
    result = run_command(["docker", "compose", "-f", "docker-compose.ci.yml", "ps", "--format", "json"])
    if result.returncode == 0:
        try:
            ps_data = json.loads(result.stdout)
            info["services"] = ps_data
        except json.JSONDecodeError:
            pass

    return info


def generate_diagnostics_report(service_name: str) -> Dict[str, Any]:
    """Generate a comprehensive diagnostics report."""
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "service_name": service_name,
        "docker_info": get_docker_info(),
        "service_status": get_service_status(service_name),
        "network_info": get_network_info(),
        "system_info": {
            "python_version": sys.version,
            "working_directory": str(Path.cwd()),
        }
    }

    return report


def print_diagnostics_summary(report: Dict[str, Any]) -> None:
    """Print a human-readable diagnostics summary."""
    print("🔍 CI Diagnostics Report")
    print("=" * 50)
    print(f"Service: {report['service_name']}")
    print(f"Timestamp: {report['timestamp']}")
    print()

    # Service status
    service_status = report["service_status"]
    print("📊 Service Status:")
    print(f"  Container: {service_status['container_status']}")
    print(f"  Health: {service_status['health_status']}")
    print(f"  State: {service_status.get('state', 'unknown')}")
    print()

    # Resource usage
    if service_status["resource_usage"]:
        print("💻 Resource Usage:")
        for key, value in service_status["resource_usage"].items():
            print(f"  {key}: {value}")
        print()

    # Recent logs
    if service_status["logs"]:
        print("📝 Recent Logs (last 10 lines):")
        for line in service_status["logs"][-10:]:
            if line.strip():
                print(f"  {line}")
        print()

    # Docker info
    docker_info = report["docker_info"]
    print("🐳 Docker Information:")
    print(f"  Version: {docker_info['docker_version']}")
    print(f"  Compose: {docker_info['docker_compose_version']}")
    print()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/ci_diagnostics.py <service_name> [--json]")
        print("       python scripts/ci_diagnostics.py all [--json]")
        sys.exit(1)

    service_name = sys.argv[1]
    output_json = "--json" in sys.argv

    if service_name == "all":
        # Generate diagnostics for all services
        services = ["discord", "stt", "flan", "orchestrator", "bark", "audio", "guardrails", "testing", "monitoring"]
        for svc in services:
            report = generate_diagnostics_report(svc)
            if output_json:
                print(json.dumps(report, indent=2))
            else:
                print_diagnostics_summary(report)
                print("-" * 50)
    else:
        # Generate diagnostics for specific service
        report = generate_diagnostics_report(service_name)

        if output_json:
            print(json.dumps(report, indent=2))
        else:
            print_diagnostics_summary(report)


if __name__ == "__main__":
    main()
