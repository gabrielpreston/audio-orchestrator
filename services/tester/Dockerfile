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

COPY services/tester/requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip==24.0 && \
    pip install -r /tmp/requirements.txt

COPY services/tester/run-tests.sh /usr/local/bin/run-tests.sh
RUN chmod +x /usr/local/bin/run-tests.sh

WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/run-tests.sh"]
