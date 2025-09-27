# Troubleshooting Guide: Odoo MCP HTTP Transport

This guide helps you diagnose and resolve common issues with the Odoo MCP HTTP Transport. Each section includes symptoms, root causes, and step-by-step solutions.

## Table of Contents

1. [Error Code Reference](#error-code-reference)
2. [Connection Issues](#connection-issues)
3. [Authentication Problems](#authentication-problems)
4. [Rate Limiting Issues](#rate-limiting-issues)
5. [Odoo Integration Problems](#odoo-integration-problems)
6. [Performance Issues](#performance-issues)
7. [SSL/TLS Problems](#ssltls-problems)
8. [Configuration Issues](#configuration-issues)
9. [Docker Deployment Issues](#docker-deployment-issues)
10. [Claude Code Integration Problems](#claude-code-integration-problems)
11. [Diagnostic Tools](#diagnostic-tools)
12. [Getting Help](#getting-help)

## Error Code Reference

### HTTP Status Codes

| Code | Name | Description | Common Causes | Solution |
|------|------|-------------|---------------|----------|
| 200 | OK | Request successful | - | Normal operation |
| 400 | Bad Request | Invalid request format | Invalid JSON, missing fields | Check request format |
| 401 | Unauthorized | Authentication failed | Invalid/missing API key | Verify API key |
| 403 | Forbidden | Insufficient permissions | Wrong scope, expired key | Check API key scopes |
| 404 | Not Found | Resource not found | Wrong URL, deleted resource | Verify endpoint URL |
| 413 | Payload Too Large | Request too large | Oversized request body | Reduce request size |
| 429 | Too Many Requests | Rate limit exceeded | Too many requests | Wait or increase limits |
| 500 | Internal Server Error | Server error | Server bug, config issue | Check logs |

### JSON-RPC 2.0 Error Codes

| Code | Message | Description | Common Causes |
|------|---------|-------------|---------------|
| -32700 | Parse error | Invalid JSON | Malformed JSON syntax |
| -32600 | Invalid Request | Invalid request object | Missing required fields |
| -32601 | Method not found | Unknown method | Typo in method name |
| -32602 | Invalid params | Invalid parameters | Wrong parameter types |
| -32603 | Internal error | Server error | Internal server issue |

### MCP-Specific Error Codes

| Code | Message | Description | Solution |
|------|---------|-------------|----------|
| -32001 | Authentication required | Missing API key | Add Authorization header |
| -32002 | Invalid API key | API key invalid/expired | Create new API key |
| -32003 | Insufficient permissions | Missing required scope | Update API key scopes |
| -32004 | Rate limit exceeded | Request rate too high | Reduce request rate |
| -32005 | Session expired | Session timeout | Create new session |
| -32006 | Resource not found | URI doesn't exist | Check resource URI |
| -32007 | Tool not found | Tool doesn't exist | Check tool name |
| -32008 | Odoo connection error | Can't connect to Odoo | Check Odoo configuration |

## Connection Issues

### Issue: Connection Refused

**Symptoms:**
- `curl: (7) Failed to connect to localhost port 8000: Connection refused`
- Browser shows "This site can't be reached"
- Client applications timeout

**Diagnosis:**
```bash
# Check if server is running
ps aux | grep odoo-mcp

# Check port binding
netstat -tlnp | grep :8000

# Test health endpoint
curl http://localhost:8000/health
```

**Solutions:**

1. **Server Not Running:**
   ```bash
   # Start the server
   source venv/bin/activate && odoo-mcp --transport http --dev
   ```

2. **Wrong Port/Host:**
   ```bash
   # Check configuration
   cat http_config.json | jq '.port, .host'

   # Start with specific host/port
   odoo-mcp --transport http --host 0.0.0.0 --port 8000
   ```

3. **Firewall Blocking:**
   ```bash
   # Check firewall rules
   sudo ufw status

   # Allow port
   sudo ufw allow 8000/tcp
   ```

### Issue: Server Starts But Doesn't Respond

**Symptoms:**
- Server starts without errors
- Health endpoint returns 200 but MCP endpoints timeout
- Logs show requests arriving but no responses

**Diagnosis:**
```bash
# Check server logs
tail -f logs/server.log

# Test with verbose curl
curl -v http://localhost:8000/mcp \
  -H "Authorization: Bearer test-key" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}'
```

**Solutions:**

1. **Configuration Issue:**
   ```bash
   # Validate configuration
   python -c "
   from src.odoo_mcp.config import load_config
   config = load_config()
   print('Config loaded successfully')
   "
   ```

2. **Odoo Connection Problem:**
   ```bash
   # Test Odoo connection separately
   python -c "
   from src.odoo_mcp.odoo_client import get_odoo_client
   client = get_odoo_client()
   print('Odoo connection successful')
   "
   ```

3. **Memory/Resource Issues:**
   ```bash
   # Check system resources
   free -h
   df -h
   top -p $(pgrep odoo-mcp)
   ```

## Authentication Problems

### Issue: Invalid API Key

**Symptoms:**
- HTTP 401 Unauthorized
- Error: "Invalid API key"
- All authenticated requests fail

**Diagnosis:**
```bash
# List existing API keys
odoo-mcp --list-api-keys

# Test API key format
echo "your-api-key" | wc -c  # Should be 32+ characters

# Check API key in request
curl -H "Authorization: Bearer your-api-key" \
     http://localhost:8000/health
```

**Solutions:**

1. **Create New API Key:**
   ```bash
   # Create API key
   NEW_KEY=$(odoo-mcp --create-api-key "test-app")
   echo "New API key: $NEW_KEY"

   # Test new key
   curl -H "Authorization: Bearer $NEW_KEY" \
        http://localhost:8000/health
   ```

2. **Check Key Format:**
   ```bash
   # Correct format
   Authorization: Bearer abc123def456...

   # Common mistakes
   Authorization: abc123def456...      # Missing "Bearer"
   Authorization: Bearer "abc123..."   # Extra quotes
   ```

3. **Verify Key Exists:**
   ```bash
   # Check if key exists in storage
   python -c "
   from src.odoo_mcp.security import security_manager
   keys = security_manager.list_api_keys()
   for key in keys:
       print(f'{key[\"key_id\"]}: {key[\"name\"]}')
   "
   ```

### Issue: Insufficient Permissions

**Symptoms:**
- HTTP 403 Forbidden
- Error: "Insufficient permissions for tool: execute_method"
- Some endpoints work, others don't

**Diagnosis:**
```bash
# Check API key scopes
odoo-mcp --list-api-keys --verbose

# Test different endpoints
curl -H "Authorization: Bearer your-key" \
     -X POST http://localhost:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}'  # Should work with any scope

curl -H "Authorization: Bearer your-key" \
     -X POST http://localhost:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":"2","method":"tools/call","params":{"name":"execute_method","arguments":{"model":"res.partner","method":"search","args":[]}}}'  # Requires 'write' scope
```

**Solutions:**

1. **Update API Key Scopes:**
   ```bash
   # Get key ID
   KEY_ID=$(odoo-mcp --list-api-keys | jq -r '.api_keys[0].key_id')

   # Update scopes (create new key with correct scopes)
   NEW_KEY=$(odoo-mcp --create-api-key "app-with-write" --scopes read,write)

   # Delete old key
   odoo-mcp --delete-api-key $KEY_ID
   ```

2. **Verify Tool Requirements:**
   ```python
   # Check tool scope requirements
   from src.odoo_mcp.http_transport import HTTPTransport
   transport = HTTPTransport(config, None)

   tools = {
       "execute_method": "write",
       "search_employee": "read",
       "search_holidays": "read"
   }

   for tool, scope in tools.items():
       print(f"{tool} requires '{scope}' scope")
   ```

## Rate Limiting Issues

### Issue: Rate Limit Exceeded

**Symptoms:**
- HTTP 429 Too Many Requests
- Error: "Rate limit exceeded"
- Requests work initially, then fail

**Diagnosis:**
```bash
# Check rate limit headers
curl -I -H "Authorization: Bearer your-key" \
       http://localhost:8000/health

# Look for headers:
# X-RateLimit-Limit: 1000
# X-RateLimit-Remaining: 0
# X-RateLimit-Reset: 1642248000

# Check current usage
python -c "
from src.odoo_mcp.security import security_manager
stats = security_manager.get_usage_stats('your-key-id')
print(f'Requests used: {stats[\"requests_used\"]}/{stats[\"rate_limit\"]}')
"
```

**Solutions:**

1. **Increase Rate Limit:**
   ```bash
   # Create new key with higher limit
   NEW_KEY=$(odoo-mcp --create-api-key "high-volume-app" \
     --rate-limit 5000 \
     --scopes read,write)
   ```

2. **Implement Exponential Backoff:**
   ```python
   import time
   import requests

   def make_request_with_backoff(url, headers, data, max_retries=3):
       for attempt in range(max_retries):
           response = requests.post(url, headers=headers, json=data)

           if response.status_code == 429:
               # Extract retry-after header or use exponential backoff
               wait_time = int(response.headers.get('Retry-After', 2 ** attempt))
               print(f"Rate limited, waiting {wait_time} seconds...")
               time.sleep(wait_time)
               continue

           return response

       raise Exception("Max retries exceeded")
   ```

3. **Monitor Usage:**
   ```bash
   # Monitor rate limit headers
   watch -n 5 'curl -s -I -H "Authorization: Bearer your-key" \
     http://localhost:8000/health | grep -E "X-RateLimit"'
   ```

## Odoo Integration Problems

### Issue: Odoo Connection Failed

**Symptoms:**
- Error: "Odoo connection error"
- XML-RPC errors in logs
- Authentication works but tool calls fail

**Diagnosis:**
```bash
# Test Odoo connectivity
python -c "
import xmlrpc.client
common = xmlrpc.client.ServerProxy('https://your-odoo.com/xmlrpc/2/common')
print(common.version())
"

# Test authentication
python -c "
import xmlrpc.client
common = xmlrpc.client.ServerProxy('https://your-odoo.com/xmlrpc/2/common')
uid = common.authenticate('your-db', 'your-user', 'your-password', {})
print(f'Authenticated as user ID: {uid}')
"

# Test object access
python -c "
from src.odoo_mcp.odoo_client import get_odoo_client
client = get_odoo_client()
models = client.execute('ir.model', 'search', [])
print(f'Found {len(models)} models')
"
```

**Solutions:**

1. **Check Odoo Configuration:**
   ```bash
   # Verify configuration file
   cat odoo_config.json | jq '.'

   # Test with environment variables
   export ODOO_URL="https://your-odoo.com"
   export ODOO_DB="your-database"
   export ODOO_USERNAME="your-username"
   export ODOO_PASSWORD="your-password"

   python -c "from src.odoo_mcp.odoo_client import get_odoo_client; get_odoo_client()"
   ```

2. **Network Connectivity:**
   ```bash
   # Test network access
   curl -I https://your-odoo.com

   # Test specific XML-RPC endpoints
   curl -X POST https://your-odoo.com/xmlrpc/2/common \
     -H "Content-Type: application/xml" \
     -d '<?xml version="1.0"?><methodCall><methodName>version</methodName></methodCall>'
   ```

3. **SSL/Certificate Issues:**
   ```bash
   # Test SSL connection
   openssl s_client -connect your-odoo.com:443 -servername your-odoo.com

   # Disable SSL verification (development only)
   export ODOO_VERIFY_SSL=false
   ```

### Issue: Model Access Errors

**Symptoms:**
- Error: "Access denied"
- Some models work, others don't
- Tools return empty results

**Diagnosis:**
```bash
# Test specific model access
python -c "
from src.odoo_mcp.odoo_client import get_odoo_client
client = get_odoo_client()

# Test different models
models_to_test = ['res.partner', 'res.users', 'sale.order', 'hr.employee']
for model in models_to_test:
    try:
        count = client.execute(model, 'search_count', [])
        print(f'{model}: {count} records')
    except Exception as e:
        print(f'{model}: ERROR - {e}')
"
```

**Solutions:**

1. **Check User Permissions:**
   ```python
   # Check user groups
   from src.odoo_mcp.odoo_client import get_odoo_client
   client = get_odoo_client()

   # Get current user info
   user_info = client.execute('res.users', 'read', [client.uid], ['name', 'groups_id'])
   print("User:", user_info)

   # Check access rights
   for model in ['res.partner', 'sale.order']:
       access = client.execute('ir.model.access', 'search_read',
                              [['model_id.model', '=', model]],
                              ['name', 'perm_read', 'perm_write'])
       print(f"{model} access: {access}")
   ```

2. **Use Appropriate User:**
   ```json
   // Use a user with appropriate permissions
   {
     "username": "admin",  // or a user with full access
     "password": "admin_password"
   }
   ```

3. **Check Record Rules:**
   ```python
   # Check if record rules are blocking access
   try:
       # Try with sudo (if available)
       records = client.execute('sale.order', 'sudo().search_read', [], ['name'])
   except:
       # Use normal search
       records = client.execute('sale.order', 'search_read', [], ['name'])
   ```

## Performance Issues

### Issue: Slow Response Times

**Symptoms:**
- Requests take >5 seconds
- Timeouts in client applications
- High CPU/memory usage

**Diagnosis:**
```bash
# Monitor response times
time curl -H "Authorization: Bearer your-key" \
          http://localhost:8000/mcp \
          -H "Content-Type: application/json" \
          -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}'

# Check system resources
top -p $(pgrep odoo-mcp)
htop

# Monitor network
netstat -i
iftop  # if available
```

**Solutions:**

1. **Increase Timeouts:**
   ```json
   // In odoo_config.json
   {
     "timeout": 60,  // Increase from default 30
     "http_timeout": 120
   }
   ```

2. **Optimize Queries:**
   ```python
   # Instead of loading all fields
   records = client.execute('res.partner', 'search_read', [], [])

   # Load only needed fields
   records = client.execute('res.partner', 'search_read', [], ['name', 'email'])

   # Use limits
   records = client.execute('res.partner', 'search_read', [], ['name'], limit=100)
   ```

3. **Enable Connection Pooling:**
   ```python
   # Configure connection pooling (if supported)
   POOL_SIZE = 5
   POOL_TIMEOUT = 30
   ```

### Issue: Memory Leaks

**Symptoms:**
- Memory usage continuously increases
- Server becomes unresponsive over time
- Out of memory errors

**Diagnosis:**
```bash
# Monitor memory usage
watch -n 5 'ps -p $(pgrep odoo-mcp) -o pid,vsz,rss,comm'

# Check for memory leaks
valgrind --tool=memcheck --leak-check=full python -m src.odoo_mcp
```

**Solutions:**

1. **Restart Periodically:**
   ```bash
   # Add to systemd service
   RuntimeMaxSec=86400  # Restart daily
   ```

2. **Optimize Session Management:**
   ```json
   {
     "session_timeout": 1800,        // 30 minutes instead of 1 hour
     "session_cleanup_interval": 300  // Clean up every 5 minutes
   }
   ```

3. **Limit Request Size:**
   ```json
   {
     "max_request_size": 1048576  // 1MB limit
   }
   ```

## SSL/TLS Problems

### Issue: SSL Certificate Errors

**Symptoms:**
- "SSL certificate verify failed"
- "certificate has expired"
- Browsers show security warnings

**Diagnosis:**
```bash
# Check certificate validity
openssl x509 -in /path/to/cert.pem -text -noout

# Test SSL connection
openssl s_client -connect your-domain.com:443 -servername your-domain.com

# Check certificate chain
curl -vI https://your-domain.com
```

**Solutions:**

1. **Renew Certificate:**
   ```bash
   # Using Let's Encrypt
   sudo certbot renew

   # Manual renewal
   sudo certbot certonly --standalone -d your-domain.com

   # Restart service
   sudo systemctl restart odoo-mcp
   ```

2. **Fix Certificate Chain:**
   ```bash
   # Ensure full chain is used
   cat cert.pem intermediate.pem > fullchain.pem

   # Update configuration
   odoo-mcp --transport http \
     --ssl-cert fullchain.pem \
     --ssl-key privkey.pem
   ```

3. **Test Certificate:**
   ```bash
   # Verify certificate matches private key
   openssl x509 -noout -modulus -in cert.pem | openssl md5
   openssl rsa -noout -modulus -in privkey.pem | openssl md5
   # Outputs should match
   ```

### Issue: TLS Version Errors

**Symptoms:**
- "tlsv1 alert protocol version"
- "SSL handshake failed"
- Clients can't connect despite valid certificates

**Solutions:**

1. **Configure TLS Version:**
   ```json
   {
     "ssl_version": "TLS",  // Allow TLS 1.2+
     "ssl_ciphers": "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS"
   }
   ```

2. **Update SSL Context:**
   ```python
   import ssl
   context = ssl.create_default_context()
   context.minimum_version = ssl.TLSVersion.TLSv1_2
   ```

## Configuration Issues

### Issue: Configuration Not Loaded

**Symptoms:**
- Server uses default settings despite config file
- Environment variables ignored
- Configuration validation errors

**Diagnosis:**
```bash
# Check configuration file syntax
python -c "
import json
with open('http_config.json') as f:
    config = json.load(f)
    print('Configuration valid')
"

# Test configuration loading
python -c "
from src.odoo_mcp.config import load_config
config = load_config()
print('HTTP config:', config.http.__dict__)
"

# Check file permissions
ls -la *config.json
```

**Solutions:**

1. **Fix JSON Syntax:**
   ```bash
   # Validate JSON
   jq . http_config.json

   # Common issues:
   # - Trailing commas
   # - Missing quotes
   # - Wrong data types
   ```

2. **Check File Path:**
   ```bash
   # Specify absolute path
   odoo-mcp --transport http --config /full/path/to/http_config.json

   # Verify current directory
   pwd
   ls -la *.json
   ```

3. **Environment Variable Priority:**
   ```bash
   # Environment variables override config files
   unset HTTP_PORT  # If you want to use config file value

   # Or set explicitly
   export HTTP_PORT=8080
   ```

### Issue: Invalid Configuration Values

**Symptoms:**
- "ValueError: Invalid configuration"
- Server fails to start
- Type validation errors

**Solutions:**

1. **Check Data Types:**
   ```json
   {
     "port": 8000,          // Number, not string
     "require_https": true, // Boolean, not string
     "allowed_origins": [   // Array, not string
       "https://app.com"
     ]
   }
   ```

2. **Validate Ranges:**
   ```json
   {
     "port": 8000,              // 1-65535
     "session_timeout": 3600,   // Positive integer
     "max_request_size": 1048576 // Positive integer
   }
   ```

## Docker Deployment Issues

### Issue: Container Won't Start

**Symptoms:**
- Container exits immediately
- "docker-compose up" fails
- Health checks fail

**Diagnosis:**
```bash
# Check container logs
docker logs odoo-mcp-container

# Check container status
docker ps -a

# Inspect container
docker inspect odoo-mcp-container

# Test image manually
docker run -it --rm odoo-mcp-image bash
```

**Solutions:**

1. **Fix Dockerfile:**
   ```dockerfile
   # Use specific Python version
   FROM python:3.11-slim

   # Install dependencies first
   COPY requirements.txt .
   RUN pip install -r requirements.txt

   # Then copy application
   COPY . .

   # Set proper permissions
   RUN chown -R mcpuser:mcpuser /app
   USER mcpuser
   ```

2. **Environment Variables:**
   ```yaml
   # docker-compose.yml
   environment:
     - ODOO_URL=${ODOO_URL}
     - ODOO_DB=${ODOO_DB}
     - ODOO_USERNAME=${ODOO_USERNAME}
     - ODOO_PASSWORD=${ODOO_PASSWORD}
   ```

3. **Health Check:**
   ```yaml
   healthcheck:
     test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
     interval: 30s
     timeout: 10s
     retries: 3
     start_period: 60s
   ```

### Issue: Network Connectivity

**Symptoms:**
- Container can't reach Odoo
- Port mapping not working
- Services can't communicate

**Solutions:**

1. **Check Network Configuration:**
   ```yaml
   # docker-compose.yml
   networks:
     default:
       external:
         name: bridge

   services:
     odoo-mcp:
       ports:
         - "8000:8000"
       networks:
         - default
   ```

2. **Test Connectivity:**
   ```bash
   # From inside container
   docker exec -it odoo-mcp curl https://your-odoo.com

   # Check DNS resolution
   docker exec -it odoo-mcp nslookup your-odoo.com
   ```

## Claude Code Integration Problems

### Issue: Claude Code Can't Connect

**Symptoms:**
- "Failed to connect to MCP server"
- Authentication errors in Claude Code
- Server appears unreachable

**Diagnosis:**
```bash
# Test server from Claude Code's perspective
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"test","method":"tools/list"}'

# Check if server is accessible from outside localhost
curl -X POST http://your-external-ip:8000/mcp \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"test","method":"tools/list"}'
```

**Solutions:**

1. **Fix Server Binding:**
   ```bash
   # Bind to all interfaces, not just localhost
   odoo-mcp --transport http --host 0.0.0.0 --port 8000
   ```

2. **Correct Claude Code Configuration:**
   ```bash
   # Use IP address if hostname doesn't resolve
   /mcp add http://192.168.1.100:8000/mcp?api_key=your-api-key

   # Or with headers
   /mcp add http://localhost:8000/mcp
   # Authorization: Bearer your-api-key
   ```

3. **Check Firewall:**
   ```bash
   # Allow access from Claude Code's IP range
   sudo ufw allow from claude-code-ip to any port 8000
   ```

### Issue: Authentication Headers Not Working

**Symptoms:**
- Claude Code shows authentication errors
- Manual curl works but Claude Code doesn't
- Intermittent authentication failures

**Solutions:**

1. **Use Query Parameter Method:**
   ```bash
   # Include API key in URL
   /mcp add http://localhost:8000/mcp?api_key=your-api-key-here
   ```

2. **Verify Header Format:**
   ```bash
   # Correct format
   Authorization: Bearer your-api-key-here

   # Not
   Authorization: your-api-key-here
   ```

3. **Check API Key Permissions:**
   ```bash
   # Ensure key has correct scopes
   odoo-mcp --list-api-keys --verbose
   ```

## Diagnostic Tools

### Built-in Diagnostics

```bash
# Health check endpoint
curl http://localhost:8000/health

# List all API keys
odoo-mcp --list-api-keys

# Test configuration
odoo-mcp --test-config

# Validate Odoo connection
python -c "
from src.odoo_mcp.odoo_client import get_odoo_client
client = get_odoo_client()
print('Odoo connection successful')
"
```

### Log Analysis

```bash
# Monitor logs in real-time
tail -f logs/server.log

# Filter for errors
grep -i error logs/server.log

# Search for specific patterns
grep "rate.limit" logs/security.log

# Analyze access patterns
awk '{print $1}' logs/access.log | sort | uniq -c | sort -nr
```

### Network Debugging

```bash
# Check open ports
netstat -tulpn | grep :8000

# Monitor network traffic
tcpdump -i any port 8000

# Test SSL/TLS
nmap --script ssl-enum-ciphers -p 443 your-domain.com
```

### Performance Monitoring

```bash
# Monitor resource usage
htop
iostat -x 1
vmstat 1

# Check memory usage
free -h
pmap $(pgrep odoo-mcp)

# Monitor API response times
while true; do
  time curl -s -o /dev/null \
    -H "Authorization: Bearer your-key" \
    http://localhost:8000/health
  sleep 1
done
```

## Getting Help

### Before Seeking Help

1. **Check the logs:**
   ```bash
   tail -100 logs/server.log
   tail -100 logs/error.log
   ```

2. **Test basic connectivity:**
   ```bash
   curl http://localhost:8000/health
   ```

3. **Verify configuration:**
   ```bash
   cat http_config.json | jq .
   ```

4. **Document the issue:**
   - What were you trying to do?
   - What exactly happened?
   - What did you expect to happen?
   - Steps to reproduce
   - Relevant log entries

### Support Channels

1. **GitHub Issues:**
   - Create detailed issue reports
   - Include configuration (redact sensitive data)
   - Attach relevant logs

2. **Community Forums:**
   - Search existing discussions
   - Provide context for your use case

3. **Documentation:**
   - [API Reference](API_REFERENCE.md)
   - [Security Guide](SECURITY.md)
   - [Quick Start](QUICK_START.md)

### Creating Bug Reports

**Template:**
```markdown
## Environment
- OS: Ubuntu 20.04
- Python: 3.11.2
- Package version: 1.0.0
- Odoo version: 15.0

## Configuration
```json
{
  "host": "localhost",
  "port": 8000,
  // ... redacted sensitive values
}
```

## Steps to Reproduce
1. Start server with `odoo-mcp --transport http`
2. Make request to `/mcp` endpoint
3. Observe error

## Expected Behavior
Should return list of tools

## Actual Behavior
Returns 500 Internal Server Error

## Logs
```
2024-01-15 10:30:00 ERROR: Connection failed
...
```

## Additional Context
This worked in version 0.9.0
```

This troubleshooting guide covers the most common issues. For additional help, consult the [API Reference](API_REFERENCE.md) or create an issue on GitHub with detailed information about your problem.