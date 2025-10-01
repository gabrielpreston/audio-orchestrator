#!/usr/bin/env bash
set -euo pipefail

# convert_llama2_to_gguf.sh
# Helper to download Llama 2 checkpoint from Hugging Face (after accepting license),
# then provide step-by-step commands to perform GPTQ quantization on GPU and
# convert to GGUF for CPU serving with llama.cpp.
#
# IMPORTANT: You must accept Meta's Llama 2 license on Hugging Face before downloading.
# License URL: https://ai.meta.com/resources/models-and-libraries/llama-downloads/
# Hugging Face model hub: https://huggingface.co/meta-llama

HF_REPO="meta-llama/Llama-2-7b-chat-hf"
OUT_DIR="./llm/models-src"
GGUF_OUT_DIR="./llm/models"

mkdir -p "$OUT_DIR"
mkdir -p "$GGUF_OUT_DIR"

echo "This script will not automatically run GPTQ quantization (requires CUDA + PyTorch).
It will download the HF repo snapshot to '$OUT_DIR' and print the recommended commands to run on a GPU.

Make sure you have logged in with: 
  huggingface-cli login

If you have an HF token set as HUGGINGFACE_TOKEN env var, the script will use it via huggingface_hub.
"

python3 - <<PY
from huggingface_hub import snapshot_download
import os
repo = os.environ.get('HF_REPO', '${HF_REPO}')
token = os.environ.get('HUGGINGFACE_TOKEN', None)
print('Downloading', repo, 'to', '${OUT_DIR}')
path = snapshot_download(repo, local_dir='${OUT_DIR}', token=token)
print('Downloaded to:', path)
PY

cat <<'EOF'

=== NEXT STEPS (run on GPU machine, your RTX 4070 Ti is suitable) ===

# 1) Create a Python venv and install dependencies (example uses pip and PyTorch + CUDA 12.1/13.0 as appropriate)
python3 -m venv ~/gptq-venv && source ~/gptq-venv/bin/activate
pip install --upgrade pip

# Install PyTorch with CUDA (pick correct CUDA for your driver; example for CUDA 13.0):
pip install torch --index-url https://download.pytorch.org/whl/cu118  # adjust for your CUDA

# Install AutoGPTQ (or GPTQ-for-LLM) and transformers and accelerate
pip install transformers accelerate bitsandbytes peft
# AutoGPTQ example (community project) - install per its README
pip install auto-gptq

# 2) Run GPTQ quantization (example placeholder command; follow your chosen GPTQ tool's docs)
# Example using AutoGPTQ (pseudocode):
auto-gptq --model-dir ./llm/models-src --model-name Llama-2-7b-chat-hf --wbits 4 --groupsize 128 --outfile ./llm/models/llama2-7b-4bit-GPTQ

# 3) Convert the quantized model to GGUF using llama.cpp conversion tools (in your llama.cpp repo):
# From the llama.cpp repo run the appropriate conversion script (example):
python3 ./llama.cpp/scripts/gptq_to_gguf.py --input ./llm/models/llama2-7b-4bit-GPTQ --outfile ./llm/models/llama2-7b.gguf

# 4) Ensure the resulting GGUF is readable by the container and restart the llm service
chmod a+r ./llm/models/llama2-7b.gguf
docker-compose restart llm

EOF

echo "Done. Review the printed next steps above and run them on the GPU machine."
