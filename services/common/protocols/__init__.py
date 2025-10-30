"""Core protocol definitions for audio-orchestrator.

This module provides base protocol patterns used across all services.
Protocols enable structural subtyping and composition over inheritance.
"""

from .core import LifecycleProtocol, HealthProtocol, ConfigurableProtocol
from .service import ServiceDiscoveryProtocol, ServiceCommunicationProtocol

__all__ = [
    "ConfigurableProtocol",
    "HealthProtocol",
    "LifecycleProtocol",
    "ServiceCommunicationProtocol",
    "ServiceDiscoveryProtocol",
]
