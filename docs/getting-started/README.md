---
title: Getting Started Index
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-16
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Getting Started

# Getting Started

Use these guides to prepare your workstation, manage environment files, and exercise
local workflows before touching production infrastructure.

## Guides

-  [Environment configuration](environment.md) — How to manage `.env.sample`, `.env.common`,
  and service-specific overrides.
-  [Runtime quickstart](runtime.md) — Build, run, and monitor the Docker Compose stack.
-  [Local development workflows](local-development.md) — Make targets, linting, testing, and
  Docker routines.
-  [Troubleshooting](troubleshooting.md) — Common issues and remediation steps for audio,
  Docker, and permissions.

## Prerequisites

-  Docker Engine with `docker-compose` support.
-  `make` for invoking repository workflows.
-  Access to Discord, STT, LLM, and TTS credentials as required by your deployment plan.

## Next Steps

After completing the getting started tasks, review the [architecture overview](../architecture/system-overview.md)
for a deeper look at the service topology and data flows.
