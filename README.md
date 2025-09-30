Discord Voice Lab - Minimal scaffold

This repository contains documentation and a minimal Go scaffold for an LLM client used by the voice agent. It implements runtime model selection and fallback behavior for `gpt-5` vs a local fallback.

Quickstart:

```bash
make test
```

Troubleshooting: saving audio to disk
-----------------------------------

You can optionally save decoded audio WAV files to disk for troubleshooting STT mismatches. To avoid confusion between container paths and host paths we provide two environment variables:

- `SAVE_AUDIO_DIR_CONTAINER` — container-local directory where the bot writes WAVs (example: `/app/wavs`).
- `SAVE_AUDIO_DIR_HOST` — host directory mounted into the container (example: `./.wavs`).

Example (docker-compose already mounts `./.wavs` to `/app/wavs`):

```bash
# set host path for convenience scripts
export SAVE_AUDIO_DIR_HOST="/tmp/discord-voice-audio"
# container path (when running in docker compose this should be /app/wavs)
export SAVE_AUDIO_DIR_CONTAINER="/app/wavs"
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
