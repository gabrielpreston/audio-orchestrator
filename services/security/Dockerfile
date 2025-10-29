FROM ghcr.io/gabrielpreston/python-web:latest

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates=* \
        curl=* \
        git=* && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and constraints and install with pinned versions
COPY services/security/requirements.txt /workspace/services/security/requirements.txt
COPY constraints.txt /workspace/constraints.txt
RUN python -m pip install --upgrade pip==24.0 && \
    pip install -r /workspace/services/security/requirements.txt -c /workspace/constraints.txt

COPY services/security/run-security.sh /usr/local/bin/run-security.sh
RUN chmod +x /usr/local/bin/run-security.sh

WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/run-security.sh"]
