---
title: MCP Integration Appendix
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-18
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Architecture ▸ Integrations ▸ MCP

# MCP Integration Appendix

This appendix documents the `mcp.json` manifest format consumed by `services/discord/mcp.py` to
discover and connect to Model Context Protocol (MCP) servers.

## Manifest Discovery

The Discord bot loads manifests in the following order (later entries override earlier ones):

1. `MCP_CONFIG_PATH` environment override.
2. Workspace-scoped `./.audio-orchestrator/mcp.json` file.
3. User-scoped `~/.config/audio-orchestrator/mcp.json` file.

## Top-Level Shape

Manifests are JSON documents with an `mcpServers` map containing named server definitions.
Each server can specify either a `transport` (remote WebSocket) or `command` (local subprocess)
connection.

```json
{
  "mcpServers": {
    "docker-cmd": {
      "command": "/usr/local/bin/mcp-server",
      "args": ["--mode", "compose"],
      "env": {
        "SOME_ENV": "value"
      },
      "enabled": true
    },
    "remote-hub": {
      "transport": {
        "type": "websocket",
        "url": "wss://mcp.example.com/mcp/ws"
      },
      "enabled": true
    }
  }
}
```

## Field Reference

- `mcpServers` *(object)* — Map of server name to configuration.
- Server configuration fields:
  - `transport` *(object, optional)* — Remote connection descriptor.
    - `type` *(string)* — Supported value: `websocket`.
    - `url` *(string)* — WebSocket endpoint; HTTP(S) values are normalized to WS/WSS.
  - `command` *(string, optional)* — Executable to spawn from the bot container.
  - `args` *(array[string], optional)* — Arguments passed to the command.
  - `env` *(object[string]string, optional)* — Environment variables injected for the subprocess.
  - `enabled` *(boolean, optional)* — Disable an entry without deleting it.

## Behavior & Fallbacks

- Manifests are merged during startup; later files override earlier entries with the same name.
- Transport-backed servers are dialed over WebSocket using the provided URL.
- Command-backed servers run as child processes with stdio bridged as the MCP JSON-RPC transport.

## Recommendations

- Use absolute paths in `command` entries to avoid PATH resolution surprises; home directories are expanded automatically.
- Prefer `wss://` endpoints for production MCP servers and secure them with authentication headers or token-based access.
- Ensure subprocess servers speak newline-delimited JSON-RPC over stdio; the client uses upstream framing helpers.

### Minimal Example

```json
{
  "mcpServers": {
    "docker-tool": {
      "command": "./bin/mcp-server",
      "args": ["--config", "/data/config.json"],
      "enabled": true
    }
  }
}
```
