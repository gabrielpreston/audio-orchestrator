Discord Voice Lab - Minimal scaffold

This repository contains documentation and a minimal Go scaffold for an LLM client used by the voice agent. It implements runtime model selection and fallback behavior for `gpt-5` vs a local fallback.

Quickstart:

```bash
make test
```

Troubleshooting: saving audio to disk
-----------------------------------

You can optionally save decoded audio WAV files to disk for troubleshooting STT mismatches by setting the `SAVE_AUDIO_DIR` environment variable before running the bot. Example:

```bash
export SAVE_AUDIO_DIR="/tmp/discord-voice-audio"
make run
```

The processor will write per-flush WAV files named like `20250101T123456.000Z_ssrc12345_username.wav` so you can replay them locally and compare against your STT service.

BuildKit / buildx
------------------

This repository provides Makefile helpers to build and push Docker images using Docker BuildKit / buildx. Example:

```bash
# Build the bot image (uses buildx if available)
make build-image IMAGE_TAG=latest

# Push the image (multi-arch builds via buildx)
make push-image IMAGE_TAG=latest
```

If you don't have a buildx builder configured, the Makefile target `buildx-ensure` will create one named `mybuilder` automatically.
