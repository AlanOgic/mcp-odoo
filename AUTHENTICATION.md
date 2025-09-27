# Authentication Guide: Odoo MCP HTTP Transport

This guide provides comprehensive information about authentication and authorization in the Odoo MCP HTTP Transport, including setup, management, and best practices.

## Table of Contents

1. [Authentication Overview](#authentication-overview)
2. [API Key Management](#api-key-management)
3. [Scope-Based Authorization](#scope-based-authorization)
4. [Session Management](#session-management)
5. [Authentication Methods](#authentication-methods)
6. [Client Integration](#client-integration)
7. [Security Considerations](#security-considerations)
8. [Common Patterns](#common-patterns)
9. [Migration and Rotation](#migration-and-rotation)
10. [Troubleshooting](#troubleshooting)

## Authentication Overview

The Odoo MCP HTTP Transport uses a multi-layered security approach:

### Security Architecture

```
┌─────────────────┐
│   Client App    │
└─────────┬───────┘
          │ API Key (Bearer Token)
          ▼
┌─────────────────┐
│  HTTP Transport │ ← Rate Limiting
└─────────┬───────┘   Scope Validation
          │           Session Management
          ▼
┌─────────────────┐
│   MCP Server    │
└─────────┬───────┘
          │ XML-RPC Authentication
          ▼
┌─────────────────┐
│  Odoo Instance  │
└─────────────────┘
```

### Key Components

1. **API Keys**: Cryptographically secure tokens for client authentication
2. **Scopes**: Fine-grained permission system (read/write/admin)
3. **Rate Limiting**: Request throttling per API key
4. **Sessions**: Optional stateful interactions
5. **Transport Security**: HTTPS/TLS encryption

## API Key Management

### Creating API Keys

#### Command Line Interface

```bash
# Basic API key creation
odoo-mcp --create-api-key "my-application"

# With specific scopes and rate limit
odoo-mcp --create-api-key "production-app" \
  --scopes read,write \
  --rate-limit 2000

# Administrative key
odoo-mcp --create-api-key "admin-tool" \
  --scopes read,write,admin \
  --rate-limit 5000
```

#### Programmatic Creation

```python
from src.odoo_mcp.security import security_manager

# Create API key
api_key = security_manager.create_api_key(
    name="integration-service",
    scopes={"read", "write"},
    rate_limit=1000
)

print(f"API Key: {api_key}")
print("Store this securely - it cannot be retrieved again!")
```

#### HTTP API (Admin Required)

```bash
curl -X POST http://localhost:8000/api-keys \
  -H "Authorization: Bearer admin-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "new-service",
    "scopes": ["read", "write"],
    "rate_limit": 1500
  }'
```

### Listing and Managing Keys

#### List All Keys

```bash
# Basic listing
odoo-mcp --list-api-keys

# Detailed information
odoo-mcp --list-api-keys --verbose

# JSON output for scripting
odoo-mcp --list-api-keys --format json
```

#### Via HTTP API

```bash
curl -H "Authorization: Bearer admin-api-key" \
     http://localhost:8000/api-keys
```

**Response:**
```json
{
  "api_keys": [
    {
      "key_id": "key_abc123",
      "name": "production-app",
      "scopes": ["read", "write"],
      "rate_limit": 2000,
      "created_at": "2024-01-15T10:30:00Z",
      "last_used": "2024-01-15T14:20:00Z",
      "requests_count": 1542
    }
  ]
}
```

### Key Properties

#### Key Structure
```json
{
  "key_id": "unique-identifier",
  "name": "human-readable-name",
  "scopes": ["read", "write", "admin"],
  "rate_limit": 1000,
  "created_at": "2024-01-15T10:30:00Z",
  "last_used": "2024-01-15T14:20:00Z",
  "requests_count": 1542,
  "is_active": true
}
```

#### Key Generation
- **Length**: 32+ bytes of cryptographically secure randomness
- **Format**: Base64-encoded for URL safety
- **Storage**: bcrypt-hashed with cost factor 12
- **Validation**: Real-time verification against stored hash

## Scope-Based Authorization

### Available Scopes

| Scope | Description | Permitted Operations |
|-------|-------------|---------------------|
| `read` | Read-only access | `tools/list`, `resources/list`, `resources/read`, search operations |
| `write` | Read and write access | All read operations + `tools/call` with data modification |
| `admin` | Administrative access | All operations + API key management, session management |

### Scope Validation

#### Automatic Validation
```python
# Tool scope requirements (defined in http_transport.py)
TOOL_SCOPES = {
    "execute_method": "write",      # Requires write scope
    "search_employee": "read",      # Requires read scope
    "search_holidays": "read",      # Requires read scope
}

# Resource access (all require read scope minimum)
RESOURCE_SCOPES = {
    "odoo://models": "read",
    "odoo://model/*": "read",
    "odoo://record/*": "read",
    "odoo://search/*": "read"
}
```

#### Custom Scope Validation
```python
from src.odoo_mcp.security import APIKeyAuth

def require_scope(required_scope: str):
    def decorator(func):
        def wrapper(api_key: APIKey = Depends(APIKeyAuth())):
            if required_scope not in api_key.scopes:
                raise HTTPException(
                    status_code=403,
                    detail=f"Requires '{required_scope}' scope"
                )
            return func(api_key)
        return wrapper
    return decorator

# Usage
@app.post("/custom-endpoint")
@require_scope("admin")
async def admin_only_endpoint(api_key: APIKey):
    # This endpoint requires admin scope
    pass
```

### Best Practices for Scopes

#### Principle of Least Privilege
```python
# Good: Minimal scopes
reporting_key = create_api_key(
    name="reporting-dashboard",
    scopes={"read"}  # Only needs to read data
)

integration_key = create_api_key(
    name="crm-integration",
    scopes={"read", "write"}  # Needs to sync data
)

# Avoid: Excessive privileges
admin_key = create_api_key(
    name="simple-report",
    scopes={"read", "write", "admin"}  # Too many privileges
)
```

#### Environment-Specific Scopes
```bash
# Development - broader access for testing
DEV_KEY=$(odoo-mcp --create-api-key "dev-testing" --scopes read,write,admin)

# Staging - production-like restrictions
STAGING_KEY=$(odoo-mcp --create-api-key "staging-app" --scopes read,write)

# Production - minimal required access
PROD_KEY=$(odoo-mcp --create-api-key "production-app" --scopes read)
```

## Session Management

### Session Lifecycle

#### Creating Sessions

```bash
# Create a session
curl -X POST http://localhost:8000/auth/token \
  -H "Authorization: Bearer your-api-key"
```

**Response:**
```json
{
  "session_id": "sess_abc123def456",
  "expires_in": 3600
}
```

#### Using Sessions

```bash
# Include session ID in subsequent requests
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer your-api-key" \
  -H "Mcp-Session-Id: sess_abc123def456" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}'
```

#### Session Benefits

1. **Performance**: Reduced authentication overhead
2. **State Management**: Server-side state preservation
3. **Tracking**: Request correlation and audit trails
4. **Security**: Additional validation layer

### Session Configuration

```json
{
  "session_timeout": 3600,        // 1 hour default
  "session_cleanup_interval": 300, // Clean expired sessions every 5 minutes
  "max_sessions_per_key": 10,     // Prevent session exhaustion
  "secure_session_ids": true      // Use cryptographically secure IDs
}
```

### Session Management API

#### List Active Sessions (Admin)

```bash
curl -H "Authorization: Bearer admin-api-key" \
     http://localhost:8000/mcp/sessions
```

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "sess_abc123",
      "created_at": "2024-01-15T10:30:00Z",
      "last_activity": "2024-01-15T10:35:00Z",
      "api_key_id": "key_def456"
    }
  ]
}
```

#### Delete Session

```bash
# Delete your own session
curl -X DELETE http://localhost:8000/mcp/sessions/sess_abc123 \
  -H "Authorization: Bearer your-api-key"

# Admin can delete any session
curl -X DELETE http://localhost:8000/mcp/sessions/sess_abc123 \
  -H "Authorization: Bearer admin-api-key"
```

## Authentication Methods

### Bearer Token Authentication

#### Standard Format
```http
Authorization: Bearer your-api-key-here
```

#### Implementation
```python
import requests

headers = {
    "Authorization": "Bearer your-api-key",
    "Content-Type": "application/json"
}

response = requests.post(
    "http://localhost:8000/mcp",
    headers=headers,
    json={
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/list"
    }
)
```

### Query Parameter Authentication

#### URL Format
```
http://localhost:8000/mcp?api_key=your-api-key-here
```

#### Use Cases
- Claude Code integration
- Simple client implementations
- URL-based access patterns

#### Security Considerations
- API key visible in URL
- Logged in access logs
- Should only be used over HTTPS
- Consider for internal networks only

### Custom Header Authentication

#### Alternative Headers
```http
X-API-Key: your-api-key-here
X-Auth-Token: your-api-key-here
```

#### Configuration
```python
# Custom authentication handler
class CustomAPIKeyAuth:
    def __call__(self, request: Request):
        api_key = (
            request.headers.get("X-API-Key") or
            request.headers.get("X-Auth-Token") or
            request.headers.get("Authorization", "").replace("Bearer ", "")
        )

        if not api_key:
            raise HTTPException(401, "API key required")

        return validate_api_key(api_key)
```

## Client Integration

### Python Client Example

```python
import requests
import json
from typing import Optional, Dict, Any

class OdooMCPClient:
    def __init__(self, base_url: str, api_key: str, use_sessions: bool = False):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session_id: Optional[str] = None

        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        if use_sessions:
            self._create_session()

    def _create_session(self):
        """Create a new session for this client"""
        response = requests.post(
            f"{self.base_url}/auth/token",
            headers=self.headers
        )
        response.raise_for_status()

        data = response.json()
        self.session_id = data["session_id"]
        self.headers["Mcp-Session-Id"] = self.session_id

    def _make_request(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make an MCP request"""
        payload = {
            "jsonrpc": "2.0",
            "id": f"req_{hash(json.dumps([method, params]))}",
            "method": method
        }

        if params:
            payload["params"] = params

        response = requests.post(
            f"{self.base_url}/mcp",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()

        data = response.json()
        if "error" in data:
            raise Exception(f"MCP Error: {data['error']}")

        return data["result"]

    def list_tools(self) -> Dict[str, Any]:
        """List available tools"""
        return self._make_request("tools/list")

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a specific tool"""
        return self._make_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })

    def search_employees(self, name: str, limit: int = 20) -> Dict[str, Any]:
        """Search for employees by name"""
        return self.call_tool("search_employee", {
            "name": name,
            "limit": limit
        })

    def execute_odoo_method(self, model: str, method: str,
                           args: list = None, kwargs: dict = None) -> Dict[str, Any]:
        """Execute an Odoo model method"""
        return self.call_tool("execute_method", {
            "model": model,
            "method": method,
            "args": args or [],
            "kwargs": kwargs or {}
        })

    def close(self):
        """Clean up resources"""
        if self.session_id:
            try:
                requests.delete(
                    f"{self.base_url}/mcp/sessions/{self.session_id}",
                    headers=self.headers
                )
            except:
                pass  # Best effort cleanup

# Usage example
client = OdooMCPClient(
    base_url="http://localhost:8000",
    api_key="your-api-key",
    use_sessions=True
)

try:
    # List available tools
    tools = client.list_tools()
    print("Available tools:", [tool["name"] for tool in tools["tools"]])

    # Search for employees
    employees = client.search_employees("John", limit=5)
    print("Employees:", employees)

    # Execute custom Odoo method
    partners = client.execute_odoo_method(
        model="res.partner",
        method="search_read",
        args=[["is_company", "=", True]],
        kwargs={"fields": ["name", "email"], "limit": 10}
    )
    print("Partners:", partners)

finally:
    client.close()
```

### JavaScript/Node.js Client

```javascript
const axios = require('axios');

class OdooMCPClient {
    constructor(baseURL, apiKey, useSession = false) {
        this.baseURL = baseURL.replace(/\/$/, '');
        this.apiKey = apiKey;
        this.sessionId = null;

        this.headers = {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
        };

        if (useSession) {
            this.createSession();
        }
    }

    async createSession() {
        try {
            const response = await axios.post(
                `${this.baseURL}/auth/token`,
                {},
                { headers: this.headers }
            );

            this.sessionId = response.data.session_id;
            this.headers['Mcp-Session-Id'] = this.sessionId;

            console.log(`Session created: ${this.sessionId}`);
        } catch (error) {
            console.error('Failed to create session:', error.message);
        }
    }

    async makeRequest(method, params = null) {
        const payload = {
            jsonrpc: '2.0',
            id: `req_${Date.now()}_${Math.random()}`,
            method: method
        };

        if (params) {
            payload.params = params;
        }

        try {
            const response = await axios.post(
                `${this.baseURL}/mcp`,
                payload,
                { headers: this.headers }
            );

            if (response.data.error) {
                throw new Error(`MCP Error: ${JSON.stringify(response.data.error)}`);
            }

            return response.data.result;
        } catch (error) {
            if (error.response) {
                throw new Error(`HTTP ${error.response.status}: ${error.response.data?.detail || error.response.statusText}`);
            }
            throw error;
        }
    }

    async listTools() {
        return this.makeRequest('tools/list');
    }

    async callTool(toolName, arguments) {
        return this.makeRequest('tools/call', {
            name: toolName,
            arguments: arguments
        });
    }

    async searchEmployees(name, limit = 20) {
        return this.callTool('search_employee', {
            name: name,
            limit: limit
        });
    }

    async executeOdooMethod(model, method, args = [], kwargs = {}) {
        return this.callTool('execute_method', {
            model: model,
            method: method,
            args: args,
            kwargs: kwargs
        });
    }

    async close() {
        if (this.sessionId) {
            try {
                await axios.delete(
                    `${this.baseURL}/mcp/sessions/${this.sessionId}`,
                    { headers: this.headers }
                );
                console.log('Session closed');
            } catch (error) {
                console.error('Failed to close session:', error.message);
            }
        }
    }
}

// Usage example
(async () => {
    const client = new OdooMCPClient(
        'http://localhost:8000',
        'your-api-key',
        true  // Use sessions
    );

    try {
        // List tools
        const tools = await client.listTools();
        console.log('Available tools:', tools.tools.map(t => t.name));

        // Search employees
        const employees = await client.searchEmployees('John', 5);
        console.log('Employees:', employees);

        // Execute Odoo method
        const partners = await client.executeOdooMethod(
            'res.partner',
            'search_read',
            [['is_company', '=', true]],
            { fields: ['name', 'email'], limit: 10 }
        );
        console.log('Partners:', partners);

    } catch (error) {
        console.error('Error:', error.message);
    } finally {
        await client.close();
    }
})();
```

### cURL Examples

#### Basic Authentication

```bash
# Set up variables
API_KEY="your-api-key-here"
BASE_URL="http://localhost:8000"

# Helper function for MCP requests
mcp_request() {
    local method="$1"
    local params="$2"

    local payload='{"jsonrpc":"2.0","id":"'$(date +%s)'","method":"'$method'"'
    if [ -n "$params" ]; then
        payload+=', "params":'$params''
    fi
    payload+='}'

    curl -s -X POST "$BASE_URL/mcp" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d "$payload"
}

# List tools
mcp_request "tools/list"

# Call a tool
mcp_request "tools/call" '{
    "name": "search_employee",
    "arguments": {
        "name": "John",
        "limit": 5
    }
}'
```

#### Session-Based Authentication

```bash
# Create session
SESSION_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/token" \
    -H "Authorization: Bearer $API_KEY")

SESSION_ID=$(echo "$SESSION_RESPONSE" | jq -r '.session_id')

# Use session in requests
curl -X POST "$BASE_URL/mcp" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Mcp-Session-Id: $SESSION_ID" \
    -H "Content-Type: application/json" \
    -d '{
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/list"
    }'

# Clean up session
curl -X DELETE "$BASE_URL/mcp/sessions/$SESSION_ID" \
    -H "Authorization: Bearer $API_KEY"
```

## Security Considerations

### API Key Security

#### Storage Best Practices

```bash
# Environment variables (recommended)
export ODOO_MCP_API_KEY="your-api-key"

# Secure file storage
echo "your-api-key" | sudo tee /etc/odoo-mcp/api-key.txt
sudo chmod 600 /etc/odoo-mcp/api-key.txt
sudo chown root:root /etc/odoo-mcp/api-key.txt

# Read from secure storage
API_KEY=$(sudo cat /etc/odoo-mcp/api-key.txt)
```

#### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: odoo-mcp-credentials
type: Opaque
data:
  api-key: eW91ci1hcGkta2V5LWhlcmU=  # base64 encoded

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
spec:
  template:
    spec:
      containers:
      - name: app
        env:
        - name: ODOO_MCP_API_KEY
          valueFrom:
            secretKeyRef:
              name: odoo-mcp-credentials
              key: api-key
```

#### Docker Secrets

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    environment:
      - ODOO_MCP_API_KEY_FILE=/run/secrets/api_key
    secrets:
      - api_key

secrets:
  api_key:
    file: ./api_key.txt
```

### Transport Security

#### HTTPS Enforcement

```json
{
  "require_https": true,
  "ssl_certfile": "/etc/ssl/certs/your-cert.pem",
  "ssl_keyfile": "/etc/ssl/private/your-key.pem",
  "ssl_protocols": ["TLSv1.2", "TLSv1.3"]
}
```

#### Header Security

```python
# Security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
```

### Rate Limiting Security

#### Adaptive Rate Limiting

```python
def get_rate_limit(api_key: APIKey) -> int:
    """Dynamic rate limiting based on key type and usage patterns"""
    base_limit = api_key.rate_limit

    # Increase limit for trusted keys
    if api_key.is_trusted:
        base_limit *= 2

    # Decrease limit for suspicious activity
    if api_key.suspicious_activity_score > 0.7:
        base_limit = int(base_limit * 0.5)

    return base_limit
```

#### Rate Limit Monitoring

```python
# Monitor for abuse patterns
def detect_abuse(api_key: APIKey) -> bool:
    recent_requests = get_recent_requests(api_key.key_id, hours=1)

    # Check for rapid fire requests
    if len(recent_requests) > api_key.rate_limit * 1.5:
        return True

    # Check error rate
    error_rate = sum(1 for r in recent_requests if r.status >= 400) / len(recent_requests)
    if error_rate > 0.5:
        return True

    return False
```

## Common Patterns

### Long-Running Clients

```python
import time
import threading
from datetime import datetime, timedelta

class PersistentOdooMCPClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.api_key = api_key
        self.session_id = None
        self.session_expires = None
        self.lock = threading.Lock()

        self._create_session()

        # Start session renewal thread
        self.renewal_thread = threading.Thread(
            target=self._session_renewal_worker,
            daemon=True
        )
        self.renewal_thread.start()

    def _create_session(self):
        with self.lock:
            response = requests.post(
                f"{self.base_url}/auth/token",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            data = response.json()

            self.session_id = data["session_id"]
            self.session_expires = datetime.now() + timedelta(seconds=data["expires_in"])

    def _session_renewal_worker(self):
        while True:
            # Renew session 5 minutes before expiration
            if self.session_expires and datetime.now() > self.session_expires - timedelta(minutes=5):
                try:
                    self._create_session()
                except Exception as e:
                    print(f"Failed to renew session: {e}")

            time.sleep(60)  # Check every minute

    def make_request(self, method, params=None):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        # Implementation continues...
```

### Batch Operations

```python
import asyncio
import aiohttp

class BatchOdooMCPClient:
    def __init__(self, base_url, api_key, max_concurrent=10):
        self.base_url = base_url
        self.api_key = api_key
        self.semaphore = asyncio.Semaphore(max_concurrent)

        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def _make_request(self, session, method, params=None):
        async with self.semaphore:
            payload = {
                "jsonrpc": "2.0",
                "id": f"batch_{method}_{hash(str(params))}",
                "method": method
            }

            if params:
                payload["params"] = params

            async with session.post(
                f"{self.base_url}/mcp",
                json=payload,
                headers=self.headers
            ) as response:
                return await response.json()

    async def batch_execute(self, operations):
        """Execute multiple operations concurrently"""
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._make_request(session, op["method"], op.get("params"))
                for op in operations
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results

# Usage
client = BatchOdooMCPClient("http://localhost:8000", "your-api-key")

operations = [
    {"method": "tools/call", "params": {"name": "search_employee", "arguments": {"name": "John"}}},
    {"method": "tools/call", "params": {"name": "search_employee", "arguments": {"name": "Jane"}}},
    {"method": "tools/call", "params": {"name": "search_holidays", "arguments": {"start_date": "2024-01-01", "end_date": "2024-01-31"}}}
]

results = asyncio.run(client.batch_execute(operations))
```

### Error Handling and Retry Logic

```python
import time
import random
from typing import Dict, Any, Optional

class RobustOdooMCPClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def _exponential_backoff(self, attempt: int, base_delay: float = 1.0) -> float:
        """Calculate exponential backoff with jitter"""
        delay = base_delay * (2 ** attempt)
        jitter = random.uniform(0.1, 0.5) * delay
        return delay + jitter

    def make_request_with_retry(self, method: str, params: Optional[Dict] = None,
                               max_retries: int = 3) -> Dict[str, Any]:
        """Make request with exponential backoff retry"""
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "id": f"retry_{method}_{attempt}",
                    "method": method
                }

                if params:
                    payload["params"] = params

                response = requests.post(
                    f"{self.base_url}/mcp",
                    json=payload,
                    headers=self.headers,
                    timeout=30
                )

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    if attempt < max_retries:
                        print(f"Rate limited, waiting {retry_after} seconds...")
                        time.sleep(retry_after)
                        continue

                response.raise_for_status()

                data = response.json()
                if "error" in data:
                    error = data["error"]

                    # Don't retry certain errors
                    if error["code"] in [-32002, -32003]:  # Invalid API key, insufficient permissions
                        raise Exception(f"Authentication error: {error['message']}")

                    # Retry on server errors
                    if attempt < max_retries and error["code"] == -32603:
                        delay = self._exponential_backoff(attempt)
                        print(f"Server error, retrying in {delay:.2f} seconds...")
                        time.sleep(delay)
                        continue

                    raise Exception(f"MCP Error: {error}")

                return data["result"]

            except requests.exceptions.RequestException as e:
                last_exception = e

                if attempt < max_retries:
                    delay = self._exponential_backoff(attempt)
                    print(f"Request failed, retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                    continue

        raise Exception(f"Request failed after {max_retries} retries: {last_exception}")
```

## Migration and Rotation

### API Key Rotation Strategy

#### Gradual Migration

```python
def rotate_api_keys(old_key_name: str, new_key_name: str):
    """Rotate API keys with overlap period"""

    # 1. Create new key with same permissions
    old_key_info = get_api_key_info(old_key_name)
    new_key = security_manager.create_api_key(
        name=new_key_name,
        scopes=old_key_info["scopes"],
        rate_limit=old_key_info["rate_limit"]
    )

    print(f"New API key created: {new_key}")
    print("Update your applications to use the new key")

    # 2. Monitor usage of old key
    input("Press Enter when all applications are using the new key...")

    # 3. Verify old key is no longer used
    old_usage = get_recent_usage(old_key_info["key_id"], hours=24)
    if old_usage:
        print(f"Warning: Old key still has {len(old_usage)} recent requests")
        confirm = input("Proceed with deletion? (y/N): ")
        if confirm.lower() != 'y':
            print("Key rotation cancelled")
            return

    # 4. Delete old key
    delete_api_key(old_key_info["key_id"])
    print("Old API key deleted successfully")

# Usage
rotate_api_keys("production-app-v1", "production-app-v2")
```

#### Automated Rotation

```python
import schedule
import time
from datetime import datetime, timedelta

def automated_key_rotation():
    """Automated key rotation for security"""

    # Get keys older than 90 days
    old_keys = [
        key for key in security_manager.list_api_keys()
        if datetime.fromisoformat(key["created_at"]) < datetime.now() - timedelta(days=90)
    ]

    for old_key in old_keys:
        # Skip if key is still active
        if get_recent_usage(old_key["key_id"], hours=168):  # 1 week
            continue

        # Create replacement key
        new_key = security_manager.create_api_key(
            name=f"{old_key['name']}-rotated-{datetime.now().strftime('%Y%m%d')}",
            scopes=old_key["scopes"],
            rate_limit=old_key["rate_limit"]
        )

        # Notify administrators
        send_notification(
            subject="API Key Rotation",
            message=f"Key {old_key['name']} has been rotated. New key: {new_key[:8]}..."
        )

        # Mark old key for deletion (after grace period)
        schedule_key_deletion(old_key["key_id"], days=7)

# Schedule rotation check
schedule.every().week.do(automated_key_rotation)
```

### Bulk Key Management

```python
import csv
import json

def bulk_create_keys(csv_file: str):
    """Create API keys from CSV file"""
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)

        results = []
        for row in reader:
            try:
                key = security_manager.create_api_key(
                    name=row["name"],
                    scopes=set(row["scopes"].split(",")),
                    rate_limit=int(row["rate_limit"])
                )

                results.append({
                    "name": row["name"],
                    "api_key": key,
                    "status": "created"
                })

            except Exception as e:
                results.append({
                    "name": row["name"],
                    "api_key": None,
                    "status": f"error: {e}"
                })

        # Save results
        with open("key_creation_results.json", "w") as f:
            json.dump(results, f, indent=2)

        return results

# CSV format:
# name,scopes,rate_limit
# app-1,read,1000
# app-2,"read,write",2000
# admin-tool,"read,write,admin",5000
```

## Troubleshooting

### Common Authentication Issues

#### Issue: "Invalid API Key"
```bash
# Check key format
echo "your-api-key" | wc -c  # Should be 32+ characters

# Verify key exists
odoo-mcp --list-api-keys | grep "key-id"

# Test with known good key
curl -H "Authorization: Bearer dev-key-12345" http://localhost:8000/health
```

#### Issue: "Insufficient Permissions"
```bash
# Check key scopes
odoo-mcp --list-api-keys --verbose

# Test scope requirements
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer your-key" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}'  # Requires any scope

curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer your-key" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"2","method":"tools/call","params":{"name":"execute_method","arguments":{"model":"res.partner","method":"search"}}}'  # Requires write scope
```

#### Issue: "Session Expired"
```bash
# Check session timeout configuration
grep session_timeout http_config.json

# Create new session
SESSION_RESPONSE=$(curl -X POST http://localhost:8000/auth/token \
  -H "Authorization: Bearer your-api-key")

SESSION_ID=$(echo "$SESSION_RESPONSE" | jq -r '.session_id')
```

### Debugging Authentication Flow

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Test authentication step by step
def debug_authentication(api_key: str):
    print(f"1. Testing API key format: {len(api_key)} characters")

    # Test health endpoint (no auth required)
    response = requests.get("http://localhost:8000/health")
    print(f"2. Health check: {response.status_code}")

    # Test with API key
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get("http://localhost:8000/health", headers=headers)
    print(f"3. Health check with auth: {response.status_code}")

    # Test MCP endpoint
    payload = {"jsonrpc": "2.0", "id": "test", "method": "tools/list"}
    response = requests.post("http://localhost:8000/mcp", json=payload, headers=headers)
    print(f"4. MCP request: {response.status_code}")

    if response.status_code != 200:
        print(f"   Error: {response.text}")
    else:
        print(f"   Success: {len(response.json().get('result', {}).get('tools', []))} tools")

debug_authentication("your-api-key")
```

For additional troubleshooting, see the [Troubleshooting Guide](TROUBLESHOOTING.md).