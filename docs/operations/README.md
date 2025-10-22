---
title: Operations Index
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-20
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Operations

# Operations

These guides support day-to-day operation of the Discord Voice Lab stack, including runbooks,
observability practices, and security considerations.

## Runbooks

-  [Discord voice runbook](runbooks/discord-voice.md)

## Supporting Guides

-  [Observability](observability.md)
-  [Security](security.md)

## Tooling

-  `make logs` — Stream structured logs for one or more services.
-  `make docker-restart` — Restart the Compose stack while preserving volumes.
-  `make docker-clean` — Remove unused Docker resources (stopped containers, dangling images, build cache).
-  `make docker-clean-all` — Aggressive cleanup: stop compose and remove all images/volumes/networks.

Update this index when introducing new operational guides (e.g., incident response, deployment playbooks).
