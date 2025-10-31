"""Streamlit entry point for monitoring dashboard."""

from services.monitoring.app import create_monitoring_dashboard

if __name__ == "__main__":
    create_monitoring_dashboard()
