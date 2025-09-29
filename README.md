Discord Voice Lab - Minimal scaffold

This repository contains documentation and a minimal Go scaffold for an LLM client used by the voice agent. It implements runtime model selection and fallback behavior for `gpt-5` vs a local fallback.

Quickstart:

```bash
make test
```

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
