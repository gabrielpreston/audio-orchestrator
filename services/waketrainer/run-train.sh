#!/usr/bin/env bash
set -euo pipefail

# Wake Word Training Script
# Orchestrates three-stage training using openWakeWord training API

if [[ $# -gt 0 ]]; then
  exec "$@"
fi

# Validate CONFIG environment variable
if [[ -z "${CONFIG:-}" ]]; then
    echo "Error: CONFIG environment variable is required"
    echo "Usage: CONFIG=path/to/config.yaml make wake-train"
    exit 1
fi

# Resolve config path (workspace mount)
CONFIG_PATH="${CONFIG}"
if [[ ! "$CONFIG_PATH" = /* ]]; then
    # Relative path - assume it's relative to workspace root
    CONFIG_PATH="/workspace/$CONFIG_PATH"
fi

# Validate config file exists
if [[ ! -f "$CONFIG_PATH" ]]; then
    echo "Error: Config file not found: $CONFIG_PATH"
    exit 1
fi

# Locate train.py in openwakeword package
TRAIN_PY=$(python -c "import openwakeword; import os; print(os.path.join(os.path.dirname(openwakeword.__file__), 'train.py'))")

if [[ ! -f "$TRAIN_PY" ]]; then
    echo "Error: Could not locate openwakeword train.py"
    exit 1
fi

# Determine which stage to run (default: all stages)
STAGE="${STAGE:-all}"

# Check if overwrite flag should be passed (for regenerating features)
OVERWRITE="${OVERWRITE:-false}"

echo "=========================================="
echo "Wake Word Training Tool"
echo "=========================================="
echo "Config: $CONFIG_PATH"
echo "Stage: $STAGE"
echo "Train script: $TRAIN_PY"
echo "=========================================="
echo ""

# Ensure piper-sample-generator exists (volume mount may override build-time clone)
if [[ ! -d "/workspace/piper-sample-generator" ]]; then
    echo "Cloning piper-sample-generator (not found in mounted volume)..."
    git clone --depth 1 https://github.com/dscripka/piper-sample-generator /workspace/piper-sample-generator || {
        echo "Warning: Failed to clone piper-sample-generator. Synthetic data generation may not work."
    }
fi

# Set PYTHONPATH to include piper-sample-generator for generate_samples import
export PYTHONPATH="/workspace/piper-sample-generator:${PYTHONPATH:-}"

# Verify generate_samples.py exists
if [[ ! -f "/workspace/piper-sample-generator/generate_samples.py" ]]; then
    echo "Error: generate_samples.py not found in /workspace/piper-sample-generator/"
    echo "Directory contents:"
    ls -la /workspace/piper-sample-generator/ || echo "Directory does not exist"
    exit 1
fi

# Check for Piper TTS model and download if missing
PIPER_MODEL_DIR="/workspace/piper-sample-generator/models"
PIPER_MODEL_FILE="$PIPER_MODEL_DIR/en-us-libritts-high.pt"
PIPER_MODEL_URL="https://github.com/rhasspy/piper-sample-generator/releases/download/v1.0.0/en-us-libritts-high.pt"

if [[ ! -f "$PIPER_MODEL_FILE" ]]; then
    echo "=========================================="
    echo "Piper TTS model missing - downloading..."
    echo "=========================================="
    echo "Model file: $PIPER_MODEL_FILE"
    echo ""

    # Create models directory if it doesn't exist
    mkdir -p "$PIPER_MODEL_DIR"

    # Download the model file using Python (more reliable than wget/curl)
    if ! python -c "
import urllib.request
import sys
try:
    print(f'Downloading Piper TTS model from {sys.argv[1]}...')
    urllib.request.urlretrieve(sys.argv[1], sys.argv[2])
    print('Download complete!')
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
" "$PIPER_MODEL_URL" "$PIPER_MODEL_FILE" 2>&1; then
        echo ""
        echo "Error: Failed to download Piper TTS model from GitHub."
        echo "Training cannot proceed without the TTS model."
        echo ""
        echo "Please check your internet connection and try again."
        echo "To download manually, run:"
        echo "  python -c \"import urllib.request; urllib.request.urlretrieve('$PIPER_MODEL_URL', '$PIPER_MODEL_FILE')\""
        echo ""
        exit 1
    fi

    # Verify the file was downloaded successfully
    if [[ ! -f "$PIPER_MODEL_FILE" ]]; then
        echo "Error: Piper model file not found after download: $PIPER_MODEL_FILE"
        exit 1
    fi

    echo ""
    echo "Piper TTS model downloaded successfully!"
    echo ""
fi

# Check for JSON config file (required by generate_samples.py)
# Note: Volume mount overrides /workspace/piper-sample-generator/models/, so we need to
# get the JSON file from a backup location or download it
PIPER_MODEL_JSON="$PIPER_MODEL_DIR/en-us-libritts-high.pt.json"
if [[ ! -f "$PIPER_MODEL_JSON" ]]; then
    echo "=========================================="
    echo "Piper TTS model JSON config missing - retrieving..."
    echo "=========================================="
    echo "Config file: $PIPER_MODEL_JSON"
    echo ""

    # Strategy 1: Try to copy from build-time backup (no network required)
    # Backup is in /app to avoid being overridden by workspace volume mount
    JSON_BACKUP="/app/piper-json-backup.json"
    if [[ -f "$JSON_BACKUP" ]]; then
        echo "Copying JSON config from build-time backup..."
        cp "$JSON_BACKUP" "$PIPER_MODEL_JSON"
        if [[ -f "$PIPER_MODEL_JSON" ]]; then
            echo "JSON config copied successfully from backup!"
            echo ""
        else
            echo "Warning: Failed to copy from backup, will try other sources..."
        fi
    fi

    # Strategy 2: Try to copy from mounted workspace (local codebase is mounted at /workspace)
    if [[ ! -f "$PIPER_MODEL_JSON" ]]; then
        WORKSPACE_JSON="/workspace/piper-sample-generator/models/en-us-libritts-high.pt.json"
        if [[ -f "$WORKSPACE_JSON" ]]; then
            echo "Copying JSON config from mounted workspace..."
            cp "$WORKSPACE_JSON" "$PIPER_MODEL_JSON"
            if [[ -f "$PIPER_MODEL_JSON" ]]; then
                echo "JSON config copied successfully from workspace!"
                echo ""
            else
                echo "Warning: Failed to copy from workspace, will try download..."
            fi
        fi
    fi

    # Strategy 3: Download from GitHub if all other strategies failed
    if [[ ! -f "$PIPER_MODEL_JSON" ]]; then
        echo "Downloading JSON config from dscripka/piper-sample-generator repository..."
        PIPER_MODEL_JSON_URL="https://raw.githubusercontent.com/dscripka/piper-sample-generator/main/models/en-us-libritts-high.pt.json"
        if ! python -c "
import urllib.request
import sys
try:
    print(f'Downloading Piper TTS JSON config from {sys.argv[1]}...')
    urllib.request.urlretrieve(sys.argv[1], sys.argv[2])
    print('Download complete!')
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
" "$PIPER_MODEL_JSON_URL" "$PIPER_MODEL_JSON" 2>&1; then
            echo ""
            echo "Error: Failed to download Piper TTS JSON config from GitHub."
            echo "Training cannot proceed without the JSON config file."
            echo ""
            echo "All strategies failed:"
            echo "  1. Build-time backup not found"
            echo "  2. Workspace copy failed"
            echo "  3. GitHub download failed (404)"
            echo ""
            echo "Please rebuild the image: make build-wake-trainer-image-force"
            echo ""
            exit 1
        fi
    fi

    # Verify the JSON file was created successfully
    if [[ ! -f "$PIPER_MODEL_JSON" ]]; then
        echo "Error: Piper JSON config file not found: $PIPER_MODEL_JSON"
        exit 1
    fi

    echo ""
    echo "Piper TTS JSON config ready!"
    echo ""
fi

# Check for training data and download if missing
TRAINING_DATA_DIR="/workspace/services/models/wake/training-data"
MISSING_DATA=false

if [[ ! -d "$TRAINING_DATA_DIR/mit_rirs" ]]; then
    echo "Warning: MIT RIRs directory not found: $TRAINING_DATA_DIR/mit_rirs"
    MISSING_DATA=true
fi

if [[ ! -d "$TRAINING_DATA_DIR/background_clips" ]]; then
    echo "Warning: Background clips directory not found: $TRAINING_DATA_DIR/background_clips"
    MISSING_DATA=true
fi

# Check for validation features (full or subset)
if [[ ! -f "$TRAINING_DATA_DIR/validation_set_features.npy" ]] && \
   [[ ! -f "$TRAINING_DATA_DIR/validation_set_features_small.npy" ]]; then
    echo "Warning: Validation features file not found: $TRAINING_DATA_DIR/validation_set_features.npy"
    echo "         Subset also not found: $TRAINING_DATA_DIR/validation_set_features_small.npy"
    MISSING_DATA=true
fi

if [[ ! -f "$TRAINING_DATA_DIR/openwakeword_features_ACAV100M_2000_hrs_16bit.npy" ]]; then
    echo "Warning: Feature data file not found: $TRAINING_DATA_DIR/openwakeword_features_ACAV100M_2000_hrs_16bit.npy"
    MISSING_DATA=true
fi

if [[ "$MISSING_DATA" == "true" ]]; then
    echo "=========================================="
    echo "Training data missing - downloading from HuggingFace..."
    echo "=========================================="
    echo ""

    # Set HuggingFace cache to writable location
    export HF_HOME="/workspace/.cache/huggingface"
    mkdir -p "$HF_HOME"

    # Download training data - exit on failure
    if ! python /workspace/services/waketrainer/download-training-data.py \
        --base-dir "$TRAINING_DATA_DIR" 2>&1; then
        echo ""
        echo "Error: Failed to download training data from HuggingFace."
        echo "Training cannot proceed without the required data."
        echo ""
        echo "Please check your internet connection and try again."
        echo "To download manually, run:"
        echo "  python /workspace/services/waketrainer/download-training-data.py --base-dir $TRAINING_DATA_DIR"
        echo ""
        exit 1
    fi

    echo ""
    echo "Training data download completed successfully!"
    echo ""
fi

# Create validation subset if full dataset exists but subset doesn't
if [[ -f "$TRAINING_DATA_DIR/validation_set_features.npy" ]] && \
   [[ ! -f "$TRAINING_DATA_DIR/validation_set_features_small.npy" ]]; then
    echo "=========================================="
    echo "Creating validation subset (10,000 samples) for memory efficiency..."
    echo "=========================================="
    echo ""

    if python /workspace/services/waketrainer/create_validation_subset.py \
        --input "$TRAINING_DATA_DIR/validation_set_features.npy" \
        --output "$TRAINING_DATA_DIR/validation_set_features_small.npy" \
        --size 10000 2>&1; then
        echo ""
        echo "Validation subset created successfully!"
        echo ""
    else
        echo ""
        echo "Warning: Failed to create validation subset. Training will continue,"
        echo "         but you may need to disable validation in your config if OOM occurs."
        echo ""
    fi
fi

# Create openwakeword resources directory and verify/download infrastructure models
# Models should be available via volume mount (configured in Makefile), but download if missing
# This follows the same pattern as the discord service
python -c "
import openwakeword
import os
import shutil
import tempfile
from pathlib import Path

resources_dir = os.path.join(os.path.dirname(openwakeword.__file__), 'resources')
models_dir = os.path.join(resources_dir, 'models')

try:
    os.makedirs(models_dir, exist_ok=True)
    print(f'Ensured openwakeword resources directory exists: {models_dir}')

    # Check if infrastructure models exist (should be there via volume mount)
    infrastructure_models = ['melspectrogram.onnx', 'embedding_model.onnx', 'silero_vad.onnx']
    missing_models = [m for m in infrastructure_models if not os.path.exists(os.path.join(models_dir, m))]

    if missing_models:
        print(f'Warning: Missing infrastructure models: {missing_models}')
        print('These should be available via volume mount. Downloading missing models...')
        try:
            from openwakeword import utils as oww_utils

            # Download all models to temporary directory
            temp_dir = tempfile.mkdtemp(prefix='openwakeword_infrastructure_')
            oww_utils.download_models(model_names=[], target_directory=temp_dir)

            # Move infrastructure models to resources directory (mounted, so persists to host)
            downloaded_count = 0
            for model_name in missing_models:
                src = os.path.join(temp_dir, model_name)
                dst = os.path.join(models_dir, model_name)
                if os.path.exists(src):
                    shutil.move(src, dst)
                    downloaded_count += 1
                    print(f'Downloaded {model_name} to {dst}')
                else:
                    print(f'Warning: {model_name} not found in download')

            # Clean up temporary directory
            shutil.rmtree(temp_dir, ignore_errors=True)

            if downloaded_count > 0:
                print(f'Successfully downloaded {downloaded_count} infrastructure model(s)')
            else:
                print('Warning: No infrastructure models were downloaded')
        except Exception as e:
            print(f'Error: Could not download infrastructure models: {e}')
            print('Training will likely fail without these models')
    else:
        print('All infrastructure models are present (via volume mount)')

except PermissionError as e:
    print(f'Warning: Could not create openwakeword resources directory: {e}')
    print('This may cause training to fail during adversarial text generation.')
except Exception as e:
    print(f'Warning: Error setting up openwakeword resources: {e}')
" || echo "Warning: Could not verify openwakeword resources directory"

# Stage 1: Generate synthetic clips
if [[ "$STAGE" == "all" || "$STAGE" == "generate" ]]; then
    echo "=========================================="
    echo "Stage 1: Generating synthetic clips"
    echo "=========================================="
    python "$TRAIN_PY" --training_config "$CONFIG_PATH" --generate_clips || {
        echo "Error: Stage 1 (generate_clips) failed"
        exit 1
    }
    echo ""
fi

# Stage 2: Augment clips
if [[ "$STAGE" == "all" || "$STAGE" == "augment" ]]; then
    echo "=========================================="
    echo "Stage 2: Augmenting clips"
    echo "=========================================="
    OVERWRITE_FLAG=""
    if [[ "$OVERWRITE" == "true" || "$OVERWRITE" == "1" ]]; then
        OVERWRITE_FLAG="--overwrite"
        echo "Overwrite mode enabled - will regenerate existing features"
    fi
    python "$TRAIN_PY" --training_config "$CONFIG_PATH" --augment_clips $OVERWRITE_FLAG || {
        echo "Error: Stage 2 (augment_clips) failed"
        exit 1
    }
    echo ""
fi

# Stage 3: Train model
if [[ "$STAGE" == "all" || "$STAGE" == "train" ]]; then
    echo "=========================================="
    echo "Stage 3: Training model"
    echo "=========================================="
    # Use minimal wrapper to fix memory-intensive validation reshape
    WRAPPER_SCRIPT="/workspace/services/waketrainer/train_wrapper_minimal.py"
    if [[ -f "$WRAPPER_SCRIPT" ]]; then
        echo "Using memory-efficient validation reshape wrapper..."
        python "$WRAPPER_SCRIPT" --training_config "$CONFIG_PATH" --train_model || {
            echo "Error: Stage 3 (train_model) failed"
            exit 1
        }
    else
        echo "Warning: train_wrapper_minimal.py not found, using original train.py"
        python "$TRAIN_PY" --training_config "$CONFIG_PATH" --train_model || {
            echo "Error: Stage 3 (train_model) failed"
            exit 1
        }
    fi
    echo ""
fi

echo "=========================================="
echo "Training Complete!"
echo "=========================================="
echo ""
echo "Trained models should be in the output_dir specified in your config file."
echo "If output_dir is set to /workspace/services/models/wake/detection/{model_name},"
echo "models will be automatically discovered by the wake detection system."
echo ""

