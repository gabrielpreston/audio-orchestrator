#!/bin/bash
# Download required models to ./services/models/ subdirectories
set -euo pipefail

# Resolve script directory for reliable path handling
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

mkdir -p ./services/models/tts ./services/models/stt

echo "Downloading TTS model (en_US-amy-medium)..."
if [ ! -f "./services/models/tts/en_US-amy-medium.onnx" ]; then
	wget -O ./services/models/tts/en_US-amy-medium.onnx \
	"https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx" || \
	echo "Failed to download TTS model. You may need to download it manually."
else
	echo "TTS model already exists, skipping download."
fi

if [ ! -f "./services/models/tts/en_US-amy-medium.onnx.json" ]; then
	wget -O ./services/models/tts/en_US-amy-medium.onnx.json \
	"https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx.json" || \
	echo "Failed to download TTS model config. You may need to download it manually."
else
	echo "TTS model config already exists, skipping download."
fi

echo "Downloading STT model (faster-whisper medium.en)..."
if [ ! -d "./services/models/stt/medium.en" ]; then
	mkdir -p ./services/models/stt/medium.en
	wget -O ./services/models/stt/medium.en/config.json \
	"https://huggingface.co/Systran/faster-whisper-medium.en/resolve/main/config.json" || \
	echo "Failed to download STT model config."
	wget -O ./services/models/stt/medium.en/model.bin \
	"https://huggingface.co/Systran/faster-whisper-medium.en/resolve/main/model.bin" || \
	echo "Failed to download STT model weights."
	wget -O ./services/models/stt/medium.en/tokenizer.json \
	"https://huggingface.co/Systran/faster-whisper-medium.en/resolve/main/tokenizer.json" || \
	echo "Failed to download STT tokenizer."
	wget -O ./services/models/stt/medium.en/vocabulary.txt \
	"https://huggingface.co/Systran/faster-whisper-medium.en/resolve/main/vocabulary.txt" || \
	echo "Failed to download STT vocabulary."
else
	echo "STT model already exists, skipping download."
fi

echo "Downloading FLAN-T5 model (flan-t5-large)..."
if [ ! -d "./services/models/flan-t5" ]; then
	mkdir -p ./services/models/flan-t5
	python3 "$SCRIPT_DIR/download_flan_t5.py" large || \
	echo "Failed to download FLAN-T5 model. You may need to download it manually."
else
	echo "FLAN-T5 model already exists, skipping download."
fi

echo "Model download complete"
echo "Models downloaded to:"
echo "  - TTS: ./services/models/tts/en_US-amy-medium.onnx"
echo "  - TTS: ./services/models/tts/en_US-amy-medium.onnx.json"
echo "  - STT: ./services/models/stt/medium.en/"
echo "  - FLAN-T5: ./services/models/flan-t5/"

