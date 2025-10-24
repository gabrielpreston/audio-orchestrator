"""Base contract definitions for service contracts."""

from dataclasses import dataclass, field
import enum
from typing import Any


class ContractType(enum.Enum):
    HTTP_API = "http_api"
    INTERFACE = "interface"
    HEALTH = "health"
    PERFORMANCE = "performance"
    SECURITY = "security"


@dataclass
class EndpointContract:
    name: str
    path: str
    method: str
    expected_status_codes: list[int]
    request_schema: dict[str, Any] | None = None
    response_schema: dict[str, Any] | None = None
    timeout_ms: int = 5000


@dataclass
class InterfaceContract:
    interface_name: str
    methods: list[str]
    required_properties: list[str] = field(default_factory=list)
    lifecycle_methods: list[str] = field(default_factory=list)
    telemetry_methods: list[str] = field(default_factory=list)


@dataclass
class PerformanceContract:
    max_latency_ms: int
    min_throughput_rps: int | None = None
    max_memory_mb: int | None = None
    max_cpu_percent: float | None = None
    availability_percent: float = 99.9


@dataclass
class SecurityContract:
    authentication_required: bool = False
    authorization_required: bool = False
    data_encryption_required: bool = False
    pii_handling_required: bool = False


@dataclass
class ValidationResult:
    """Result of contract validation."""

    contract_name: str
    passed: bool
    errors: list[str]
    warnings: list[str]
    performance_metrics: dict[str, Any]
    validation_time_ms: float

    def add_error(self, error: str) -> None:
        """Add an error to the validation result."""
        self.errors.append(error)
        self.passed = False

    def add_warning(self, warning: str) -> None:
        """Add a warning to the validation result."""
        self.warnings.append(warning)


@dataclass
class ServiceContract:
    service_name: str
    base_url: str
    version: str = "1.0.0"
    endpoints: list[EndpointContract] = field(default_factory=list)
    interfaces: list[InterfaceContract] = field(default_factory=list)
    performance: PerformanceContract | None = None
    security: SecurityContract | None = None
    health_endpoints: list[EndpointContract] = field(default_factory=list)
