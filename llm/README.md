# LLM service (llama.cpp GGUF runner)

This folder contains a minimal Dockerized service that runs a GGUF/ggml model via `llama.cpp` and exposes a simple HTTP API.

How it works
- The image builds `llama.cpp` from source and installs a small Flask app.
- Place a GGUF model file (for example `llama2-7b.gguf`) into `./llm/models/` on the host. The container mounts this as `/app/models`.
- The service exposes `/generate` which accepts JSON: {"prompt": "...", "max_tokens": 128}

Environment
- You may override the default model path by setting the `MODEL_PATH` environment variable when running the container. Example: `MODEL_PATH=/app/models/custom.gguf`.

Endpoints
- `/models` - lists GGUF models found in `/app/models`.
- `/generate` - generation endpoint as above.

Notes & recommendations
- On CPU-only systems (Synology or low-power desktop), use a quantized GGUF (Q4/Q5) of Llama 2 7B.
- For best quality, perform GPTQ quantization on a GPU-capable machine and store the resulting GGUF in `./llm/models/`.
- The current implementation shells out to `llama.cpp`'s `main` binary. For production you may replace with a C API wrapper or a more robust server.

Running locally (docker-compose)

1. Put your model in `./llm/models/llama2-7b.gguf`.
2. Build and run with the project's docker-compose: `docker compose up --build llm`
