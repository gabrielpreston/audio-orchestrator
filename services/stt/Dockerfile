# Build stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Install OpenBLAS development packages for building numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas-dev \
    libopenblas-pthread-dev \
    gfortran \
    && rm -rf /var/lib/apt/lists/*

# Copy service-specific requirements
COPY services/stt/requirements.txt /app/services/stt/requirements.txt
COPY services/requirements-base.txt /app/services/requirements-base.txt

# Install Python deps, rebuilding numpy from source against system OpenBLAS
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/requirements-base.txt && \
    pip uninstall -y numpy || true && \
    pip install --no-cache-dir --no-binary=numpy "numpy>=1.24,<2.0" && \
    pip install --no-cache-dir -r /app/services/stt/requirements.txt && \
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

# Install OpenBLAS runtime libraries for numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas0 \
    libopenblas0-pthread \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create models directory and clean up unnecessary files
RUN --mount=type=cache,target=/var/cache/apt \
    mkdir -p /app/models && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
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
