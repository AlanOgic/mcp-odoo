# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an MCP (Model Context Protocol) server implementation for Odoo ERP integration. It provides a bridge between AI assistants and Odoo systems through XML-RPC communication, allowing AI agents to query and interact with Odoo data.

## Development Commands

### Setup and Installation
```bash
# Create virtual environment and install in development mode
python3 -m venv venv
source venv/bin/activate
pip install -e '.[dev]'

# Copy and configure Odoo connection
cp odoo_config.json.example odoo_config.json
# Edit odoo_config.json with your Odoo instance details
```

### Running the Server

#### Stdio Transport (Default)
```bash
# Run using the package entry point (stdio transport)
source venv/bin/activate && odoo-mcp

# Alternative: Run using the development script with logging
source venv/bin/activate && python run_server.py

# Run using MCP dev tools
mcp dev odoo_mcp/server.py
```

#### HTTP Transport (New)
```bash
# Run HTTP server in development mode
source venv/bin/activate && odoo-mcp --transport http --dev

# Run HTTP server with custom host/port
source venv/bin/activate && odoo-mcp --transport http --host 0.0.0.0 --port 8080

# Run HTTPS server with SSL certificates
source venv/bin/activate && odoo-mcp --transport http --ssl-cert /path/to/cert.pem --ssl-key /path/to/key.pem

# Run with custom configuration file
source venv/bin/activate && odoo-mcp --transport http --config http_config.json
```

#### API Key Management
```bash
# Create a new API key
source venv/bin/activate && odoo-mcp --create-api-key "my-application"

# List all API keys
source venv/bin/activate && odoo-mcp --list-api-keys
```

### Code Quality Tools
```bash
# Format code with black
black src/

# Sort imports
isort src/

# Type checking
mypy src/

# Linting with ruff
ruff check src/

# Fix linting issues automatically
ruff check --fix src/
```

### Building and Publishing
```bash
# Build package
python -m build

# Upload to PyPI (requires credentials)
twine upload dist/*
```

## Architecture

### Core Components

1. **FastMCP Server** (`src/odoo_mcp/server.py`):
   - Built using the FastMCP framework from the MCP SDK
   - Implements MCP resources (URI-based access patterns) and tools (function calls)
   - Uses an async context manager for lifecycle management
   - Entry point: `mcp` FastMCP instance

2. **Odoo Client** (`src/odoo_mcp/odoo_client.py`):
   - XML-RPC client wrapper for Odoo communication
   - Handles authentication, connection management, and SSL verification
   - Implements redirect handling and timeout management
   - Singleton pattern via `get_odoo_client()` function

3. **HTTP Transport** (`src/odoo_mcp/http_transport.py`):
   - FastAPI-based HTTP server implementing MCP over HTTP
   - Supports both JSON and Server-Sent Events for streaming
   - Full MCP protocol compatibility with JSON-RPC 2.0
   - Session management and streaming responses

4. **Security System** (`src/odoo_mcp/security.py`):
   - API key-based authentication with bcrypt hashing
   - Rate limiting (requests per hour) per API key
   - Scope-based authorization (read/write/admin)
   - Session management with configurable timeouts

5. **Configuration Management** (`src/odoo_mcp/config.py`):
   - Unified configuration for both Odoo and HTTP transport
   - Environment variable and file-based configuration
   - SSL/TLS configuration support
   - CORS and security settings

6. **Entry Points**:
   - `__main__.py`: Package entry point supporting both stdio and HTTP transports
   - `run_server.py`: Development server with enhanced logging using stdio transport
   - `http_server.py`: Standalone HTTP server with SSL and production features

### MCP Resources (URI-based patterns)

- `odoo://models` - List all available Odoo models
- `odoo://model/{model_name}` - Get model metadata and fields
- `odoo://record/{model_name}/{record_id}` - Fetch specific record
- `odoo://search/{model_name}/{domain}` - Search records with domain filters

### MCP Tools (Function calls)

- `execute_method` - Execute any Odoo model method with args/kwargs
- `search_employee` - Search employees by name
- `search_holidays` - Search time-off records by date range

### Configuration

#### Odoo Configuration
The server reads Odoo configuration from (in order of precedence):
1. Environment variables (`ODOO_URL`, `ODOO_DB`, `ODOO_USERNAME`, `ODOO_PASSWORD`)
2. `odoo_config.json` file in the project root

Additional Odoo environment variables:
- `ODOO_TIMEOUT` - Connection timeout in seconds (default: 30)
- `ODOO_VERIFY_SSL` - SSL verification flag (default: true)
- `HTTP_PROXY` - Force HTTP proxy usage

#### HTTP Transport Configuration
HTTP transport configuration can be set via:
1. Environment variables (see below)
2. `http_config.json` file in the project root
3. Command line arguments (override all other settings)

HTTP environment variables:
- `HTTP_HOST` - Server host (default: 127.0.0.1)
- `HTTP_PORT` - Server port (default: 8000)
- `HTTP_PATH` - MCP endpoint path (default: /mcp)
- `REQUIRE_HTTPS` - Force HTTPS (default: false)
- `ALLOWED_ORIGINS` - Comma-separated CORS origins (default: *)
- `SSL_CERTFILE` - SSL certificate file path
- `SSL_KEYFILE` - SSL private key file path
- `DEFAULT_RATE_LIMIT` - Default requests per hour (default: 1000)
- `SESSION_TIMEOUT` - Session timeout in seconds (default: 3600)

#### Configuration Files
```bash
# Copy and customize HTTP configuration
cp http_config.json.example http_config.json

# For production with HTTPS
cp http_config_production.json.example http_config.json
```

### Key Design Patterns

1. **FastMCP Decorators**: Resources and tools are registered using `@mcp.resource()` and `@mcp.tool()` decorators
2. **Context Management**: Application context (`AppContext`) holds the Odoo client instance
3. **Domain Parsing**: Flexible domain parameter handling supporting list, object, and JSON string formats
4. **Error Handling**: Clear error messages with context for debugging Odoo API issues

## HTTP Transport Usage

### Authentication
All HTTP requests require an API key in the Authorization header:
```bash
curl -H "Authorization: Bearer your_api_key_here" \
     http://localhost:8000/health
```

### Available Endpoints
- `GET /health` - Health check (no auth required)
- `POST /auth/token` - Create session (returns session ID)
- `POST /mcp` - Main MCP endpoint (JSON-RPC 2.0)
- `GET /mcp/sessions` - List active sessions (admin only)
- `DELETE /mcp/sessions/{id}` - Delete session
- `GET /api-keys` - List API keys (admin only)
- `POST /api-keys` - Create API key (admin only)
- `GET /docs` - Interactive API documentation

### Session Management
```bash
# Create a session
curl -X POST -H "Authorization: Bearer your_api_key" \
     http://localhost:8000/auth/token

# Use session ID in subsequent requests
curl -X POST -H "Authorization: Bearer your_api_key" \
     -H "Mcp-Session-Id: session_id_here" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}' \
     http://localhost:8000/mcp
```

### Client Examples
- Python client: `examples/http_client_example.py`
- JavaScript client: `examples/javascript_client_example.html`

### Security Features
- **API Key Authentication**: Secure bcrypt-hashed API keys
- **Rate Limiting**: Configurable requests per hour per API key
- **CORS Support**: Configurable origin restrictions
- **Session Management**: Secure session handling with timeouts
- **HTTPS Support**: TLS/SSL encryption for production
- **Scope-based Authorization**: Fine-grained access control

## Important Notes

- The server uses XML-RPC protocol for Odoo communication (endpoints: `/xmlrpc/2/common` and `/xmlrpc/2/object`)
- Authentication happens on client initialization and persists for the session
- All Odoo operations are stateless - each request is independent
- The FastMCP framework handles MCP protocol implementation details
- Logs are written to `logs/` directory when using `run_server.py`
- HTTP transport supports both JSON and Server-Sent Events for streaming responses
- Default API key is created automatically in development mode