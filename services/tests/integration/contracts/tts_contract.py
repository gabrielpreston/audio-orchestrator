"""TTS service contract definition."""

from services.tests.contracts.base_contracts import (
    EndpointContract,
    InterfaceContract,
    PerformanceContract,
    SecurityContract,
    ServiceContract,
)

# TTS Service Contract
TTS_CONTRACT = ServiceContract(
    service_name="bark",
    base_url="http://bark:7100",
    version="1.0.0",
    endpoints=[
        EndpointContract(
            name="synthesize",
            path="/synthesize",
            method="POST",
            expected_status_codes=[200],
            timeout_ms=30000,
        ),
        EndpointContract(
            name="voices",
            path="/voices",
            method="GET",
            expected_status_codes=[200],
            timeout_ms=5000,
        ),
        EndpointContract(
            name="metrics",
            path="/metrics",
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
            interface_name="TTSInterface",
            methods=["synthesize", "list_voices", "get_metrics", "health_check"],
            required_properties=["model_path", "voice"],
            lifecycle_methods=["initialize", "cleanup"],
            telemetry_methods=["get_metrics", "get_stats"],
        ),
    ],
    performance=PerformanceContract(
        max_latency_ms=10000,
        min_throughput_rps=5,
        max_memory_mb=1000,
        max_cpu_percent=80.0,
        availability_percent=99.9,
    ),
    security=SecurityContract(
        authentication_required=True,
        authorization_required=False,
        data_encryption_required=False,
        pii_handling_required=False,
    ),
)
