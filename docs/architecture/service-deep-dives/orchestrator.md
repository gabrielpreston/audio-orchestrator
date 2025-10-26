---
title: Orchestrator Service Deep Dive
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-18
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Architecture ▸ Service Deep Dives ▸ Orchestrator

# Orchestrator Enhanced Service

The orchestrator enhanced service coordinates transcript processing, LangChain tool calls, and response planning. It routes reasoning requests to the LLM service and manages the overall conversation flow.

## Responsibilities

-  Process transcripts from the Discord bot and coordinate MCP tool calls.
-  Route reasoning requests to the LLM service for natural language processing.
-  Manage conversation flow and response planning.
-  Coordinate with TTS service for spoken responses.
-  Provide bearer-authenticated APIs for downstream callers.

## API Surface

-  `POST /mcp/transcript` — Handle transcript processing from Discord service.
-  `GET /mcp/tools` — List available MCP tools.
-  `GET /mcp/connections` — List active MCP connections.
-  `GET /health/live` — Liveness check for container health.
-  `GET /health/ready` — Readiness check for service availability.

## Configuration Highlights

-  `LLM_BASE_URL`, `LLM_AUTH_TOKEN` — LLM service integration settings.
-  `TTS_BASE_URL`, `TTS_AUTH_TOKEN` — TTS service integration settings.
-  `MCP_CONFIG_PATH` — MCP manifest configuration path.
-  `ORCHESTRATOR_DEBUG_SAVE` — Enable debug data collection.
-  Logging inherits from `.env.common`.

## Observability

-  Structured logs track request IDs, MCP tool invocations, and latency breakdowns.
-  `/metrics` exposes request counters and duration histograms when scraped.
-  Use `make logs SERVICE=orchestrator-enhanced` to monitor orchestrated tool chains and LLM service interactions.

## Dependencies

-  Receives transcripts from the Discord bot and optional MCP tool manifests.
-  Routes reasoning requests to the LLM service for natural language processing.
-  Calls the TTS service to synthesize spoken responses.
-  May depend on additional capability servers registered through MCP manifests.
