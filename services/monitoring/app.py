"""
Monitoring Dashboard service for Audio Orchestrator.

Provides a Streamlit dashboard for monitoring system health,
performance metrics, and guardrail statistics.
"""

import os
from contextlib import suppress

from services.common.app_factory import create_service_app
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

# Import dashboard dependencies with strict fail-fast
try:
    import httpx
    import pandas as pd  # noqa: F401
    import plotly.express as px  # noqa: F401
    import plotly.graph_objects as go  # noqa: F401
    import streamlit as st
except ImportError as exc:
    raise ImportError(
        f"Required dashboard dependencies not available: {exc}. "
        "Monitoring service requires streamlit, pandas, and plotly. "
        "Use python-web base image or explicitly install these dependencies."
    ) from exc


# Health manager and observability
health_manager = HealthManager("monitoring")
_observability_manager = None

# Prometheus connection via HTTP client
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")


def create_monitoring_dashboard() -> None:
    """Create the Streamlit monitoring dashboard."""

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
        # Query service health metrics via synchronous HTTP client
        health_data: dict[str, float] = {}

        with httpx.Client(timeout=5.0) as client:
            try:
                response = client.get(
                    f"{PROMETHEUS_URL}/api/v1/query",
                    params={
                        "query": 'audio_orchestrator_service_health_status{component="overall"}'
                    },
                )
                response.raise_for_status()
                result = response.json()

                # Parse Prometheus response
                if result.get("status") == "success" and result.get("data", {}).get(
                    "result"
                ):
                    for item in result["data"]["result"]:
                        service_name = item["metric"].get("service", "unknown")
                        # Value is [timestamp, value_string]
                        value = float(item["value"][1])
                        health_data[service_name] = value
            except Exception as e:
                logger.warning(
                    "monitoring.prometheus_query_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    note="Prometheus may be unavailable",
                )
                st.warning(f"Could not connect to Prometheus: {str(e)}")

        # Expected services
        services = [
            "discord",
            "stt",
            "flan",
            "audio",
            "bark",
            "orchestrator",
            "guardrails",
            "monitoring",
        ]

        # Display service health status
        cols = st.columns(3)
        for i, service in enumerate(services):
            with cols[i % 3]:
                if service in health_data:
                    health_value = health_data[service]
                    # Health values: 1 = healthy, 0.5 = degraded, 0 = unhealthy
                    if health_value >= 1.0:
                        status = "🟢 Healthy"
                    elif health_value >= 0.5:
                        status = "🟡 Degraded"
                    else:
                        status = "🔴 Unhealthy"

                    st.metric(
                        f"{service.title()}",
                        status,
                        delta=None,
                    )
                else:
                    st.metric(
                        f"{service.title()}",
                        "⚪ Unknown",
                        delta=None,
                    )

        if not health_data:
            st.info(
                "No health data available. Services may still be starting up, or Prometheus may not be receiving metrics yet."
            )

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
        # Query HTTP performance metrics
        with httpx.Client(timeout=5.0) as client:
            try:
                # Get request rate
                rate_response = client.get(
                    f"{PROMETHEUS_URL}/api/v1/query",
                    params={
                        "query": "sum(rate(audio_orchestrator_http_server_duration_milliseconds_count[5m]))"
                    },
                )

                # Get 95th percentile latency
                latency_response = client.get(
                    f"{PROMETHEUS_URL}/api/v1/query",
                    params={
                        "query": "histogram_quantile(0.95, sum(rate(audio_orchestrator_http_server_duration_milliseconds_bucket[5m])) by (le)) / 1000"
                    },
                )

                rate_result = (
                    rate_response.json() if rate_response.status_code == 200 else None
                )
                latency_result = (
                    latency_response.json()
                    if latency_response.status_code == 200
                    else None
                )

                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("Request Throughput")
                    if rate_result and rate_result.get("status") == "success":
                        rate_value = (
                            rate_result.get("data", {})
                            .get("result", [{}])[0]
                            .get("value", [None, "0"])[1]
                        )
                        try:
                            rate_float = float(rate_value)
                            st.metric("Requests/sec", f"{rate_float:.2f}")
                        except (ValueError, TypeError):
                            st.info("No data available yet")
                    else:
                        st.info("No data available yet")

                with col2:
                    st.subheader("95th Percentile Latency")
                    if latency_result and latency_result.get("status") == "success":
                        latency_value = (
                            latency_result.get("data", {})
                            .get("result", [{}])[0]
                            .get("value", [None, "0"])[1]
                        )
                        try:
                            latency_float = float(latency_value)
                            st.metric("Latency", f"{latency_float*1000:.2f} ms")
                        except (ValueError, TypeError):
                            st.info("No data available yet")
                    else:
                        st.info("No data available yet")

            except Exception as e:
                logger.warning(
                    "monitoring.performance_query_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                st.info(
                    "Performance metrics will appear once services receive requests. Check Grafana dashboards for detailed metrics."
                )

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
        # Query guardrail metrics from Prometheus
        with httpx.Client(timeout=5.0) as client:
            try:
                # Get validation requests (blocked vs allowed)
                blocked_query = 'sum(rate(audio_orchestrator_guardrails_validation_requests_total{status="blocked"}[5m]))'
                allowed_query = 'sum(rate(audio_orchestrator_guardrails_validation_requests_total{status="success"}[5m]))'

                # Get toxicity checks
                toxicity_query = (
                    "sum(rate(audio_orchestrator_guardrails_toxicity_checks_total[5m]))"
                )

                # Get PII detections
                pii_query = (
                    "sum(rate(audio_orchestrator_guardrails_pii_detections_total[5m]))"
                )

                # Get rate limit hits
                rate_limit_query = (
                    "sum(rate(audio_orchestrator_guardrails_rate_limit_hits_total[5m]))"
                )

                # Get escalations
                escalations_query = (
                    "sum(rate(audio_orchestrator_guardrails_escalations_total[5m]))"
                )

                queries = {
                    "blocked": blocked_query,
                    "allowed": allowed_query,
                    "toxicity": toxicity_query,
                    "pii": pii_query,
                    "rate_limit": rate_limit_query,
                    "escalations": escalations_query,
                }

                results = {}
                for key, query in queries.items():
                    try:
                        response = client.get(
                            f"{PROMETHEUS_URL}/api/v1/query",
                            params={"query": query},
                        )
                        if response.status_code == 200:
                            result = response.json()
                            if result.get("status") == "success" and result.get(
                                "data", {}
                            ).get("result"):
                                value = result["data"]["result"][0].get(
                                    "value", [None, "0"]
                                )[1]
                                results[key] = (
                                    float(value) if value and value != "0" else 0.0
                                )
                            else:
                                results[key] = 0.0
                        else:
                            results[key] = 0.0
                    except Exception:
                        results[key] = 0.0

                # Display blocked requests
                st.subheader("Blocked Requests")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Blocked Rate", f"{results.get('blocked', 0.0):.2f}/sec")
                with col2:
                    st.metric("Allowed Rate", f"{results.get('allowed', 0.0):.2f}/sec")

                # Display safety metrics
                st.subheader("Safety Metrics")
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        "Toxicity Checks", f"{results.get('toxicity', 0.0):.2f}/sec"
                    )
                with col2:
                    st.metric("PII Detections", f"{results.get('pii', 0.0):.2f}/sec")
                with col3:
                    st.metric(
                        "Rate Limit Hits", f"{results.get('rate_limit', 0.0):.2f}/sec"
                    )

                # Display escalations
                st.subheader("Escalations")
                st.metric(
                    "Escalations to Human Review",
                    f"{results.get('escalations', 0.0):.2f}/sec",
                )

                # Show info if no data
                if all(v == 0.0 for v in results.values()):
                    st.info(
                        "No guardrail activity yet. Metrics will appear once the guardrails service processes requests."
                    )

            except Exception as e:
                logger.warning(
                    "monitoring.guardrail_query_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                st.info(
                    "Guardrail metrics will appear once services receive requests. Check Grafana dashboards for detailed metrics."
                )

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
        # Query operational metrics from Prometheus
        with httpx.Client(timeout=5.0) as client:
            try:
                # Get active HTTP requests (in-flight)
                active_requests_query = (
                    "sum(audio_orchestrator_http_server_active_requests)"
                )

                # Get total services reporting health
                healthy_services_query = (
                    "count(audio_orchestrator_service_health_status >= 1)"
                )
                total_services_query = "count(audio_orchestrator_service_health_status)"

                # Get request rate by service (for distribution)
                request_dist_query = "sum by (exported_job) (rate(audio_orchestrator_http_server_duration_milliseconds_count[5m]))"

                queries = {
                    "active_requests": active_requests_query,
                    "healthy_services": healthy_services_query,
                    "total_services": total_services_query,
                    "request_dist": request_dist_query,
                }

                results = {}
                for key, query in queries.items():
                    try:
                        response = client.get(
                            f"{PROMETHEUS_URL}/api/v1/query",
                            params={"query": query},
                        )
                        if response.status_code == 200:
                            result = response.json()
                            if result.get("status") == "success":
                                if key == "request_dist":
                                    # Store full distribution results
                                    results[key] = result.get("data", {}).get(
                                        "result", []
                                    )
                                elif result.get("data", {}).get("result"):
                                    value = result["data"]["result"][0].get(
                                        "value", [None, "0"]
                                    )[1]
                                    results[key] = (
                                        float(value) if value and value != "0" else 0.0
                                    )
                                else:
                                    results[key] = 0.0
                            elif key != "request_dist":
                                results[key] = 0.0
                        elif key != "request_dist":
                            results[key] = 0.0
                    except Exception:
                        if key != "request_dist":
                            results[key] = 0.0

                # Display service availability
                st.subheader("Service Availability")
                col1, col2 = st.columns(2)
                with col1:
                    healthy = int(results.get("healthy_services", 0))
                    total = int(results.get("total_services", 0))
                    if total > 0:
                        health_percentage = (healthy / total) * 100
                        st.metric(
                            "Healthy Services",
                            f"{healthy}/{total}",
                            f"{health_percentage:.1f}%",
                        )
                    else:
                        st.metric("Healthy Services", "N/A")
                with col2:
                    active = int(results.get("active_requests", 0))
                    st.metric("Active HTTP Requests", active)

                # Display request distribution across services
                st.subheader("Request Distribution by Service")
                if results.get("request_dist"):
                    request_data = results["request_dist"]
                    if request_data:
                        # Create a simple visualization of request rates
                        service_rates = {}
                        for item in request_data:
                            exported_job = item.get("metric", {}).get(
                                "exported_job", "unknown"
                            )
                            # Extract service name from exported_job (format: audio-orchestrator/service-name)
                            service_name = (
                                exported_job.split("/")[-1]
                                if "/" in exported_job
                                else exported_job
                            )
                            value = item.get("value", [None, "0"])[1]
                            with suppress(ValueError, TypeError):
                                service_rates[service_name] = float(value)

                        if service_rates:
                            # Display as metrics
                            cols = st.columns(min(len(service_rates), 4))
                            for i, (service, rate) in enumerate(
                                sorted(
                                    service_rates.items(),
                                    key=lambda x: x[1],
                                    reverse=True,
                                )[:8]
                            ):
                                with cols[i % 4]:
                                    st.metric(service.title(), f"{rate:.2f} req/s")
                        else:
                            st.info("No request distribution data available yet.")
                    else:
                        st.info("No request distribution data available yet.")
                else:
                    st.info(
                        "Request distribution will appear once services receive requests."
                    )

                # Show info if no data
                if not any(results.values()) or (
                    results.get("total_services", 0) == 0
                    and not results.get("request_dist")
                ):
                    st.info(
                        "System metrics will appear as services start and process requests. "
                        "For detailed CPU and memory metrics, check Grafana dashboards or Docker stats."
                    )

            except Exception as e:
                logger.warning(
                    "monitoring.system_query_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                st.info(
                    "System metrics will appear once services are running. Check Grafana dashboards for detailed resource metrics."
                )

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
    global _observability_manager

    try:
        # Get observability manager (factory already setup observability)
        _observability_manager = get_observability_manager("monitoring")

        # HTTP metrics already available from app_factory via app.state.http_metrics
        # No service-specific metrics needed for monitoring service

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
    # Prevent uvicorn from resetting our logging configuration
    # We've already configured structured JSON logging in configure_logging()
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8502,
        log_config=None,  # Don't let uvicorn configure logging - we handle it ourselves
    )
