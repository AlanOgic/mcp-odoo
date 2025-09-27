# Odoo MCP HTTP Transport API Reference

This document provides comprehensive API reference for the Odoo Model Context Protocol (MCP) HTTP transport implementation.

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Rate Limiting](#rate-limiting)
4. [Request/Response Format](#requestresponse-format)
5. [Endpoints](#endpoints)
6. [MCP Protocol Methods](#mcp-protocol-methods)
7. [Error Codes](#error-codes)
8. [Client Examples](#client-examples)

## Overview

The Odoo MCP HTTP transport provides a RESTful HTTP interface to the Model Context Protocol server, enabling web-based clients to interact with Odoo ERP systems through standardized JSON-RPC 2.0 requests.

### Base URL
```
http://localhost:8000
```

### Content Type
All requests must use `Content-Type: application/json` except for streaming responses which use `text/event-stream`.

### API Version
Current API version: `1.0.0`

## Authentication

### API Key Authentication

All protected endpoints require an API key in the Authorization header:

```http
Authorization: Bearer YOUR_API_KEY_HERE
```

### Scopes

API keys have the following scopes:
- `read`: Read-only operations (search, list, get)
- `write`: Write operations (create, update, delete, execute methods)
- `admin`: Administrative operations (manage API keys, sessions)

### Session Management

Optional session management for maintaining state across requests:

1. Create a session using `/auth/token`
2. Include session ID in subsequent requests via `Mcp-Session-Id` header
3. Sessions expire after configured timeout (default: 1 hour)

## Rate Limiting

Rate limiting is enforced per API key:
- Default: 1000 requests per hour
- Configurable per API key
- Rate limit headers included in responses:
  - `X-RateLimit-Limit`: Maximum requests per hour
  - `X-RateLimit-Remaining`: Remaining requests in current window
  - `X-RateLimit-Reset`: Reset time as Unix timestamp

## Request/Response Format

### JSON-RPC 2.0 Structure

All MCP requests follow JSON-RPC 2.0 specification:

```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "method": "method_name",
  "params": {
    "parameter": "value"
  }
}
```

### Response Structure

Success response:
```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "result": {
    "data": "response_data"
  }
}
```

Error response:
```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "error": {
    "code": -32603,
    "message": "Internal error",
    "data": "Additional error information"
  }
}
```

## Endpoints

### Health Check

#### `GET /health`

Health check endpoint (no authentication required).

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "version": "1.0.0"
}
```

### Authentication

#### `POST /auth/token`

Create a new session token.

**Headers:**
```http
Authorization: Bearer YOUR_API_KEY
```

**Response:**
```json
{
  "session_id": "uuid-session-id",
  "expires_in": 3600
}
```

### Main MCP Endpoint

#### `POST /mcp`

Main endpoint for MCP protocol requests.

**Headers:**
```http
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
Mcp-Session-Id: session-id-optional
Accept: application/json (or text/event-stream for streaming)
```

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "tools/list",
  "params": {}
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "tools": [...]
  }
}
```

#### Streaming Responses

For endpoints that return large datasets, you can request streaming responses:

**Headers:**
```http
Accept: text/event-stream
```

**Response:**
```
data: {"jsonrpc":"2.0","id":"1","result":{"item":1}}

data: {"jsonrpc":"2.0","id":"1","result":{"item":2}}

data: [DONE]
```

### Session Management

#### `GET /mcp/sessions`

List active sessions (admin scope required).

**Headers:**
```http
Authorization: Bearer ADMIN_API_KEY
```

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "uuid-session-id",
      "created_at": "2024-01-15T10:30:00.000Z",
      "last_activity": "2024-01-15T11:30:00.000Z",
      "api_key_id": "key-id"
    }
  ]
}
```

#### `DELETE /mcp/sessions/{session_id}`

Delete a session.

**Headers:**
```http
Authorization: Bearer YOUR_API_KEY
```

**Response:**
```json
{
  "message": "Session deleted"
}
```

### API Key Management

#### `GET /api-keys`

List API keys (admin scope required).

**Headers:**
```http
Authorization: Bearer ADMIN_API_KEY
```

**Response:**
```json
{
  "api_keys": [
    {
      "key_id": "unique-key-id",
      "name": "claude-code",
      "scopes": ["read", "write"],
      "rate_limit": 1000,
      "created_at": "2024-01-15T10:30:00.000Z",
      "last_used": "2024-01-15T11:30:00.000Z"
    }
  ]
}
```

#### `POST /api-keys`

Create a new API key (admin scope required).

**Headers:**
```http
Authorization: Bearer ADMIN_API_KEY
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "new-application",
  "scopes": ["read", "write"],
  "rate_limit": 500
}
```

**Response:**
```json
{
  "message": "API key created successfully",
  "api_key": "generated-api-key-value",
  "warning": "Store this key securely. It cannot be retrieved again."
}
```

### API Documentation

#### `GET /docs`

Interactive API documentation (Swagger UI).

## MCP Protocol Methods

### Tools

#### `tools/list`

List available tools.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "tools/list"
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "tools": [
      {
        "name": "execute_method",
        "description": "Execute a custom method on an Odoo model",
        "inputSchema": {
          "type": "object",
          "properties": {
            "model": {"type": "string"},
            "method": {"type": "string"},
            "args": {"type": "array"},
            "kwargs": {"type": "object"}
          },
          "required": ["model", "method"]
        }
      },
      {
        "name": "search_employee",
        "description": "Search for employees by name",
        "inputSchema": {
          "type": "object",
          "properties": {
            "name": {"type": "string"},
            "limit": {"type": "integer", "default": 20}
          },
          "required": ["name"]
        }
      },
      {
        "name": "search_holidays",
        "description": "Search for holidays within a date range",
        "inputSchema": {
          "type": "object",
          "properties": {
            "start_date": {"type": "string"},
            "end_date": {"type": "string"},
            "employee_id": {"type": "integer"}
          },
          "required": ["start_date", "end_date"]
        }
      }
    ]
  }
}
```

#### `tools/call`

Call a specific tool.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": "2",
  "method": "tools/call",
  "params": {
    "name": "search_employee",
    "arguments": {
      "name": "John Doe",
      "limit": 10
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "2",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "[\n  {\n    \"id\": 1,\n    \"name\": \"John Doe\",\n    \"email\": \"john.doe@company.com\"\n  }\n]"
      }
    ]
  }
}
```

### Resources

#### `resources/list`

List available resources.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": "3",
  "method": "resources/list"
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "3",
  "result": {
    "resources": [
      {
        "uri": "odoo://models",
        "name": "List all available models",
        "description": "List all available models in the Odoo system",
        "mimeType": "application/json"
      },
      {
        "uri": "odoo://model/{model_name}",
        "name": "Get model information",
        "description": "Get detailed information about a specific model",
        "mimeType": "application/json"
      },
      {
        "uri": "odoo://record/{model_name}/{record_id}",
        "name": "Get record information",
        "description": "Get detailed information of a specific record by ID",
        "mimeType": "application/json"
      },
      {
        "uri": "odoo://search/{model_name}/{domain}",
        "name": "Search records",
        "description": "Search for records matching the domain",
        "mimeType": "application/json"
      }
    ]
  }
}
```

#### `resources/read`

Read a specific resource.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": "4",
  "method": "resources/read",
  "params": {
    "uri": "odoo://models"
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "4",
  "result": {
    "contents": [
      {
        "uri": "odoo://models",
        "mimeType": "application/json",
        "text": "{\"models\": [\"res.partner\", \"res.users\", ...]}"
      }
    ]
  }
}
```

## Error Codes

### Standard JSON-RPC 2.0 Errors

| Code | Message | Description |
|------|---------|-------------|
| -32700 | Parse error | Invalid JSON was received |
| -32600 | Invalid Request | The JSON sent is not a valid Request object |
| -32601 | Method not found | The method does not exist / is not available |
| -32602 | Invalid params | Invalid method parameter(s) |
| -32603 | Internal error | Internal JSON-RPC error |

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | OK - Request successful |
| 400 | Bad Request - Invalid request format |
| 401 | Unauthorized - Invalid or missing API key |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 413 | Payload Too Large - Request exceeds size limit |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Server error |

### MCP-Specific Errors

| Code | Message | Description |
|------|---------|-------------|
| -32001 | Authentication required | API key required but not provided |
| -32002 | Invalid API key | API key is invalid or expired |
| -32003 | Insufficient permissions | API key lacks required scope |
| -32004 | Rate limit exceeded | Request rate limit exceeded |
| -32005 | Session expired | Session has expired |
| -32006 | Resource not found | Requested resource does not exist |
| -32007 | Tool not found | Requested tool does not exist |
| -32008 | Odoo connection error | Failed to connect to Odoo |

## Client Examples

### Python

```python
import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"
API_KEY = "your-api-key-here"

# Headers
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# List available tools
response = requests.post(
    f"{BASE_URL}/mcp",
    headers=headers,
    json={
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/list"
    }
)

print(json.dumps(response.json(), indent=2))

# Call a tool
response = requests.post(
    f"{BASE_URL}/mcp",
    headers=headers,
    json={
        "jsonrpc": "2.0",
        "id": "2",
        "method": "tools/call",
        "params": {
            "name": "search_employee",
            "arguments": {
                "name": "John",
                "limit": 5
            }
        }
    }
)

print(json.dumps(response.json(), indent=2))
```

### JavaScript (Node.js)

```javascript
const axios = require('axios');

const BASE_URL = 'http://localhost:8000';
const API_KEY = 'your-api-key-here';

const headers = {
    'Authorization': `Bearer ${API_KEY}`,
    'Content-Type': 'application/json'
};

// List available tools
async function listTools() {
    try {
        const response = await axios.post(`${BASE_URL}/mcp`, {
            jsonrpc: '2.0',
            id: '1',
            method: 'tools/list'
        }, { headers });

        console.log(JSON.stringify(response.data, null, 2));
    } catch (error) {
        console.error('Error:', error.response?.data || error.message);
    }
}

// Call a tool
async function searchEmployee(name, limit = 10) {
    try {
        const response = await axios.post(`${BASE_URL}/mcp`, {
            jsonrpc: '2.0',
            id: '2',
            method: 'tools/call',
            params: {
                name: 'search_employee',
                arguments: {
                    name: name,
                    limit: limit
                }
            }
        }, { headers });

        console.log(JSON.stringify(response.data, null, 2));
    } catch (error) {
        console.error('Error:', error.response?.data || error.message);
    }
}

listTools();
searchEmployee('John', 5);
```

### cURL

```bash
# List tools
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tools/list"
  }'

# Call a tool
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "2",
    "method": "tools/call",
    "params": {
      "name": "search_employee",
      "arguments": {
        "name": "John",
        "limit": 5
      }
    }
  }'

# Read a resource
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "3",
    "method": "resources/read",
    "params": {
      "uri": "odoo://models"
    }
  }'
```

## WebSocket Support

*Note: WebSocket support is planned for future releases.*

## Rate Limiting Details

Rate limiting is implemented using a token bucket algorithm:

- Each API key has a separate bucket
- Tokens are refilled at a constant rate (configured per key)
- Requests consume tokens from the bucket
- When bucket is empty, requests are rejected with 429 status

Rate limit headers in responses:
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642248000
```

## Security Considerations

1. **API Keys**: Store API keys securely and never expose them in client-side code
2. **HTTPS**: Always use HTTPS in production environments
3. **Rate Limiting**: Monitor rate limit headers to avoid being throttled
4. **Sessions**: Use sessions for long-running clients to reduce overhead
5. **Scopes**: Use minimal required scopes for API keys
6. **Monitoring**: Monitor API usage and error rates for security threats

## Support

For issues and questions:
- GitHub Issues: [https://github.com/anthropics/claude-code/issues](https://github.com/anthropics/claude-code/issues)
- Documentation: [MCP HTTP Transport Summary](HTTP_TRANSPORT_SUMMARY.md)