# Build stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy requirements files
COPY services/requirements-base.txt /app/services/requirements-base.txt
COPY services/orchestrator/requirements.txt /app/services/orchestrator/requirements.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/orchestrator/requirements.txt

# Runtime stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/orchestrator /app/services/orchestrator
COPY scripts/health_check.py /app/scripts/health_check.py

# Docker healthcheck via HTTP readiness
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=6 \
    CMD python /app/scripts/health_check.py http://localhost:8200/health/ready --ci

# Set Python environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENV PORT=8200
ENV LLM_BASE_URL=http://flan:8100
ENV GUARDRAILS_BASE_URL=http://guardrails:9300

CMD ["python", "-m", "services.orchestrator.main"]
