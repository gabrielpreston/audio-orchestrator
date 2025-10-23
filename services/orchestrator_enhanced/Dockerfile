# Build stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy service-specific requirements
COPY services/orchestrator_enhanced/requirements.txt /app/services/orchestrator_enhanced/requirements.txt
COPY services/requirements-base.txt /app/services/requirements-base.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/orchestrator_enhanced/requirements.txt

# Runtime stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/orchestrator_enhanced /app/services/orchestrator_enhanced
COPY scripts/health_check.py /app/scripts/health_check.py

ENV PORT=8200
ENV LLM_PRIMARY_URL=http://llm-flan:8100
ENV LLM_FALLBACK_URL=http://llm:8000
ENV GUARDRAILS_URL=http://guardrails:9300

CMD ["uvicorn", "services.orchestrator_enhanced.app:app", "--host", "0.0.0.0", "--port", "8200"]
