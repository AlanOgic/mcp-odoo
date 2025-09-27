# Quick Start Guide: Odoo MCP HTTP Transport

Get up and running with the Odoo MCP HTTP Transport in minutes. This guide provides step-by-step instructions for common deployment scenarios.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Basic Setup](#basic-setup)
3. [Development Mode](#development-mode)
4. [Production Setup](#production-setup)
5. [Claude Code Integration](#claude-code-integration)
6. [Docker Deployment](#docker-deployment)
7. [Common Use Cases](#common-use-cases)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements
- Python 3.8 or higher
- Access to an Odoo instance (version 13+)
- Network connectivity between MCP server and Odoo
- 512MB RAM minimum (2GB recommended for production)

### Odoo Requirements
- Valid Odoo user account with appropriate permissions
- XML-RPC access enabled (default in most Odoo installations)
- Database user with read/write access to required models

## Basic Setup

### 1. Installation

#### From PyPI (Recommended)
```bash
pip install odoo-mcp
```

#### From Source
```bash
git clone https://github.com/your-org/mcp-odoo.git
cd mcp-odoo
pip install -e '.[dev]'
```

### 2. Configuration

#### Create Odoo Configuration
```bash
# Copy example configuration
cp odoo_config.json.example odoo_config.json

# Edit configuration
nano odoo_config.json
```

**odoo_config.json:**
```json
{
  "url": "https://your-odoo-instance.com",
  "database": "your-database-name",
  "username": "your-username",
  "password": "your-password",
  "timeout": 30,
  "verify_ssl": true
}
```

#### Environment Variables (Alternative)
```bash
export ODOO_URL="https://your-odoo-instance.com"
export ODOO_DB="your-database-name"
export ODOO_USERNAME="your-username"
export ODOO_PASSWORD="your-password"
```

### 3. Test Connection

#### Verify Odoo Connectivity
```bash
# Test basic connectivity
python -c "
from src.odoo_mcp.odoo_client import get_odoo_client
client = get_odoo_client()
models = client.execute('ir.model', 'search_read', [], ['name'])
print(f'Connected! Found {len(models)} models.')
"
```

## Development Mode

Perfect for testing and development with minimal setup.

### 1. Start Development Server

```bash
# Quick start with default settings
source venv/bin/activate && odoo-mcp --transport http --dev

# Server starts at http://localhost:8000
# Automatically creates default API key: 'dev-key-12345'
```

### 2. Test the API

```bash
# Health check
curl http://localhost:8000/health

# List tools (requires API key)
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer dev-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tools/list"
  }'
```

### 3. Interactive Documentation

Visit http://localhost:8000/docs for interactive API documentation.

## Production Setup

### 1. Create Production Configuration

**http_config.json:**
```json
{
  "host": "0.0.0.0",
  "port": 8000,
  "require_https": true,
  "ssl_certfile": "/etc/ssl/certs/your-cert.pem",
  "ssl_keyfile": "/etc/ssl/private/your-key.pem",
  "allowed_origins": [
    "https://your-app.com",
    "https://api.your-app.com"
  ],
  "default_rate_limit": 1000,
  "session_timeout": 3600,
  "max_request_size": 1048576
}
```

### 2. SSL Certificate Setup

#### Using Let's Encrypt
```bash
# Install certbot
sudo apt-get install certbot

# Get certificate
sudo certbot certonly --standalone -d your-domain.com

# Certificates will be in /etc/letsencrypt/live/your-domain.com/
```

### 3. Create Production API Keys

```bash
# Create API key for your application
API_KEY=$(odoo-mcp --create-api-key "production-app" \
  --scopes read,write \
  --rate-limit 2000)

echo "Store this API key securely: $API_KEY"
```

### 4. Start Production Server

```bash
# Start with production configuration
source venv/bin/activate && odoo-mcp \
  --transport http \
  --config http_config.json \
  --host 0.0.0.0 \
  --port 443 \
  --ssl-cert /etc/letsencrypt/live/your-domain.com/fullchain.pem \
  --ssl-key /etc/letsencrypt/live/your-domain.com/privkey.pem
```

### 5. Systemd Service (Recommended)

**/etc/systemd/system/odoo-mcp.service:**
```ini
[Unit]
Description=Odoo MCP HTTP Server
After=network.target

[Service]
Type=simple
User=mcp
Group=mcp
WorkingDirectory=/opt/odoo-mcp
Environment=PATH=/opt/odoo-mcp/venv/bin
Environment=ODOO_URL=https://your-odoo.com
Environment=ODOO_DB=production
Environment=ODOO_USERNAME=api_user
EnvironmentFile=/etc/odoo-mcp/environment
ExecStart=/opt/odoo-mcp/venv/bin/odoo-mcp --transport http --config /etc/odoo-mcp/http_config.json
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable odoo-mcp
sudo systemctl start odoo-mcp
sudo systemctl status odoo-mcp
```

## Claude Code Integration

### 1. Start MCP Server

```bash
# Development
odoo-mcp --transport http --dev

# Production
odoo-mcp --transport http --config http_config.json
```

### 2. Add to Claude Code

#### Option 1: URL with API Key
```bash
# In Claude Code terminal
/mcp add http://localhost:8000/mcp?api_key=your-api-key-here
```

#### Option 2: Headers Authentication
```bash
# Add server with authentication headers
/mcp add http://localhost:8000/mcp
# When prompted for headers:
# Header Name: Authorization
# Header Value: Bearer your-api-key-here
```

### 3. Verify Connection

```bash
# Test the connection in Claude Code
/mcp list-servers
/mcp test odoo-mcp
```

### 4. Example Usage in Claude Code

Once connected, you can use natural language to interact with Odoo:

```
"List all customers with names containing 'Tech'"
"Show me the latest 5 sales orders"
"Create a new partner with name 'Acme Corp' and email 'contact@acme.com'"
```

## Docker Deployment

### 1. Basic Docker Setup

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1001 mcpuser

# Install dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY *.json ./

# Set ownership
RUN chown -R mcpuser:mcpuser /app
USER mcpuser

# Expose port
EXPOSE 8000

# Start command
CMD ["odoo-mcp", "--transport", "http", "--host", "0.0.0.0"]
```

### 2. Docker Compose

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  odoo-mcp:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ODOO_URL=https://your-odoo.com
      - ODOO_DB=production
      - ODOO_USERNAME=api_user
      - ODOO_PASSWORD=${ODOO_PASSWORD}
      - HTTP_HOST=0.0.0.0
      - HTTP_PORT=8000
      - DEFAULT_RATE_LIMIT=1000
    volumes:
      - ./logs:/app/logs
      - ./http_config.json:/app/http_config.json
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - /etc/letsencrypt:/etc/letsencrypt
    depends_on:
      - odoo-mcp
    restart: unless-stopped
```

### 3. Production Docker with SSL

**nginx.conf:**
```nginx
events {
    worker_connections 1024;
}

http {
    upstream odoo-mcp {
        server odoo-mcp:8000;
    }

    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

        location / {
            proxy_pass http://odoo-mcp;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

### 4. Start Docker Services

```bash
# Create environment file
echo "ODOO_PASSWORD=your-secure-password" > .env

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f odoo-mcp
```

## Common Use Cases

### 1. API Integration

#### Python Client
```python
import requests
import json

BASE_URL = "https://your-domain.com"
API_KEY = "your-api-key"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Search for customers
response = requests.post(f"{BASE_URL}/mcp",
    headers=headers,
    json={
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/call",
        "params": {
            "name": "execute_method",
            "arguments": {
                "model": "res.partner",
                "method": "search_read",
                "args": [["is_company", "=", True]],
                "kwargs": {"fields": ["name", "email", "phone"]}
            }
        }
    }
)

customers = response.json()
print(json.dumps(customers, indent=2))
```

### 2. Reporting Dashboard

#### JavaScript/Node.js
```javascript
const axios = require('axios');

class OdooMCPClient {
    constructor(baseURL, apiKey) {
        this.baseURL = baseURL;
        this.headers = {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
        };
    }

    async callTool(toolName, args) {
        const response = await axios.post(`${this.baseURL}/mcp`, {
            jsonrpc: '2.0',
            id: Date.now().toString(),
            method: 'tools/call',
            params: {
                name: toolName,
                arguments: args
            }
        }, { headers: this.headers });

        return response.data.result;
    }

    async getSalesReport(startDate, endDate) {
        return this.callTool('execute_method', {
            model: 'sale.order',
            method: 'search_read',
            args: [
                ['&', ['date_order', '>=', startDate], ['date_order', '<=', endDate]]
            ],
            kwargs: {
                fields: ['name', 'partner_id', 'amount_total', 'date_order']
            }
        });
    }
}

// Usage
const client = new OdooMCPClient('https://your-domain.com', 'your-api-key');
client.getSalesReport('2024-01-01', '2024-01-31')
    .then(orders => console.log('Sales Orders:', orders))
    .catch(err => console.error('Error:', err));
```

### 3. Data Synchronization

#### Batch Processing
```python
import asyncio
import aiohttp

class OdooMCPSyncer:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

    async def sync_customers(self, external_customers):
        async with aiohttp.ClientSession() as session:
            tasks = []
            for customer in external_customers:
                task = self.create_or_update_customer(session, customer)
                tasks.append(task)

            results = await asyncio.gather(*tasks)
            return results

    async def create_or_update_customer(self, session, customer_data):
        # Implementation for customer sync
        payload = {
            "jsonrpc": "2.0",
            "id": f"sync-{customer_data['external_id']}",
            "method": "tools/call",
            "params": {
                "name": "execute_method",
                "arguments": {
                    "model": "res.partner",
                    "method": "create",
                    "args": [customer_data]
                }
            }
        }

        async with session.post(f"{self.base_url}/mcp",
                              json=payload,
                              headers=self.headers) as response:
            return await response.json()
```

## Troubleshooting

### Common Issues

#### 1. Connection Refused
```bash
# Check if server is running
curl http://localhost:8000/health

# Check logs
tail -f logs/server.log

# Verify configuration
odoo-mcp --test-config
```

#### 2. Authentication Errors
```bash
# Verify API key format
echo "Authorization: Bearer your-api-key" | base64 -d

# List existing API keys
odoo-mcp --list-api-keys

# Test authentication
curl -H "Authorization: Bearer your-api-key" \
     http://localhost:8000/health
```

#### 3. Odoo Connection Issues
```bash
# Test Odoo connectivity
python -c "
import requests
response = requests.post('https://your-odoo.com/xmlrpc/2/common',
    headers={'Content-Type': 'application/xml'},
    data='''<?xml version=\"1.0\"?>
<methodCall>
    <methodName>version</methodName>
</methodCall>''')
print(response.text)
"
```

#### 4. Rate Limiting
```bash
# Check rate limit headers
curl -I -H "Authorization: Bearer your-api-key" \
       http://localhost:8000/mcp

# Increase rate limit
odoo-mcp --update-api-key your-key-id --rate-limit 5000
```

#### 5. SSL Certificate Issues
```bash
# Test SSL configuration
openssl s_client -connect your-domain.com:443 -servername your-domain.com

# Verify certificate chain
openssl verify -CApath /etc/ssl/certs/ /path/to/your/cert.pem

# Check certificate expiration
openssl x509 -in /path/to/cert.pem -noout -dates
```

### Debug Mode

#### Enable Verbose Logging
```bash
# Start with debug logging
export LOG_LEVEL=DEBUG
odoo-mcp --transport http --dev

# Or use configuration
cat > debug_config.json << EOF
{
  "log_level": "DEBUG",
  "log_file": "logs/debug.log"
}
EOF
```

#### Health Checks
```bash
# Comprehensive health check
curl -v http://localhost:8000/health

# Test MCP protocol
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"test","method":"tools/list"}'
```

### Performance Tuning

#### Optimize for High Load
```json
{
  "max_request_size": 5242880,
  "session_cleanup_interval": 60,
  "default_rate_limit": 5000,
  "worker_processes": 4,
  "worker_connections": 1000
}
```

#### Monitor Performance
```bash
# Monitor requests per second
watch 'curl -s http://localhost:8000/health | jq .timestamp'

# Check memory usage
ps aux | grep odoo-mcp

# Monitor connections
netstat -an | grep :8000
```

## Next Steps

1. **Read the [API Reference](API_REFERENCE.md)** for detailed endpoint documentation
2. **Review [Security Best Practices](SECURITY.md)** for production deployment
3. **Check the [Examples](examples/)** directory for more integration patterns
4. **Join the Community** for support and updates

## Support

- **Documentation**: [Complete Documentation](README.md)
- **Issues**: [GitHub Issues](https://github.com/anthropics/claude-code/issues)
- **Community**: [Discord/Slack/Forum](your-community-link)
- **Email**: support@your-company.com