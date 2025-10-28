---
title: Discord Voice Runbook
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-18
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Operations ▸ Runbooks ▸ Discord Voice

# Discord Voice Runbook

Use this runbook when operating the Discord bot and companion services in staging or production.

## Daily Checks

-  Run `make logs SERVICE=discord` to verify the bot connected to the configured guild and voice channel.
-  Confirm STT, Orchestrator, LLM, and TTS containers report healthy status via `/health`.
-  Spot-check latency by issuing a wake phrase and validating end-to-end response time (<2s target).
-  Review tool manifests for required credentials or endpoint changes.

## Incident Response

| Scenario | Mitigation |
| --- | --- |
| Bot disconnected from voice | Execute `make docker-restart` and confirm Discord permissions; review reconnect logs. |
| STT latency spike | Inspect STT logs for model throttling; scale CPU resources or adjust `FW_COMPUTE_TYPE`. |
| TTS audio gaps | Check `TTS_MAX_CONCURRENCY` utilization and rate limits; adjust or add replicas. |
| Orchestrator failures | Check orchestrator logs for LLM/TTS connectivity issues; verify auth tokens. |
| External call failures | Validate downstream service credentials; re-run with increased logging level (`LOG_LEVEL=debug`). |

## Escalation

-  Capture timestamps, service logs, and failing request IDs.
-  File an incident report under [reports](../../reports/README.md) with root-cause hypotheses.
-  Page the on-call integrator when the bot cannot respond to wake phrases for more than 15 minutes.

## Post-Incident Tasks

-  Update the runbook with newly discovered remediation steps.
-  Log follow-up actions in Monday.com or the chosen tracking system.
-  Review security implications if secrets were rotated or compromised.
