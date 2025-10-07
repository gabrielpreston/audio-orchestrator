# MCP Server Integration Options

## Current State

- `services/bot` only connects to a single MCP endpoint by reading `MCP_SERVER_URL` and optionally falling back to a one-shot `/mcp/register` HTTP call when the websocket upgrade fails. The endpoint URL is derived from that single string, so there is no support for multiple servers or per-server metadata today. 【F:services/bot/cmd/bot/main.go†L23-L67】
- The shared MCP client wrapper handles one websocket session at a time and has no concept of server discovery beyond that direct URL. 【F:services/internal/mcp/client.go†L13-L78】
- The orchestrator service also self-registers with the MCP registry via a POST to `/mcp/register`, but again only supports a single server definition. 【F:services/llm/app.py†L18-L35】

To support richer MCP connectivity similar to Cursor, VS Code, and community-run clients, we need a configuration surface that can describe **multiple servers**, **per-server transports**, and **optional capability metadata** without forcing users to write code.

## Design Goals Inspired by Cursor / VS Code

Community tools generally expose a declarative manifest (e.g. `mcp.json`, VS Code `settings.json`'s `mcp.servers` map) with these properties:

1. **Workspace-local defaults + user overrides.** A repo can ship a baseline manifest while developers override entries in their own config directory.
2. **Named servers.** Each server has an identifier that clients reference when opening sessions.
3. **Command, transport, and env fields.** Cursor-style manifests specify how to spawn local MCP servers (command + args) or how to connect to remote sockets.
4. **Optional capability flags.** Some hosts allow marking servers as default for file browsing, tools, etc.

Implementations for the Discord bot should feel familiar to users coming from those tools.

## Option A — Layered `mcp.json` Manifest (Workspace + User)

**Overview.** Add support for loading a JSON manifest that follows the de facto MCP schema used by Cursor. The bot would read `mcpServers` entries, allowing either websocket endpoints or command-based spawners.

```json
{
  "mcpServers": {
    "registry": {
      "transport": {"type": "websocket", "url": "wss://registry.example.com/mcp/ws"}
    },
    "local-fs": {
      "command": "node",
      "args": ["./tools/fs-server.js"],
      "env": {"ROOT": "."}
    }
  }
}
```

**Configuration flow.**

1. Load manifests from `$XDG_CONFIG_HOME/discord-voice-lab/mcp.json` (user scope) and `<repo>/.discord-voice-lab/mcp.json` (workspace scope). Merge maps so user overrides win, mirroring VS Code’s precedence.
2. Each entry becomes a `ServerConfig` struct. For websocket entries, reuse the existing `ClientWrapper`. For command entries, spawn the process and expose stdio through the MCP SDK’s IO transport.
3. Replace the single `MCP_SERVER_URL` lookup with an iteration that connects to each enabled server and registers the bot with any matching registry entry.

**Pros.** Familiar to Cursor users; supports both local and remote servers; deterministic precedence; no new dependencies besides JSON parsing.

**Cons.** Requires new process-management code for command-based servers; operators must ship manifests with the repo or dotfiles.

**Implementation notes.**

- Introduce a `services/internal/mcp/config` package to parse/merge manifests and expand `~` references.
- Add `MCP_CONFIG_PATH` env override for nonstandard locations.
- Extend startup logs to list which servers connected successfully for observability.

## Option B — Declarative `servers.d/` Directory with Hot Reload

**Overview.** Emulate VS Code’s approach to drop-in JSON fragments by scanning a directory (e.g. `<repo>/.discord-voice-lab/mcp.d/`). Each file defines one server. This keeps manifests small and enables enabling/disabling servers by adding/removing files.

**Configuration flow.**

1. Define a schema like:

```json
{
  "name": "observability",
  "transport": {"type": "websocket", "url": "wss://observability.internal/mcp/ws"},
  "capabilities": ["logging", "metrics"],
  "enabled": true
}
```

2. At startup, read both workspace and user-level `servers.d` directories (user entries override by name). Merge into a list and connect sequentially.
3. Optional: watch the directory with fsnotify to support hot reload while the bot is running (disconnect from removed servers, connect to new ones).

**Pros.** Easy to reason about per-server configs; aligns with `.d` directory patterns from systemd/nginx; hot reload improves operator experience.

**Cons.** Slightly more complex file management; still requires command-spawn support if needed; watchers add more dependencies when hot reload is enabled.

**Implementation notes.**

- Introduce a `services/internal/mcp/loader` that can read both manifest styles (single JSON or directory of JSON files) for flexibility.
- Support `enabled` flags and future metadata like auth tokens or scopes.
- Combine with Option A’s precedence rules: workspace defaults, user overrides, environment-based fallbacks.

## Option C — Hybrid Registry + Client Manifest

**Overview.** Keep the existing registry (`/mcp/register`) for service discovery but let the bot maintain a manifest that references registry “labels.” Similar to how Cursor lets users reference remote MCP hubs.

**Configuration flow.**

1. Expand `mcp.json` to allow entries of type `registry`, e.g. `{ "type": "registry", "url": "https://mcp.example.com" }`.
2. On startup, fetch `/mcp/servers` (new endpoint) to obtain advertised services; filter by optional labels/scopes defined in config.
3. Establish websocket sessions for servers that match, while still supporting direct websocket or command entries for static dependencies.

**Pros.** Reuses existing registry infrastructure; scales to fleets where central registry keeps service metadata fresh; allows selective opt-in per bot deployment.

**Cons.** Requires enhancing the MCP server to expose discovery endpoints; adds network dependency at startup; more moving parts to secure.

**Implementation notes.**

- Define a `RegistryClient` that handles authentication and caching.
- Allow manifests to supply API tokens or TLS settings per registry entry.
- Provide clear logging when registry discovery fails so operators can fall back to static entries.

## Recommendation

Start with **Option A** to match the common MCP manifest shape used by Cursor and community projects, ensuring quick familiarity for developers. Layer in optional directory support (Option B) if teams want modular configs, and treat registry-driven discovery (Option C) as a follow-on once the MCP server exposes richer metadata.

This staged approach keeps initial changes focused on configuration parsing and connection lifecycle (low risk), while preserving a path to more dynamic service discovery as the ecosystem matures.
