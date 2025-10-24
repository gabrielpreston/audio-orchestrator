"""
Monitoring Dashboard service for Audio Orchestrator.

Provides a Streamlit dashboard for monitoring system health,
performance metrics, and guardrail statistics.
"""

import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException

from services.common.health import HealthManager

# Import optional dependencies with error handling
try:
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
    import streamlit as st
    from prometheus_api_client import PrometheusConnect

    DASHBOARD_AVAILABLE = True
except ImportError:
    DASHBOARD_AVAILABLE = False
    pd = None
    px = None
    go = None
    st = None
    PrometheusConnect = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app for health checks
app = FastAPI(title="Monitoring Dashboard Service", version="1.0.0")

# Health manager
health_manager = HealthManager("monitoring-dashboard")

# Prometheus connection
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
prom = (
    PrometheusConnect(url=PROMETHEUS_URL, disable_ssl=True)
    if DASHBOARD_AVAILABLE
    else None
)


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
        # Query service health metrics
        health_query = 'service_health_status{component="overall"}'
        health_data = prom.custom_query(health_query)

        if health_data:
            overall_health = health_data[0]["value"][1]
            st.metric("Overall Health", f"{overall_health}")
        else:
            st.warning("No health data available")

        # Individual service health
        services = [
            "discord",
            "stt",
            "llm-flan",
            "audio-preprocessor",
            "tts-bark",
            "orchestrator-enhanced",
            "guardrails",
        ]

        cols = st.columns(3)
        for i, service in enumerate(services):
            with cols[i % 3]:
                try:
                    service_query = f'service_health_status{{service="{service}"}}'
                    service_data = prom.custom_query(service_query)
                    if service_data:
                        status = service_data[0]["value"][1]
                        st.metric(f"{service.title()}", status, delta=None)
                    else:
                        st.metric(f"{service.title()}", "Unknown")
                except Exception as e:
                    st.metric(f"{service.title()}", "Error")
                    logger.error(
                        f"Failed to get health for {service}", extra={"error": str(e)}
                    )

    except Exception as e:
        st.error(f"Failed to fetch health data: {str(e)}")
        logger.error("Health data fetch failed", extra={"error": str(e)})


def display_performance_metrics(time_range: str) -> None:
    """Display performance metrics."""
    st.header("Performance Metrics")

    try:
        # Latency metrics
        st.subheader("Latency Distribution")

        # P95 Latency
        latency_query = (
            "histogram_quantile(0.95, rate(request_duration_seconds_bucket[5m]))"
        )
        latency_data = prom.custom_query_range(
            latency_query, start_time=f"now-{time_range}", end_time="now", step="1m"
        )

        if latency_data:
            latency_df = pd.DataFrame(
                latency_data[0]["values"], columns=["timestamp", "value"]
            )
            latency_df["timestamp"] = pd.to_datetime(latency_df["timestamp"], unit="s")
            latency_df["value"] = latency_df["value"].astype(float)

            fig = px.line(
                latency_df,
                x="timestamp",
                y="value",
                title="P95 Latency Over Time",
                labels={"value": "Latency (seconds)", "timestamp": "Time"},
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No latency data available")

        # Throughput metrics
        st.subheader("Request Throughput")
        throughput_query = "rate(http_requests_total[5m])"
        throughput_data = prom.custom_query_range(
            throughput_query, start_time=f"now-{time_range}", end_time="now", step="1m"
        )

        if throughput_data:
            # Create a combined chart for different services
            fig = go.Figure()
            for service_data in throughput_data:
                service_name = service_data["metric"].get("service", "unknown")
                throughput_df = pd.DataFrame(
                    service_data["values"], columns=["timestamp", "value"]
                )
                throughput_df["timestamp"] = pd.to_datetime(
                    throughput_df["timestamp"], unit="s"
                )
                throughput_df["value"] = throughput_df["value"].astype(float)

                fig.add_trace(
                    go.Scatter(
                        x=throughput_df["timestamp"],
                        y=throughput_df["value"],
                        mode="lines",
                        name=service_name,
                        line={"width": 2},
                    )
                )

            fig.update_layout(
                title="Request Throughput by Service",
                xaxis_title="Time",
                yaxis_title="Requests per second",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No throughput data available")

    except Exception as e:
        st.error(f"Failed to fetch performance data: {str(e)}")
        logger.error("Performance data fetch failed", extra={"error": str(e)})


def display_guardrail_metrics(time_range: str) -> None:
    """Display guardrail metrics."""
    st.header("Guardrail Statistics")

    try:
        # Guardrail blocks
        st.subheader("Blocked Requests")
        blocks_query = "rate(guardrail_blocks_total[5m])"
        blocks_data = prom.custom_query_range(
            blocks_query, start_time=f"now-{time_range}", end_time="now", step="1m"
        )

        if blocks_data:
            # Create pie chart for block reasons
            block_reasons: dict[str, float] = {}
            for data_point in blocks_data:
                reason = data_point["metric"].get("reason", "unknown")
                value = (
                    float(data_point["values"][-1][1]) if data_point["values"] else 0
                )
                block_reasons[reason] = block_reasons.get(reason, 0) + value

            if block_reasons:
                fig = px.pie(
                    values=list(block_reasons.values()),
                    names=list(block_reasons.keys()),
                    title="Blocked Requests by Reason",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No blocked requests in the selected time range")
        else:
            st.warning("No guardrail data available")

        # Safety metrics
        st.subheader("Safety Metrics")
        col1, col2, col3 = st.columns(3)

        with col1:
            try:
                toxicity_query = "rate(guardrail_toxicity_blocks_total[5m])"
                toxicity_data = prom.custom_query(toxicity_query)
                if toxicity_data:
                    toxicity_rate = toxicity_data[0]["value"][1]
                    st.metric("Toxicity Blocks", f"{float(toxicity_rate):.2f}/min")
                else:
                    st.metric("Toxicity Blocks", "0/min")
            except Exception:
                st.metric("Toxicity Blocks", "N/A")

        with col2:
            try:
                pii_query = "rate(guardrail_pii_blocks_total[5m])"
                pii_data = prom.custom_query(pii_query)
                if pii_data:
                    pii_rate = pii_data[0]["value"][1]
                    st.metric("PII Blocks", f"{float(pii_rate):.2f}/min")
                else:
                    st.metric("PII Blocks", "0/min")
            except Exception:
                st.metric("PII Blocks", "N/A")

        with col3:
            try:
                injection_query = "rate(guardrail_injection_blocks_total[5m])"
                injection_data = prom.custom_query(injection_query)
                if injection_data:
                    injection_rate = injection_data[0]["value"][1]
                    st.metric("Injection Blocks", f"{float(injection_rate):.2f}/min")
                else:
                    st.metric("Injection Blocks", "0/min")
            except Exception:
                st.metric("Injection Blocks", "N/A")

    except Exception as e:
        st.error(f"Failed to fetch guardrail data: {str(e)}")
        logger.error("Guardrail data fetch failed", extra={"error": str(e)})


def display_system_metrics(time_range: str) -> None:
    """Display system resource metrics."""
    st.header("System Resource Metrics")

    try:
        # Memory usage
        st.subheader("Memory Usage")
        memory_query = (
            "container_memory_usage_bytes / container_spec_memory_limit_bytes * 100"
        )
        memory_data = prom.custom_query_range(
            memory_query, start_time=f"now-{time_range}", end_time="now", step="1m"
        )

        if memory_data:
            fig = go.Figure()
            for service_data in memory_data:
                service_name = service_data["metric"].get("name", "unknown")
                memory_df = pd.DataFrame(
                    service_data["values"], columns=["timestamp", "value"]
                )
                memory_df["timestamp"] = pd.to_datetime(
                    memory_df["timestamp"], unit="s"
                )
                memory_df["value"] = memory_df["value"].astype(float)

                fig.add_trace(
                    go.Scatter(
                        x=memory_df["timestamp"],
                        y=memory_df["value"],
                        mode="lines",
                        name=service_name,
                        line={"width": 2},
                    )
                )

            fig.update_layout(
                title="Memory Usage by Service",
                xaxis_title="Time",
                yaxis_title="Memory Usage (%)",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No memory data available")

        # CPU usage
        st.subheader("CPU Usage")
        cpu_query = "rate(container_cpu_usage_seconds_total[5m]) * 100"
        cpu_data = prom.custom_query_range(
            cpu_query, start_time=f"now-{time_range}", end_time="now", step="1m"
        )

        if cpu_data:
            fig = go.Figure()
            for service_data in cpu_data:
                service_name = service_data["metric"].get("name", "unknown")
                cpu_df = pd.DataFrame(
                    service_data["values"], columns=["timestamp", "value"]
                )
                cpu_df["timestamp"] = pd.to_datetime(cpu_df["timestamp"], unit="s")
                cpu_df["value"] = cpu_df["value"].astype(float)

                fig.add_trace(
                    go.Scatter(
                        x=cpu_df["timestamp"],
                        y=cpu_df["value"],
                        mode="lines",
                        name=service_name,
                        line={"width": 2},
                    )
                )

            fig.update_layout(
                title="CPU Usage by Service",
                xaxis_title="Time",
                yaxis_title="CPU Usage (%)",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No CPU data available")

    except Exception as e:
        st.error(f"Failed to fetch system metrics: {str(e)}")
        logger.error("System metrics fetch failed", extra={"error": str(e)})


@app.get("/health/live")  # type: ignore[misc]
async def health_live() -> dict[str, str]:
    """Liveness check - always returns 200 if process is alive."""
    return {"status": "alive", "service": "monitoring-dashboard"}


@app.get("/health/ready")  # type: ignore[misc]
async def health_ready() -> dict[str, Any]:
    """Readiness check - basic functionality."""
    try:
        # Check Prometheus connection
        prometheus_healthy = False
        try:
            prom.get_metric_metadata()
            prometheus_healthy = True
        except Exception as e:
            logger.warning("Prometheus connection failed", extra={"error": str(e)})

        status = "ready" if prometheus_healthy else "degraded"

        return {
            "status": status,
            "service": "monitoring-dashboard",
            "prometheus_connected": prometheus_healthy,
        }

    except Exception as e:
        logger.error("Health check failed", extra={"error": str(e)})
        raise HTTPException(status_code=503, detail="Service not ready") from e


@app.on_event("startup")  # type: ignore[misc]
async def startup_event() -> None:
    """Service startup event handler."""
    logger.info("Monitoring dashboard service starting up")
    health_manager.mark_startup_complete()


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
