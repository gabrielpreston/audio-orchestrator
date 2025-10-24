"""Orchestrator service contract definition."""

from services.tests.contracts.base_contracts import (
    EndpointContract,
    InterfaceContract,
    PerformanceContract,
    SecurityContract,
    ServiceContract,
)

# Orchestrator Service Contract
ORCHESTRATOR_CONTRACT = ServiceContract(
    service_name="orchestrator-enhanced",
    base_url="http://orchestrator-enhanced:8200",
    version="1.0.0",
    endpoints=[
        EndpointContract(
            name="mcp_transcript",
            path="/mcp/transcript",
            method="POST",
            expected_status_codes=[200],
            timeout_ms=30000,
        ),
        EndpointContract(
            name="mcp_tools",
            path="/mcp/tools",
            method="GET",
            expected_status_codes=[200],
            timeout_ms=5000,
        ),
        EndpointContract(
            name="mcp_connections",
            path="/mcp/connections",
            method="GET",
            expected_status_codes=[200],
            timeout_ms=5000,
        ),
        EndpointContract(
            name="health_live",
            path="/health/live",
            method="GET",
            expected_status_codes=[200],
            timeout_ms=5000,
        ),
        EndpointContract(
            name="health_ready",
            path="/health/ready",
            method="GET",
            expected_status_codes=[200],
            timeout_ms=5000,
        ),
    ],
    interfaces=[
        InterfaceContract(
            interface_name="OrchestratorInterface",
            methods=[
                "mcp_transcript",
                "list_mcp_tools",
                "list_mcp_connections",
                "health_check",
            ],
            required_properties=["session_manager", "agent_registry"],
            lifecycle_methods=["initialize", "cleanup"],
            telemetry_methods=["get_metrics", "get_stats"],
        ),
    ],
    performance=PerformanceContract(
        max_latency_ms=30000,
        min_throughput_rps=5,
        max_memory_mb=500,
        max_cpu_percent=70.0,
        availability_percent=99.9,
    ),
    security=SecurityContract(
        authentication_required=True,
        authorization_required=False,
        data_encryption_required=False,
        pii_handling_required=True,
    ),
)
