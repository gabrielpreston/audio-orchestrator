# Audio Processor Service Dockerfile
# Multi-stage build with shared base image for optimal caching

FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Install OpenBLAS development packages for building numpy/scipy
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas-dev \
    libopenblas-pthread-dev \
    gfortran \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements FIRST for better caching
COPY services/audio/requirements.txt /app/services/audio/requirements.txt
COPY services/requirements-base.txt /app/services/requirements-base.txt

# Install Python dependencies, rebuilding numpy/scipy from source against system OpenBLAS
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/requirements-base.txt && \
    pip uninstall -y numpy scipy || true && \
    pip install --no-cache-dir --no-binary=numpy,scipy \
        "numpy>=1.24.0,<2.0" \
        "scipy>=1.11.0,<2.0" && \
    pip install --no-cache-dir -r /app/services/audio/requirements.txt && \
    pip cache purge && \
    find /usr/local/lib/python3.11/site-packages -name "*.pyc" -delete && \
    find /usr/local/lib/python3.11/site-packages -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11/site-packages -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11/site-packages -name "test" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11/site-packages -name "*.so" -size +10M -delete 2>/dev/null || true

# Runtime stage
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Install OpenBLAS runtime libraries for numpy/scipy
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas0 \
    libopenblas0-pthread \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy application code LAST (changes most frequently)
COPY services/audio /app/services/audio
COPY services/common /app/services/common

# Copy configuration
COPY services/audio/config /app/config

# Copy health check script
COPY scripts/health_check.py /app/scripts/health_check.py

# Create models directory and clean up unnecessary files
RUN mkdir -p /app/models && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Set environment variables
ENV PYTHONPATH=/app
ENV AUDIO_PROCESSOR_SERVICE_PORT=9100
ENV AUDIO_PROCESSOR_SERVICE_HOST=0.0.0.0


# Expose port
EXPOSE 9100

# Run the service
CMD ["python", "services/audio/app.py"]
