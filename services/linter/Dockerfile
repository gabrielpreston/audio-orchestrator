FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PATH="/usr/local/go/bin:${PATH}" \
    GOBIN=/usr/local/bin

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        gnupg \
        make \
        nodejs \
        npm \
        golang-go && \
    rm -rf /var/lib/apt/lists/*

COPY services/linter/requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt

RUN npm install -g markdownlint-cli

RUN curl -sSL https://github.com/hadolint/hadolint/releases/latest/download/hadolint-Linux-x86_64 \
    -o /usr/local/bin/hadolint && \
    chmod +x /usr/local/bin/hadolint

RUN go install github.com/mrtazz/checkmake/cmd/checkmake@latest

COPY services/linter/run-lint.sh /usr/local/bin/run-lint.sh
RUN chmod +x /usr/local/bin/run-lint.sh

WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/run-lint.sh"]
