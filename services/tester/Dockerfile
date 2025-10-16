FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential=* \
        ca-certificates=* \
        cmake=* \
        ffmpeg=* \
        git=* \
        libavcodec-dev=* \
        libavdevice-dev=* \
        libavfilter-dev=* \
        libavformat-dev=* \
        libavutil-dev=* \
        libcurl4-openssl-dev=* \
        libffi-dev=* \
        libgomp1=* \
        libopenblas-dev=* \
        libopus0=* \
        libsndfile1=* \
        libsodium-dev=* \
        ninja-build=* \
        pkg-config=* \
        python3-dev=* \
        wget=* && \
    rm -rf /var/lib/apt/lists/*

# Copy all requirements files needed for testing to workspace
COPY requirements-test.txt /workspace/requirements-test.txt
COPY requirements-base.txt /workspace/requirements-base.txt
COPY requirements-dev.txt /workspace/requirements-dev.txt
COPY services/discord/requirements.txt /workspace/services/discord/requirements.txt
COPY services/stt/requirements.txt /workspace/services/stt/requirements.txt
COPY services/llm/requirements.txt /workspace/services/llm/requirements.txt
COPY services/orchestrator/requirements.txt /workspace/services/orchestrator/requirements.txt
COPY services/tts/requirements.txt /workspace/services/tts/requirements.txt
COPY services/linter/requirements.txt /workspace/services/linter/requirements.txt
COPY services/tester/requirements.txt /workspace/requirements.txt
RUN python -m pip install --upgrade pip==24.0 && \
    pip install -r /workspace/requirements.txt

COPY services/tester/run-tests.sh /usr/local/bin/run-tests.sh
RUN chmod +x /usr/local/bin/run-tests.sh

WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/run-tests.sh"]
