"""
Monitoring Dashboard service for Audio Orchestrator.

Provides a Streamlit dashboard for monitoring system health,
performance metrics, and guardrail statistics.
"""

import os
from typing import Any

from services.common.app_factory import create_service_app
from services.common.audio_metrics import create_http_metrics
from services.common.config import (
    LoggingConfig,
    get_service_preset,
)
from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints
from services.common.structured_logging import configure_logging, get_logger
from services.common.tracing import get_observability_manager

# Load configuration using standard config classes
_config_preset = get_service_preset("monitoring")
_logging_config = LoggingConfig(**_config_preset["logging"])

# Configure logging early so we can log import errors
configure_logging(
    _logging_config.level,
    json_logs=_logging_config.json_logs,
    service_name="monitoring",
)
logger = get_logger(__name__, service_name="monitoring")

# Import optional dependencies with error handling
try:
    import httpx
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
    import streamlit as st

    DASHBOARD_AVAILABLE = True
    logger.debug("monitoring.dashboard_dependencies_available")
except Exception as exc:
    DASHBOARD_AVAILABLE = False
    pd = None
    px = None
    go = None
    st = None
    httpx = None
    # Log the actual error for debugging
    logger.warning(
        "monitoring.dashboard_dependencies_unavailable",
        error=str(exc),
        error_type=type(exc).__name__,
    )


# Health manager and observability
health_manager = HealthManager("monitoring")
_observability_manager = None
_http_metrics = {}

# Prometheus connection via HTTP client
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")


def create_monitoring_dashboard() -> None:
    """Create the Streamlit monitoring dashboard."""

    if not DASHBOARD_AVAILABLE:
        raise ImportError("Dashboard dependencies are not available")

    st.set_page_config(
        page_title="Audio Orchestrator Monitoring", page_icon="🎵", layout="wide"
    )

    st.title("🎵 Audio Orchestrator Monitoring Dashboard")
    st.markdown("Real-time monitoring of the enhanced audio processing pipeline")

    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        time_range = st.selectbox("Time Range", ["1h", "6h", "24h", "7d"], index=1)
        refresh_interval = st.selectbox(
            "Refresh Interval", ["10s", "30s", "1m", "5m"], index=1
        )
        auto_refresh = st.checkbox("Auto Refresh", value=True)

    # Main dashboard content
    tab1, tab2, tab3, tab4 = st.tabs(
        ["🏥 Service Health", "⚡ Performance", "🛡️ Guardrails", "📊 System Metrics"]
    )

    with tab1:
        display_service_health()

    with tab2:
        display_performance_metrics(time_range)

    with tab3:
        display_guardrail_metrics(time_range)

    with tab4:
        display_system_metrics(time_range)

    # Auto refresh
    if auto_refresh:
        import time

        time.sleep(int(refresh_interval.replace("s", "").replace("m", "60")))
        st.rerun()


def display_service_health() -> None:
    """Display service health status."""
    st.header("Service Health Status")

    try:
        # Query service health metrics via HTTP
        async def get_health_data() -> dict[str, Any] | None:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        f"{PROMETHEUS_URL}/api/v1/query",
                        params={
                            "query": 'audio_orchestrator_service_health_status{component="overall"}'
                        },
                    )
                    response.raise_for_status()
                    return dict(response.json())
                except Exception as e:
                    logger.warning(
                        "monitoring.prometheus_query_failed",
                        error=str(e),
                        error_type=type(e).__name__,
                        note="Prometheus may be unavailable",
                    )
                    return None

        # For now, show placeholder data since we can't easily make async calls in Streamlit
        st.info(
            "Service health monitoring is being migrated to OpenTelemetry. Please check individual service health endpoints."
        )

        # Individual service health
        services = [
            "discord",
            "stt",
            "flan",
            "audio",
            "bark",
            "orchestrator",
            "guardrails",
        ]

        cols = st.columns(3)
        for i, service in enumerate(services):
            with cols[i % 3]:
                st.metric(f"{service.title()}", "OpenTelemetry", delta=None)

    except Exception as e:
        st.error(f"Failed to fetch health data: {str(e)}")
        logger.warning(
            "monitoring.health_data_fetch_failed",
            error=str(e),
            error_type=type(e).__name__,
            note="Dashboard will show placeholder data",
        )


def display_performance_metrics(_time_range: str) -> None:
    """Display performance metrics."""
    st.header("Performance Metrics")

    try:
        st.info(
            "Performance metrics are being migrated to OpenTelemetry. Please check Grafana dashboards for real-time metrics."
        )

        # Placeholder metrics display
        st.subheader("Latency Distribution")
        st.info("Latency metrics will be available in Grafana dashboards")

        st.subheader("Request Throughput")
        st.info("Throughput metrics will be available in Grafana dashboards")

    except Exception as e:
        st.error(f"Failed to fetch performance data: {str(e)}")
        logger.warning(
            "monitoring.performance_data_fetch_failed",
            error=str(e),
            error_type=type(e).__name__,
            note="Dashboard will show placeholder data",
        )


def display_guardrail_metrics(_time_range: str) -> None:
    """Display guardrail metrics."""
    st.header("Guardrail Statistics")

    try:
        st.info(
            "Guardrail metrics are being migrated to OpenTelemetry. Please check Grafana dashboards for real-time metrics."
        )

        # Placeholder metrics display
        st.subheader("Blocked Requests")
        st.info("Blocked request metrics will be available in Grafana dashboards")

        st.subheader("Safety Metrics")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Toxicity Blocks", "OpenTelemetry")
        with col2:
            st.metric("PII Blocks", "OpenTelemetry")
        with col3:
            st.metric("Injection Blocks", "OpenTelemetry")

    except Exception as e:
        st.error(f"Failed to fetch guardrail data: {str(e)}")
        logger.warning(
            "monitoring.guardrail_data_fetch_failed",
            error=str(e),
            error_type=type(e).__name__,
            note="Dashboard will show placeholder data",
        )


def display_system_metrics(_time_range: str) -> None:
    """Display system resource metrics."""
    st.header("System Resource Metrics")

    try:
        st.info(
            "System metrics are being migrated to OpenTelemetry. Please check Grafana dashboards for real-time metrics."
        )

        # Placeholder metrics display
        st.subheader("Memory Usage")
        st.info("Memory usage metrics will be available in Grafana dashboards")

        st.subheader("CPU Usage")
        st.info("CPU usage metrics will be available in Grafana dashboards")

    except Exception as e:
        st.error(f"Failed to fetch system metrics: {str(e)}")
        logger.warning(
            "monitoring.system_metrics_fetch_failed",
            error=str(e),
            error_type=type(e).__name__,
            note="Dashboard will show placeholder data",
        )


async def _check_prometheus_health() -> bool:
    """Check if Prometheus is healthy."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": "up"},
                timeout=5.0,
            )
            return bool(response.status_code == 200)
    except Exception:
        return False


async def _startup() -> None:
    """Service startup event handler."""
    global _observability_manager, _http_metrics

    try:
        # Get observability manager (factory already setup observability)
        _observability_manager = get_observability_manager("monitoring")

        # Create service-specific metrics
        _http_metrics = create_http_metrics(_observability_manager)

        # Set observability manager in health manager
        health_manager.set_observability_manager(_observability_manager)
    except Exception as exc:
        logger.error("Monitoring dashboard service startup failed", error=str(exc))
        # Continue without crashing - service will report not_ready
    finally:
        # Always mark startup complete so health endpoint becomes available
        logger.info("Monitoring dashboard service starting up")
        health_manager.mark_startup_complete()


async def _shutdown() -> None:
    """Service shutdown event handler."""
    logger.info("Monitoring dashboard service shutting down")
    # Health manager will handle shutdown automatically


# Create app using factory pattern
app = create_service_app(
    "monitoring",
    "1.0.0",
    title="Monitoring Dashboard Service",
    startup_callback=_startup,
    shutdown_callback=_shutdown,
)


# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="monitoring",
    health_manager=health_manager,
    custom_components={
        "dashboard_available": lambda: bool(DASHBOARD_AVAILABLE),
        # Pass async function directly so HealthEndpoints awaits it
        "prometheus_connected": _check_prometheus_health,
    },
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())


if __name__ == "__main__":
    import subprocess

    # Create and launch Streamlit dashboard
    import threading

    import uvicorn

    streamlit_thread = threading.Thread(
        target=lambda: subprocess.run(
            [
                "streamlit",
                "run",
                "services/monitoring/dashboard.py",
                "--server.port=8501",
                "--server.address=0.0.0.0",
            ],
            check=True,
        )
    )
    streamlit_thread.daemon = True
    streamlit_thread.start()

    # Start FastAPI server for health checks (bind to all interfaces for reliability)
    uvicorn.run(app, host="0.0.0.0", port=8502)
