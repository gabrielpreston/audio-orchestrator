# Wake Word Training Tool

Containerized tool for training custom wake word models using the openWakeWord library.

## Overview

This tool provides a containerized environment for training custom wake word models that integrate seamlessly with the audio-orchestrator wake detection system. It follows the existing tool container patterns (linter, tester, security) and uses the `python-ml` base image which includes PyTorch, CUDA support, and all necessary ML dependencies.

## Quick Start

### 1. Build the Training Image

```bash
make build-wake-trainer-image
```

### 2. Prepare Training Data

Training data should be placed in `./services/models/wake/training-data/`:

- **MIT RIRs**: Room impulse responses for audio augmentation
  - Place in: `./services/models/wake/training-data/mit_rirs/`
- **Background Audio**: Background noise clips for augmentation
  - Download: Background audio is downloaded as Parquet files from HuggingFace
  - Extract: Run `make extract-background-audio` to convert Parquet files to WAV format
  - WAV files will be placed in: `./services/models/wake/training-data/background_clips/wav/`
- **Validation Features**: Pre-computed features for false-positive validation
  - Place at: `./services/models/wake/training-data/validation_set_features.npy`
- **Feature Data Files**: Pre-computed openwakeword features for training
  - Place at: `./services/models/wake/training-data/openwakeword_features_ACAV100M_2000_hrs_16bit.npy`

**Note**: The training data directory is gitignored (large datasets, ~50GB total).

### 3. Create Training Configuration

Copy the example configuration and customize it:

```bash
cp services/waketrainer/config/example_config.yaml services/waketrainer/config/my_model.yaml
```

Edit `my_model.yaml` to set:
- `model_name`: Name for your custom model
- `target_phrase`: The wake word/phrase to detect
- `output_dir`: Should point to `/workspace/services/models/wake/detection/{model_name}` for automatic integration

### 4. Run Training

**Full training (all 3 stages)**:
```bash
make wake-train CONFIG=services/waketrainer/config/my_model.yaml
```

**Individual stages**:
```bash
# Stage 1: Generate synthetic clips
make wake-train-generate CONFIG=services/waketrainer/config/my_model.yaml

# Stage 2: Augment clips
make wake-train-augment CONFIG=services/waketrainer/config/my_model.yaml

# Stage 3: Train model
make wake-train-train CONFIG=services/waketrainer/config/my_model.yaml
```

## Training Stages

### Stage 1: Generate Synthetic Clips
- Uses Piper TTS to generate synthetic audio clips of the target phrase
- Creates positive and negative training examples
- Outputs WAV files in `{output_dir}/{model_name}/positive_train/` and similar directories

### Stage 2: Augment Clips
- Applies audio augmentation (noise, reverb, etc.) to generated clips
- Uses MIT RIRs and background audio for realistic augmentation
- Creates openwakeword features from augmented clips

### Stage 3: Train Model
- Trains a PyTorch model using the augmented features
- Uses default openwakeword training implementation
- Exports trained models in ONNX and TFLite formats
- Models are saved to `{output_dir}/{model_name}/{model_name}.onnx` and `.tflite`

## Integration with Wake Detection

Trained models are automatically discovered by the wake detection system when:

1. **Output directory** is set to `/workspace/services/models/wake/detection/{model_name}` in the config
2. **Models are saved** with `.onnx` or `.tflite` extension
3. **Model name** matches the directory name

The wake detection system uses a three-tier fallback:
1. User-provided paths (`WAKE_MODEL_PATHS` env var)
2. Auto-discovery in `./services/models/wake/detection/` (where trained models are placed)
3. Built-in defaults

## Configuration

The training configuration file (YAML) includes:

- **Model Settings**: `model_name`, `target_phrase`, `model_type`, `layer_size`
- **Training Data**: `n_samples`, `n_samples_val`, `feature_data_files`
- **Data Paths**: `rir_paths`, `background_paths`, `output_dir`
- **Training Parameters**: `steps`, `learning_rate`, `batch_n_per_class`
- **Augmentation**: `augmentation_rounds`, `augmentation_batch_size`

See `config/example_config.yaml` for a complete example with all available options.

## GPU Support

GPU acceleration is available if:

1. NVIDIA GPU is available on the host
2. `nvidia-container-runtime` is installed
3. Docker is configured with GPU support

The base image (`python-ml`) includes CUDA 12.1 support, and PyTorch will automatically detect and use the GPU if available. No code changes are needed - GPU support is transparent.

**Note**: GPU support is optional. Training will fall back to CPU if GPU is unavailable.

## Requirements

### Training Data

- **MIT RIRs**: Room impulse responses (download from HuggingFace or other sources)
- **Background Audio**: Audio clips for augmentation (AudioSet, FMA, etc.)
- **Validation Features**: Pre-computed features for false-positive validation
- **Feature Data Files**: Pre-computed openwakeword features (ACAV100M dataset recommended)

### System Resources

Training is resource-intensive:
- **CPU**: 4+ cores recommended
- **Memory**: 8GB+ RAM recommended
- **GPU**: Optional but recommended (CUDA-capable GPU)
- **Disk**: 50GB+ free space for training data and intermediate files

## Troubleshooting

### Config File Not Found
- Ensure the config path is relative to the workspace root
- Example: `CONFIG=services/waketrainer/config/my_model.yaml` (not absolute path)

### Training Data Not Found
- Verify paths in config file match actual directory structure
- Use workspace-relative paths: `/workspace/services/models/wake/training-data/...`

### GPU Not Available
- Training will automatically fall back to CPU
- Check GPU availability: `docker run --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi`

### Model Not Discovered
- Ensure models are in `./services/models/wake/detection/{model_name}/`
- Verify `.onnx` or `.tflite` files exist
- Check that model name matches directory name

### CUDA Out of Memory (OOM) Errors
- If OOM errors occur during training, try:
  - Reducing `batch_n_per_class` values in config
  - Reducing `steps` in config
  - Reducing `n_samples_val` (validation samples) - try 25, 50, or 100
  - Check GPU memory usage logs during training
  - Consider using a smaller model architecture (`layer_size` in config)

## Make Targets

- `make build-wake-trainer-image` - Build training image (if missing)
- `make build-wake-trainer-image-force` - Force rebuild training image
- `make push-wake-trainer-image` - Push image to registry
- `make extract-background-audio` - Extract background audio from Parquet to WAV files
- `make wake-train` - Run full training (requires `CONFIG=...`)
- `make wake-train-generate` - Run stage 1 only
- `make wake-train-augment` - Run stage 2 only
- `make wake-train-train` - Run stage 3 only

## References

- [openWakeWord Documentation](https://github.com/dscripka/openWakeWord)
- [Training Example Notebook](https://github.com/dscripka/openWakeWord/blob/main/notebooks/automatic_model_training.ipynb)
- [dscripka/piper-sample-generator](https://github.com/dscripka/piper-sample-generator)

