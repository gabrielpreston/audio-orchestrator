# Audio Processor Service Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY services/audio-processor/requirements.txt .
COPY services/requirements-base.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY services/audio-processor/ .
COPY services/common/ ./services/common/

# Copy configuration
COPY services/audio-processor/config/ ./config/

# Create models directory
RUN mkdir -p /app/models

# Set environment variables
ENV PYTHONPATH=/app
ENV AUDIO_PROCESSOR_SERVICE_PORT=9100
ENV AUDIO_PROCESSOR_SERVICE_HOST=0.0.0.0

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:9100/health/ready || exit 1

# Expose port
EXPOSE 9100

# Run the service
CMD ["python", "app.py"]
