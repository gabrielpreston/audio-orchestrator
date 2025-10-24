"""STT service contract definition."""

from services.tests.contracts.base_contracts import (
    EndpointContract,
    InterfaceContract,
    PerformanceContract,
    SecurityContract,
    ServiceContract,
)

# STT Service Contract
STT_CONTRACT = ServiceContract(
    service_name="stt",
    base_url="http://stt:9000",
    version="1.0.0",
    endpoints=[
        EndpointContract(
            name="transcribe",
            path="/transcribe",
            method="POST",
            expected_status_codes=[200],
            timeout_ms=30000,
        ),
        EndpointContract(
            name="asr",
            path="/asr",
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
            interface_name="STTInterface",
            methods=["transcribe", "asr", "health_check"],
            required_properties=["model_path", "sample_rate"],
            lifecycle_methods=["initialize", "cleanup"],
            telemetry_methods=["get_metrics", "get_stats"],
        ),
    ],
    performance=PerformanceContract(
        max_latency_ms=5000,
        min_throughput_rps=10,
        max_memory_mb=2000,
        max_cpu_percent=90.0,
        availability_percent=99.9,
    ),
    security=SecurityContract(
        authentication_required=False,
        authorization_required=False,
        data_encryption_required=False,
        pii_handling_required=True,
    ),
)
