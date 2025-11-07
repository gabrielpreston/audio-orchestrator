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

# Copy requirements files
COPY services/requirements-base.txt /app/services/requirements-base.txt
COPY services/stt/requirements.txt /app/services/stt/requirements.txt

# Install Python deps, rebuilding numpy from source against system OpenBLAS
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/stt/requirements.txt && \
    pip uninstall -y numpy || true && \
    pip install --no-cache-dir --no-binary=numpy "numpy>=1.24,<2.0" && \
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
# Install CUDNN libraries required for faster-whisper/CTranslate2 CUDA support
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas0 \
    libopenblas0-pthread \
    && rm -rf /var/lib/apt/lists/*

# Install CUDNN for CUDA 12.1 (required by CTranslate2 for CUDA inference)
# CTranslate2 4.5.0+ requires cuDNN 9.2+ (looking for libcudnn_ops.so.9.x)
# Download and install cuDNN 9.x from NVIDIA redistributable repository (no login required)
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    tar \
    xz-utils \
    && mkdir -p /tmp/cudnn /usr/local/cuda/lib64 /usr/local/cuda/include \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/cudnn

RUN wget -q --progress=dot:giga \
        https://developer.download.nvidia.com/compute/cudnn/redist/cudnn/linux-x86_64/cudnn-linux-x86_64-9.2.1.26_cuda12-archive.tar.xz \
        -O cudnn.tar.xz \
    && tar -xf cudnn.tar.xz \
    && cp -P cudnn-linux-x86_64-9.2.1.26_cuda12-archive/lib/libcudnn* /usr/local/cuda/lib64/ \
    && cp -r cudnn-linux-x86_64-9.2.1.26_cuda12-archive/include/* /usr/local/cuda/include/ \
    && cp -P /usr/local/cuda/lib64/libcudnn* /usr/lib/x86_64-linux-gnu/ \
    && ldconfig \
    && rm -rf /tmp/cudnn \
    && echo "cuDNN installation complete - verifying..." \
    && ldconfig -p | grep cudnn || echo "Warning: cuDNN libraries not found in ldconfig cache"

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set LD_LIBRARY_PATH to include CUDA libraries
# Include PyTorch's bundled CUDNN location for CTranslate2 compatibility
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib:${LD_LIBRARY_PATH}

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

# Create user with matching UID/GID for consistency (torch.compile() compatibility pattern)
# This fixes getpwuid() errors in Docker containers
ARG PUID=1000
ARG PGID=1000

RUN groupadd -g ${PGID} appuser 2>/dev/null || true && \
    useradd -l -u ${PUID} -g ${PGID} -ms /bin/bash appuser 2>/dev/null || true && \
    chown -R ${PUID}:${PGID} /app 2>/dev/null || true

USER appuser

# Extended start-period to allow for model loading and pre-warming
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=6 \
    CMD python /app/scripts/health_check.py http://localhost:9000/health/ready --ci

EXPOSE 9000

ENV HOST=0.0.0.0
ENV PORT=9000

CMD ["uvicorn", "services.stt.app:app", "--host", "0.0.0.0", "--port", "9000"]
