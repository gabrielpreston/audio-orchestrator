FROM python:3.11-slim
WORKDIR /app

# Install build tools for llama.cpp and runtime deps
RUN apt-get update && \
	apt-get install -y --no-install-recommends \
		build-essential cmake git pkg-config libgomp1 libopenblas-dev wget ca-certificates libcurl4-openssl-dev && \
	rm -rf /var/lib/apt/lists/*

COPY services/llm/requirements.txt /app/services/llm/requirements.txt
RUN pip install --no-cache-dir -r /app/services/llm/requirements.txt

# Clone and build llama.cpp so the container can run gguf models directly.
RUN git clone --depth 1 https://github.com/ggerganov/llama.cpp.git /app/llama.cpp && \
	cd /app/llama.cpp && \
	mkdir -p build && cd build && \
	cmake .. && \
	cmake --build . -- -j"$(nproc)"

COPY services /app/services

# Default model path and CLI
ENV PORT=8000
ENV LLAMA_BIN=/app/llama.cpp/main
ENV LLAMA_MODEL_PATH=/app/models/llama2-7b.gguf

CMD ["uvicorn", "services.llm.app:app", "--host", "0.0.0.0", "--port", "8000"]
