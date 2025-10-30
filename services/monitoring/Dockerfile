# Build stage using shared web base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-web:latest AS builder

WORKDIR /app

# Copy service-specific requirements and constraints
COPY services/monitoring/requirements.txt /app/services/monitoring/requirements.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/monitoring/requirements.txt

# Runtime stage using shared web base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-web:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/monitoring /app/services/monitoring
COPY scripts/health_check.py /app/scripts/health_check.py

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=6 \
    CMD python /app/scripts/health_check.py http://localhost:8502/health/ready --ci

# Set Python environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV PROMETHEUS_URL=http://prometheus:9090


CMD ["python", "services/monitoring/app.py"]
