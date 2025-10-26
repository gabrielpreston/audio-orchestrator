# Build stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy service-specific requirements
COPY services/guardrails/requirements.txt /app/services/guardrails/requirements.txt
COPY services/requirements-base.txt /app/services/requirements-base.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/guardrails/requirements.txt

# Runtime stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create models directory and set environment variables in single layer
RUN mkdir -p /app/models && \
    echo "Guardrails environment configured"

# Set Python environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENV PORT=9300
ENV TOXICITY_MODEL=unitary/toxic-bert
ENV ENABLE_PII_DETECTION=true

# Copy application code LAST (changes most frequently)
COPY services/common /app/services/common
COPY services/guardrails /app/services/guardrails
COPY scripts/health_check.py /app/scripts/health_check.py

CMD ["uvicorn", "services.guardrails.app:app", "--host", "0.0.0.0", "--port", "9300"]
