FROM python:3.11-slim

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    GO_VERSION=1.25.2 \
    PATH="/usr/local/go/bin:${PATH}" \
    GOBIN=/usr/local/bin

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates=* \
        curl=* \
        git=* \
        gnupg=* \
        make=* \
        nodejs=* \
        npm=* && \
    rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" \
    | tar -C /usr/local -xz

# Copy all requirements files needed for linting to workspace
COPY requirements-base.txt /workspace/requirements-base.txt
COPY requirements-dev.txt /workspace/requirements-dev.txt
COPY services/linter/requirements.txt /workspace/requirements.txt
RUN python -m pip install --upgrade pip==24.0 && \
    pip install -r /workspace/requirements.txt

# Pin markdownlint version
RUN npm install -g markdownlint-cli@0.39.0

# Pin hadolint version
RUN curl -sSL https://github.com/hadolint/hadolint/releases/download/v2.12.0/hadolint-Linux-x86_64 \
    -o /usr/local/bin/hadolint && \
    chmod +x /usr/local/bin/hadolint

# Pin checkmake version
RUN go install github.com/checkmake/checkmake/cmd/checkmake@latest

COPY services/linter/run-lint.sh /usr/local/bin/run-lint.sh
RUN chmod +x /usr/local/bin/run-lint.sh

WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/run-lint.sh"]
