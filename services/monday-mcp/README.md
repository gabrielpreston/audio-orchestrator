Monday.com MCP helper service

This service runs the `@mondaydotcomorg/monday-api-mcp` CLI via `npx` inside a small Node 20 container. It exposes the MCP HTTP endpoints so other services can register.

Environment
- MONDAY_API_KEY: required. Your monday.com API key.

Usage (with docker-compose)

1. Add MONDAY_API_KEY to your `.env.docker` or export it in your environment.
2. Start the stack: `docker compose up --build`

Notes
- The container runs `npx @mondaydotcomorg/monday-api-mcp -t <API_KEY>` and binds to 0.0.0.0 so the compose port forward works. The compose file maps host port 9002 -> container 9001.
