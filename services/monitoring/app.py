"""
Monitoring Dashboard service for Audio Orchestrator.

Provides a Streamlit dashboard for monitoring system health,
performance metrics, and guardrail statistics.
"""

import os
from typing import Any

from fastapi import FastAPI

from services.common.audio_metrics import create_http_metrics
from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints
from services.common.structured_logging import configure_logging, get_logger
from services.common.tracing import setup_service_observability


# Import optional dependencies with error handling
try:
    import httpx
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
    import streamlit as st

    DASHBOARD_AVAILABLE = True
except ImportError:
    DASHBOARD_AVAILABLE = False
    pd = None
    px = None
    go = None
    st = None
    httpx = None

# Configure logging
configure_logging("info", json_logs=True, service_name="monitoring")
logger = get_logger(__name__, service_name="monitoring")

# FastAPI app for health checks
app = FastAPI(title="Monitoring Dashboard Service", version="1.0.0")

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
                    logger.error("Failed to query Prometheus", error=str(e))
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
        logger.error("Health data fetch failed", error=str(e))


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
        logger.error("Performance data fetch failed", error=str(e))


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
        logger.error("Guardrail data fetch failed", error=str(e))


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
        logger.error("System metrics fetch failed", error=str(e))


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


# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="monitoring",
    health_manager=health_manager,
    custom_components={
        "dashboard_available": lambda: DASHBOARD_AVAILABLE,
        "prometheus_connected": lambda: _check_prometheus_health(),
    },
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())


@app.on_event("startup")  # type: ignore[misc]
async def startup_event() -> None:
    """Service startup event handler."""
    global _observability_manager, _http_metrics

    try:
        # Setup observability (tracing + metrics)
        _observability_manager = setup_service_observability("monitoring", "1.0.0")
        _observability_manager.instrument_fastapi(app)

        # Create service-specific metrics
        _http_metrics = create_http_metrics(_observability_manager)

        # Set observability manager in health manager
        health_manager.set_observability_manager(_observability_manager)

        logger.info("Monitoring dashboard service starting up")
        health_manager.mark_startup_complete()
    except Exception as exc:
        logger.error("Monitoring dashboard service startup failed", error=str(exc))
        # Continue without crashing - service will report not_ready


@app.on_event("shutdown")  # type: ignore[misc]
async def shutdown_event() -> None:
    """Service shutdown event handler."""
    logger.info("Monitoring dashboard service shutting down")
    # Health manager will handle shutdown automatically


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
                "services/monitoring_dashboard/app.py",
                "--server.port=8501",
                "--server.address=0.0.0.0",
            ],
            check=True,
        )
    )
    streamlit_thread.daemon = True
    streamlit_thread.start()

    # Start FastAPI server for health checks
    uvicorn.run(app, host="127.0.0.1", port=8502)
    # Start FastAPI server for health checks
    uvicorn.run(app, host="127.0.0.1", port=8502)
