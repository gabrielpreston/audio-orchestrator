FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies required for audio processing and some wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libsndfile1 \
    pkg-config \
    libavdevice-dev libavformat-dev libavfilter-dev libavcodec-dev libavutil-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/stt/requirements.txt /app/services/stt/requirements.txt

# Install Python deps from the copied requirements
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install -r /app/services/stt/requirements.txt

COPY services/common /app/services/common
COPY services/stt /app/services/stt

EXPOSE 9000

ENV HOST=0.0.0.0
ENV PORT=9000

CMD ["uvicorn", "services.stt.app:app", "--host", "0.0.0.0", "--port", "9000"]
