"""Parameterized unit tests for service contract definitions."""

import pytest

from services.common.validation import (
    check_contract_compliance,
    validate_service_contract,
)
from services.tests.integration.contracts.llm_contract import LLM_CONTRACT
from services.tests.integration.contracts.orchestrator_contract import (
    ORCHESTRATOR_CONTRACT,
)
from services.tests.integration.contracts.stt_contract import STT_CONTRACT
from services.tests.integration.contracts.tts_contract import TTS_CONTRACT


@pytest.mark.parametrize(
    "contract,service_name,base_url",
    [
        (STT_CONTRACT, "stt", "http://stt:9000"),
        (LLM_CONTRACT, "llm-flan", "http://llm-flan:8100"),
        (TTS_CONTRACT, "tts-bark", "http://tts-bark:7100"),
        (
            ORCHESTRATOR_CONTRACT,
            "orchestrator-enhanced",
            "http://orchestrator-enhanced:8200",
        ),
    ],
)
class TestServiceContractDefinitions:
    """Parameterized tests for all service contracts."""

    @pytest.mark.unit
    def test_contract_structure(self, contract, service_name, base_url):
        """Test that contract has proper structure."""
        assert hasattr(contract, "service_name")
        assert hasattr(contract, "base_url")
        assert hasattr(contract, "version")
        assert hasattr(contract, "endpoints")
        assert hasattr(contract, "interfaces")
        assert hasattr(contract, "performance")
        assert hasattr(contract, "security")

    @pytest.mark.unit
    def test_contract_service_name(self, contract, service_name, base_url):
        """Test contract service name."""
        assert contract.service_name == service_name
        assert isinstance(contract.service_name, str)

    @pytest.mark.unit
    def test_contract_base_url(self, contract, service_name, base_url):
        """Test contract base URL."""
        assert contract.base_url == base_url
        assert isinstance(contract.base_url, str)

    @pytest.mark.unit
    def test_contract_version(self, contract, service_name, base_url):
        """Test contract version."""
        assert hasattr(contract, "version")
        assert isinstance(contract.version, str)
        assert contract.version == "1.0.0"

    @pytest.mark.unit
    def test_contract_endpoints(self, contract, service_name, base_url):
        """Test contract endpoints."""
        assert hasattr(contract, "endpoints")
        assert isinstance(contract.endpoints, list)
        assert len(contract.endpoints) > 0

        # Check for health endpoints
        health_endpoints = [e for e in contract.endpoints if "health" in e.name.lower()]
        assert len(health_endpoints) >= 2  # Should have live and ready endpoints

    @pytest.mark.unit
    def test_contract_interfaces(self, contract, service_name, base_url):
        """Test contract interfaces."""
        assert hasattr(contract, "interfaces")
        assert isinstance(contract.interfaces, list)
        assert len(contract.interfaces) > 0

    @pytest.mark.unit
    def test_contract_performance(self, contract, service_name, base_url):
        """Test contract performance requirements."""
        assert hasattr(contract, "performance")
        assert contract.performance is not None
        assert hasattr(contract.performance, "max_latency_ms")
        assert hasattr(contract.performance, "min_throughput_rps")

    @pytest.mark.unit
    def test_contract_security(self, contract, service_name, base_url):
        """Test contract security requirements."""
        assert hasattr(contract, "security")
        assert contract.security is not None
        assert hasattr(contract.security, "authentication_required")
        assert hasattr(contract.security, "authorization_required")

    @pytest.mark.unit
    def test_contract_validation(self, contract, service_name, base_url):
        """Test contract validation."""
        result = validate_service_contract(contract)
        assert result["valid"] is True
        assert len(result["issues"]) == 0

    @pytest.mark.unit
    def test_contract_compliance(self, contract, service_name, base_url):
        """Test contract compliance."""
        result = check_contract_compliance(contract)
        assert result["compliant"] is True
        assert result["compliance_score"] > 0.8
        assert result["compliance_score"] > 0.8
