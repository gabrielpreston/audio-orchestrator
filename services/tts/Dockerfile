# Build stage using shared audio base image
FROM discord-voice-lab/python-audio:latest as builder

WORKDIR /app

# Copy service-specific requirements
COPY services/tts/requirements.txt /app/services/tts/requirements.txt

# Install Python dependencies
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /app/services/tts/requirements.txt

# Runtime stage using shared audio base image
FROM discord-voice-lab/python-audio:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/tts /app/services/tts

# Create models directory (Piper models will be mounted via volume)
RUN mkdir -p /app/models

EXPOSE 7000

ENV HOST=0.0.0.0
ENV PORT=7000

CMD ["uvicorn", "services.tts.app:app", "--host", "0.0.0.0", "--port", "7000"]