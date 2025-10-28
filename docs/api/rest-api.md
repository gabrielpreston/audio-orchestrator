---
title: REST API Documentation
author: Discord Voice Lab Team
status: active
last-updated: 2025-01-27
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ API ▸ REST API Documentation

# REST API Documentation

This document describes the REST API endpoints for the Audio Orchestrator services.

## Overview

The Audio Orchestrator uses REST APIs for service-to-service communication:

-  **Discord Service**: `http://discord:8001/api/v1/`
-  **Orchestrator Service**: `http://orchestrator:8200/api/v1/`

## Discord Service API

### Base URL

```text
http://discord:8001/api/v1/
```

### Endpoints

#### GET /capabilities

List available Discord service capabilities.

**Response:**

```json
{
  "service": "discord",
  "version": "1.0.0",
  "capabilities": [
    {
      "name": "send_message",
      "description": "Send a text message to Discord channel",
      "parameters": {
        "type": "object",
        "properties": {
          "channel_id": {"type": "string", "description": "Discord channel ID"},
          "content": {"type": "string", "description": "Message content"},
          "correlation_id": {"type": "string", "description": "Correlation ID for tracing"}
        },
        "required": ["channel_id", "content"]
      }
    },
    {
      "name": "transcript_notification",
      "description": "Receive transcript notifications from orchestrator",
      "parameters": {
        "type": "object",
        "properties": {
          "transcript": {"type": "string", "description": "Transcript text"},
          "user_id": {"type": "string", "description": "Discord user ID"},
          "channel_id": {"type": "string", "description": "Discord channel ID"},
          "correlation_id": {"type": "string", "description": "Correlation ID for tracing"}
        },
        "required": ["transcript", "user_id", "channel_id"]
      }
    }
  ]
}
```

#### POST /messages

Send a text message to a Discord channel.

**Request:**

```json
{
  "channel_id": "123456789",
  "content": "Hello, world!",
  "correlation_id": "test_correlation_123",
  "metadata": {"source": "test"}
}
```

**Response:**

```json
{
  "success": true,
  "message_id": "simulated_message_id",
  "correlation_id": "test_correlation_123"
}
```

#### POST /notifications/transcript

Receive transcript notifications from the orchestrator.

**Request:**

```json
{
  "transcript": "Hello, this is a test transcript",
  "user_id": "123456789",
  "channel_id": "987654321",
  "correlation_id": "test_correlation_456",
  "metadata": {"source": "test"}
}
```

**Response:**

```json
{
  "success": true,
  "correlation_id": "test_correlation_456"
}
```

## Orchestrator Service API

### Base URL

```text
http://orchestrator:8200/api/v1/
```

### Endpoints

#### GET /capabilities

List available orchestrator capabilities.

**Response:**

```json
{
  "service": "orchestrator",
  "version": "1.0.0",
  "capabilities": [
    {
      "name": "transcript_processing",
      "description": "Process voice transcripts using LangChain orchestration",
      "parameters": {
        "type": "object",
        "properties": {
          "transcript": {"type": "string", "description": "Transcript text to process"},
          "user_id": {"type": "string", "description": "User identifier"},
          "channel_id": {"type": "string", "description": "Channel identifier"},
          "correlation_id": {"type": "string", "description": "Correlation ID for tracing"},
          "metadata": {"type": "object", "description": "Additional metadata"}
        },
        "required": ["transcript", "user_id", "channel_id"]
      }
    },
    {
      "name": "discord_message_sending",
      "description": "Send messages to Discord channels",
      "parameters": {
        "type": "object",
        "properties": {
          "channel_id": {"type": "string", "description": "Discord channel ID"},
          "content": {"type": "string", "description": "Message content"},
          "correlation_id": {"type": "string", "description": "Correlation ID for tracing"}
        },
        "required": ["channel_id", "content"]
      }
    }
  ]
}
```

#### POST /transcripts

Process voice transcripts using LangChain orchestration.

**Request:**

```json
{
  "transcript": "Hello, how are you today?",
  "user_id": "test_user_123",
  "channel_id": "test_channel_456",
  "correlation_id": "test_correlation_789",
  "metadata": {"source": "test"}
}
```

**Response:**

```json
{
  "success": true,
  "response_text": "I'm doing well, thank you for asking!",
  "tool_calls": [
    {
      "tool": "weather",
      "args": {"location": "San Francisco"}
    }
  ],
  "correlation_id": "test_correlation_789"
}
```

#### GET /status

Get orchestrator service status and connections.

**Response:**

```json
{
  "service": "orchestrator",
  "status": "healthy",
  "version": "1.0.0",
  "connections": [
    {
      "service": "discord",
      "status": "connected",
      "url": "http://discord:8001"
    },
    {
      "service": "flan",
      "status": "connected",
      "url": "http://flan:8200"
    },
    {
      "service": "guardrails",
      "status": "available",
      "url": "http://guardrails:9300"
    }
  ],
  "uptime": "2h 30m"
}
```

## Error Handling

All endpoints return appropriate HTTP status codes:

-  `200 OK`: Request successful
-  `400 Bad Request`: Invalid request data
-  `422 Unprocessable Entity`: Validation error
-  `500 Internal Server Error`: Server error
-  `503 Service Unavailable`: Service not ready

Error responses include details:

```json
{
  "success": false,
  "error": "Invalid request data",
  "correlation_id": "test_correlation_123"
}
```

## Authentication

Currently, all REST API endpoints are public and do not require authentication. This is suitable for internal service-to-service communication within the Docker network.

## Rate Limiting

No rate limiting is currently implemented. Services should implement appropriate rate limiting based on their specific needs.

## Correlation ID

All requests support correlation ID for tracing requests across services. Include the `correlation_id` field in request bodies and headers:

**Header:**

```text
X-Correlation-ID: test_correlation_123
```

**Request Body:**

```json
{
  "correlation_id": "test_correlation_123",
  ...
}
```

## Examples

### Complete Voice Pipeline

1.  **Process transcript with orchestrator:**

```bash
curl -X POST http://orchestrator:8200/api/v1/transcripts \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "What is the weather like?",
    "user_id": "user_123",
    "channel_id": "channel_456",
    "correlation_id": "pipeline_test_123"
  }'
```

1.  **Send response message to Discord:**

```bash
curl -X POST http://discord:8001/api/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": "channel_456",
    "content": "The weather is sunny and 72°F",
    "correlation_id": "pipeline_test_123"
  }'
```

1.  **Send transcript notification:**

```bash
curl -X POST http://discord:8001/api/v1/notifications/transcript \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "What is the weather like?",
    "user_id": "user_123",
    "channel_id": "channel_456",
    "correlation_id": "pipeline_test_123"
  }'
```

### Check Service Status

```bash
# Check orchestrator status
curl http://orchestrator:8200/api/v1/status

# Check Discord capabilities
curl http://discord:8001/api/v1/capabilities
```
