#!/usr/bin/env bash
set -euo pipefail

# optimum_quantize_and_convert.sh
# Quantize a Hugging Face Llama 2 checkpoint using Hugging Face Optimum GPTQ API
# and convert the quantized output to GGUF for llama.cpp.
#
# Usage: run from repository root. Ensure you have run:
#   source ./.venv-gptq/bin/activate
# and that ./llm/models-src contains the downloaded HF snapshot (see convert_llama2_to_gguf.sh)

MODEL_SRC_DIR="./llm/models-src/meta-llama--Llama-2-7b-chat-hf"
QUANT_OUT_DIR="./llm/models/llama2-7b-4bit-optimum"
GGUF_OUT="./llm/models/llama2-7b.gguf"
LLAMA_CPP_DIR="./llama.cpp"

mkdir -p "$QUANT_OUT_DIR"

echo "Starting Optimum GPTQ quantization"
python3 - <<PY
from optimum.gptq import GPTQQuantizer
from transformers import AutoConfig
import os

src = os.getenv('MODEL_SRC_DIR', '${MODEL_SRC_DIR}')
out = os.getenv('QUANT_OUT_DIR', '${QUANT_OUT_DIR}')

print('Source:', src)
print('Output:', out)

cfg = AutoConfig.from_pretrained(src)
print('Loaded config')

q = GPTQQuantizer.from_pretrained(src)
print('Created GPTQQuantizer')

# Example quantization — these parameters are a reasonable starting point.
q.quantize(bits=4, group_size=128, out_folder=out, max_memory=None)
print('Quantization finished, saved to', out)
PY

echo "Converting GPTQ output to GGUF using llama.cpp script"
if [ ! -d "$LLAMA_CPP_DIR" ]; then
  echo "llama.cpp not found at $LLAMA_CPP_DIR. Clone it first: git clone https://github.com/ggerganov/llama.cpp.git $LLAMA_CPP_DIR"
  exit 1
fi

python3 "$LLAMA_CPP_DIR/scripts/gptq_to_gguf.py" --input "$QUANT_OUT_DIR" --outfile "$GGUF_OUT"

chmod a+r "$GGUF_OUT" || true
echo "GGUF written to $GGUF_OUT"
echo "Restart the llm container: docker-compose restart llm"
