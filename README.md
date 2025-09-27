# Odoo MCP Server with HTTP Transport
(Based on the tuanle96/mcp-odoo, thanks to him for his very good work)

An MCP server implementation that integrates with Odoo ERP systems, enabling AI assistants to interact with Odoo data and functionality through the Model Context Protocol. Now featuring both stdio and HTTP transport layers for maximum flexibility.

## Features

* **Dual Transport Support**: Both stdio (traditional) and HTTP transport layers
* **Comprehensive Odoo Integration**: Full access to Odoo models, records, and methods
* **XML-RPC Communication**: Secure connection to Odoo instances via XML-RPC
* **HTTP Transport Security**: API key authentication, rate limiting, and CORS support
* **Session Management**: Secure session handling for HTTP clients
* **SSL/TLS Support**: HTTPS encryption for production deployments
* **Flexible Configuration**: Support for config files and environment variables
* **Resource Pattern System**: URI-based access to Odoo data structures
* **Error Handling**: Clear error messages for common Odoo API issues
* **Stateless Operations**: Clean request/response cycle for reliable integration

## Tools

* **execute_method**
  * Execute a custom method on an Odoo model
  * Inputs:
    * `model` (string): The model name (e.g., 'res.partner')
    * `method` (string): Method name to execute
    * `args` (optional array): Positional arguments
    * `kwargs` (optional object): Keyword arguments
  * Returns: Dictionary with the method result and success indicator

* **search_employee**
  * Search for employees by name
  * Inputs:
    * `name` (string): The name (or part of the name) to search for
    * `limit` (optional number): The maximum number of results to return (default 20)
  * Returns: Object containing success indicator, list of matching employee names and IDs, and any error message

* **search_holidays**
  * Searches for holidays within a specified date range
  * Inputs:
    * `start_date` (string): Start date in YYYY-MM-DD format
    * `end_date` (string): End date in YYYY-MM-DD format
    * `employee_id` (optional number): Optional employee ID to filter holidays
  * Returns: Object containing success indicator, list of holidays found, and any error message

## Resources

* **odoo://models**
  * Lists all available models in the Odoo system
  * Returns: JSON array of model information

* **odoo://model/{model_name}**
  * Get information about a specific model including fields
  * Example: `odoo://model/res.partner`
  * Returns: JSON object with model metadata and field definitions

* **odoo://record/{model_name}/{record_id}**
  * Get a specific record by ID
  * Example: `odoo://record/res.partner/1`
  * Returns: JSON object with record data

* **odoo://search/{model_name}/{domain}**
  * Search for records that match a domain
  * Example: `odoo://search/res.partner/[["is_company","=",true]]`
  * Returns: JSON array of matching records (limited to 10 by default)

## Configuration

### Odoo Connection Setup

1. Create a configuration file named `odoo_config.json`:

```json
{
  "url": "https://your-odoo-instance.com",
  "db": "your-database-name",
  "username": "your-username",
  "password": "your-password-or-api-key"
}
```

2. Alternatively, use environment variables:
   * `ODOO_URL`: Your Odoo server URL
   * `ODOO_DB`: Database name
   * `ODOO_USERNAME`: Login username
   * `ODOO_PASSWORD`: Password or API key
   * `ODOO_TIMEOUT`: Connection timeout in seconds (default: 30)
   * `ODOO_VERIFY_SSL`: Whether to verify SSL certificates (default: true)
   * `HTTP_PROXY`: Force the ODOO connection to use an HTTP proxy

### HTTP Transport Configuration

For HTTP transport, you can configure additional settings via environment variables or `http_config.json`:

```json
{
  "host": "0.0.0.0",
  "port": 8000,
  "path": "/mcp",
  "require_https": false,
  "allowed_origins": ["*"],
  "ssl_certfile": null,
  "ssl_keyfile": null,
  "default_rate_limit": 1000,
  "session_timeout": 3600
}
```

HTTP environment variables:
* `HTTP_HOST`: Server host (default: 127.0.0.1)
* `HTTP_PORT`: Server port (default: 8000)
* `REQUIRE_HTTPS`: Force HTTPS (default: false)
* `ALLOWED_ORIGINS`: Comma-separated CORS origins (default: *)
* `SSL_CERTFILE`: SSL certificate file path
* `SSL_KEYFILE`: SSL private key file path

### Usage with Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "python",
      "args": [
        "-m",
        "odoo_mcp"
      ],
      "env": {
        "ODOO_URL": "https://your-odoo-instance.com",
        "ODOO_DB": "your-database-name",
        "ODOO_USERNAME": "your-username",
        "ODOO_PASSWORD": "your-password-or-api-key"
      }
    }
  }
}
```

### Docker

```json
{
  "mcpServers": {
    "odoo": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "ODOO_URL",
        "-e",
        "ODOO_DB",
        "-e",
        "ODOO_USERNAME",
        "-e",
        "ODOO_PASSWORD",
        "mcp/odoo"
      ],
    }
  }
}
```

## Installations methods

## 1. Docker Build and Run

Docker build:

```bash
docker build -t mcp/odoo:latest -f Dockerfile .
```

Docker run:

```bash
docker run -i --rm -e ODOO_URL -e ODOO_DB -e ODOO_USERNAME -e ODOO_PASSWORD mcp/odoo
```



### 2. Python Package

```bash
pip install odoo-mcp
```

### Running the Server

#### Stdio Transport (Traditional MCP)

```bash
# Using the installed package (default stdio transport)
odoo-mcp

# Using the MCP development tools
mcp dev odoo_mcp/server.py

# With additional dependencies
mcp dev odoo_mcp/server.py --with pandas --with numpy

# Mount local code for development
mcp dev odoo_mcp/server.py --with-editable .
```

#### HTTP Transport (New)

```bash
# Run HTTP server in development mode
odoo-mcp --transport http --dev

# Run HTTP server with custom host/port
odoo-mcp --transport http --host 0.0.0.0 --port 8080

# Run HTTPS server with SSL certificates
odoo-mcp --transport http --ssl-cert /path/to/cert.pem --ssl-key /path/to/key.pem

# Run with custom configuration file
odoo-mcp --transport http --config http_config.json
```

#### API Key Management

```bash
# Create a new API key
odoo-mcp --create-api-key "my-application"

# List all API keys
odoo-mcp --list-api-keys
```

#### HTTP Transport Usage

Once the HTTP server is running, you can access:

* **Health Check**: `GET http://localhost:8000/health`
* **API Documentation**: `GET http://localhost:8000/docs`
* **MCP Endpoint**: `POST http://localhost:8000/mcp`

Example HTTP request (with API key in URL):
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}' \
  "http://localhost:8000/mcp?api_key=your_api_key_here"
```

Or with Authorization header:
```bash
curl -X POST \
  -H "Authorization: Bearer your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}' \
  http://localhost:8000/mcp
```

**Client Examples:**
* Python client: See `examples/http_client_example.py`
* JavaScript client: See `examples/javascript_client_example.html`



## Parameter Formatting Guidelines

When using the MCP tools for Odoo, pay attention to these parameter formatting guidelines:

1. **Domain Parameter**:
   * The following domain formats are supported:
     * List format: `[["field", "operator", value], ...]`
     * Object format: `{"conditions": [{"field": "...", "operator": "...", "value": "..."}]}`
     * JSON string of either format
   * Examples:
     * List format: `[["is_company", "=", true]]`
     * Object format: `{"conditions": [{"field": "date_order", "operator": ">=", "value": "2025-03-01"}]}`
     * Multiple conditions: `[["date_order", ">=", "2025-03-01"], ["date_order", "<=", "2025-03-31"]]`

2. **Fields Parameter**:
   * Should be an array of field names: `["name", "email", "phone"]`
   * The server will try to parse string inputs as JSON

## License

This MCP server is licensed under the MIT License. 
