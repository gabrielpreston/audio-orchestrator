# Build stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy service-specific requirements and constraints
COPY services/guardrails/requirements.txt /app/services/guardrails/requirements.txt
COPY constraints.txt /app/constraints.txt
# Install Python dependencies with aggressive cleanup for GitHub Actions
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/guardrails/requirements.txt -c /app/constraints.txt && \
    pip cache purge && \
    find /usr/local/lib/python3.11/site-packages -name "*.pyc" -delete && \
    find /usr/local/lib/python3.11/site-packages -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11/site-packages -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11/site-packages -name "test" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11/site-packages -name "*.so" -size +10M -delete 2>/dev/null || true

# Runtime stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create models directory and clean up unnecessary files
RUN mkdir -p /app/models && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
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

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=6 \
    CMD python /app/scripts/health_check.py http://localhost:9300/health/ready --ci

CMD ["uvicorn", "services.guardrails.app:app", "--host", "0.0.0.0", "--port", "9300"]
