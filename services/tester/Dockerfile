FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        ninja-build \
        ffmpeg \
        pkg-config \
        libffi-dev \
        python3-dev \
        libsodium-dev && \
    rm -rf /var/lib/apt/lists/*

COPY services/tester/requirements.txt /tmp/requirements.txt
COPY services/discord/requirements.txt /tmp/discord-requirements.txt
COPY services/llm/requirements.txt /tmp/llm-requirements.txt
COPY services/stt/requirements.txt /tmp/stt-requirements.txt
RUN python -m pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt && \
    pip install -r /tmp/discord-requirements.txt && \
    pip install -r /tmp/llm-requirements.txt && \
    pip install -r /tmp/stt-requirements.txt

COPY services/tester/run-tests.sh /usr/local/bin/run-tests.sh
RUN chmod +x /usr/local/bin/run-tests.sh

WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/run-tests.sh"]
