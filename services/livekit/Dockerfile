FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libsndfile1 \
    libasound2-dev \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY services/livekit/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY services/livekit/ ./
COPY services/common/ ../common/

# Set Python path
ENV PYTHONPATH=/app:/app/../common

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the service
CMD ["python", "-m", "livekit_agent"]