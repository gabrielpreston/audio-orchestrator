# Build stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy service-specific requirements
COPY services/stt/requirements.txt /app/services/stt/requirements.txt
COPY services/requirements-base.txt /app/services/requirements-base.txt

# Install Python deps from the copied requirements
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/stt/requirements.txt

# Runtime stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create models directory and set environment variables in single layer
RUN --mount=type=cache,target=/var/cache/apt \
    mkdir -p /app/models && \
    echo "Python environment configured"

# Set Python environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application code LAST (changes most frequently)
COPY services/common /app/services/common
COPY services/stt /app/services/stt
COPY scripts/health_check.py /app/scripts/health_check.py

EXPOSE 9000

ENV HOST=0.0.0.0
ENV PORT=9000

CMD ["uvicorn", "services.stt.app:app", "--host", "0.0.0.0", "--port", "9000"]
