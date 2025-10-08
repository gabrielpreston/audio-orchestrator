# MCP manifest (mcp.json)

This document shows the `mcp.json` manifest shape used by the bot to discover and connect to MCP servers. The bot reads manifests in the following order (override -> workspace -> user):

- MCP_CONFIG_PATH (environment override)
- workspace `.discord-voice-lab/mcp.json` (project-local)
- user `~/.config/discord-voice-lab/mcp.json`

The parsed manifest is merged and normalized by `services/internal/mcp/config/manifest.go`.

Top-level shape

The manifest is a JSON object with an `mcpServers` map of named server entries. Each server entry may specify either a `transport` (remote websocket) or a `command` (local subprocess) connection.

Example manifest (two servers)

```json
{
  "mcpServers": {
    "local-cmd": {
      "command": "/usr/local/bin/mcp-server",
      "args": ["--mode", "dev"],
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

Field reference

- `mcpServers` (object): map of server name -> server config.
- ServerConfig fields:
  - `transport` (object, optional): when present and `type` is `websocket` the bot will attempt to connect by websocket. Use the `url` field to provide the websocket endpoint (e.g. `wss://host/mcp/ws`).
    - `type` (string): currently `websocket` is supported.
    - `url` (string): websocket URL (http(s) will be normalized to ws/wss automatically by the client).
  - `command` (string, optional): executable to spawn locally. If provided, the bot starts the process and wires stdio as the MCP transport.
  - `args` (array[string], optional): CLI args when spawning `command`.
  - `env` (object[string]string, optional): environment variables to set for the spawned process.
  - `enabled` (boolean, optional): set to `false` to skip a server entry.

Behavior and fallbacks

- The bot loads and merges manifests using `mcpconfig.LoadResult()` at startup. If a server is configured with `transport.type == "websocket"` the bot uses the provided `url` and attempts a websocket connection.
- If a server is configured with `command` the bot will start the command and use stdio as a JSON-RPC transport.
- If no servers from the manifest are connected and the `MCP_SERVER_URL` environment variable is set, the bot will attempt to connect directly to `${MCP_SERVER_URL}/mcp/ws` (http(s) is normalized to ws/wss).
- If websocket connection fails and `MCP_SERVER_URL` is configured, the bot falls back to registering itself by POSTing to `${MCP_SERVER_URL}/mcp/register` (the `Register` helper in `services/internal/mcp/registrar.go`).

Notes and recommendations

- Use absolute paths in `command` to avoid path/lookup surprises; the manifest loader expands `~` and similar paths when present.
- For production MCP servers prefer `wss://` and protect the endpoint (authentication/tokens) — the current client wrapper dials without additional headers by default.
- When running local MCP server processes via `command`, ensure the binary speaks the MCP JSON-RPC protocol over stdio. The client expects newline-delimited JSON messages and frames them with the upstream `jsonrpc` helper.

Example: minimal `mcp.json` for local development

```json
{
  "mcpServers": {
    "dev-local": {
      "command": "./bin/mcp-local-server",
      "args": ["--dev"],
      "enabled": true
    }
  }
}
```

Related files

- `services/internal/mcp/config/manifest.go` — manifest parsing and normalization.
- `services/internal/mcp/client.go` — `ClientWrapper`, ConnectWebSocket, ConnectCommand, session keepalive and Close logic.
- `services/internal/mcp/command_transport.go` and `services/internal/mcp/ws_transport_client.go` — transport adapters for command stdio and websockets.
- `services/internal/mcp/registrar.go` — helper to POST a simple service record to `${MCP_SERVER_URL}/mcp/register`.
