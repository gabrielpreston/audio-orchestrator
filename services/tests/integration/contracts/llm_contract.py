"""LLM service contract definition."""

from services.tests.contracts.base_contracts import (
    EndpointContract,
    InterfaceContract,
    PerformanceContract,
    SecurityContract,
    ServiceContract,
)

# LLM Service Contract
LLM_CONTRACT = ServiceContract(
    service_name="flan",
    base_url="http://flan:8100",
    version="1.0.0",
    endpoints=[
        EndpointContract(
            name="chat_completions",
            path="/v1/chat/completions",
            method="POST",
            expected_status_codes=[200],
            timeout_ms=30000,
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
            interface_name="LLMInterface",
            methods=["chat_completions", "health_check"],
            required_properties=["model_path", "context_length"],
            lifecycle_methods=["initialize", "cleanup"],
            telemetry_methods=["get_metrics", "get_stats"],
        ),
    ],
    performance=PerformanceContract(
        max_latency_ms=30000,
        min_throughput_rps=1,
        max_memory_mb=1000,
        max_cpu_percent=80.0,
        availability_percent=99.9,
    ),
    security=SecurityContract(
        authentication_required=True,
        authorization_required=False,
        data_encryption_required=False,
        pii_handling_required=True,
    ),
)
