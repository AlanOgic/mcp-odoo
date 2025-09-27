# Security Best Practices for Odoo MCP HTTP Transport

This document outlines security best practices, considerations, and guidelines for deploying and using the Odoo MCP HTTP Transport in production environments.

## Table of Contents

1. [Authentication & Authorization](#authentication--authorization)
2. [API Key Management](#api-key-management)
3. [Network Security](#network-security)
4. [Rate Limiting & Abuse Prevention](#rate-limiting--abuse-prevention)
5. [Session Management](#session-management)
6. [Production Deployment](#production-deployment)
7. [Monitoring & Logging](#monitoring--logging)
8. [Incident Response](#incident-response)
9. [Security Checklist](#security-checklist)

## Authentication & Authorization

### API Key Security

#### Generation
- API keys are generated using cryptographically secure random number generators
- Keys are hashed using bcrypt with a cost factor of 12 before storage
- Original keys are never stored in plaintext
- Key generation includes sufficient entropy (recommended: 32+ bytes)

#### Storage
```bash
# Secure storage in environment variables
export ODOO_MCP_API_KEY="your-secure-api-key"

# Or in secure configuration files (600 permissions)
chmod 600 /etc/odoo-mcp/config.json
```

#### Best Practices
- **Never expose API keys in client-side code**
- **Use environment variables or secure key management systems**
- **Rotate keys regularly (recommended: every 90 days)**
- **Use different keys for different environments (dev/staging/prod)**
- **Implement key expiration policies**

### Scope-Based Access Control

#### Available Scopes
- `read`: Search, list, and retrieve operations
- `write`: Create, update, delete, and execute operations
- `admin`: Manage API keys, sessions, and system administration

#### Principle of Least Privilege
```python
# Example: Create read-only API key for reporting applications
api_key = security_manager.create_api_key(
    name="reporting-dashboard",
    scopes={"read"},  # Only read access
    rate_limit=500
)

# Example: Limited write access for integration services
api_key = security_manager.create_api_key(
    name="integration-service",
    scopes={"read", "write"},  # No admin access
    rate_limit=2000
)
```

#### Scope Validation
- All endpoints validate required scopes before processing
- Tools automatically check scope requirements:
  - `execute_method`: Requires `write` scope
  - `search_employee`: Requires `read` scope
  - `search_holidays`: Requires `read` scope
- Administrative endpoints require `admin` scope

## API Key Management

### Key Lifecycle

#### Creation
```bash
# Create API key with specific scopes and rate limits
odoo-mcp --create-api-key "production-app" \
  --scopes read,write \
  --rate-limit 1000
```

#### Rotation
```bash
# 1. Create new API key
NEW_KEY=$(odoo-mcp --create-api-key "production-app-v2" --scopes read,write)

# 2. Update applications to use new key
# 3. Monitor usage to ensure transition
# 4. Delete old key after confirmation
odoo-mcp --delete-api-key "old-key-id"
```

#### Monitoring
```bash
# List all API keys with usage statistics
odoo-mcp --list-api-keys --verbose

# Monitor key usage
tail -f logs/security.log | grep "api_key_usage"
```

### Key Compromise Response

#### Immediate Actions
1. **Revoke compromised key immediately**
2. **Audit access logs for suspicious activity**
3. **Rotate related credentials (Odoo passwords, certificates)**
4. **Update all applications with new keys**
5. **Monitor for unusual activity patterns**

#### Investigation
```bash
# Audit log analysis
grep "compromised-key-id" logs/access.log | \
  grep -E "(tools/call|resources/read)" | \
  awk '{print $1, $4, $7}' | sort | uniq -c
```

## Network Security

### HTTPS/TLS Configuration

#### Production Setup
```bash
# Start with SSL certificates
odoo-mcp --transport http \
  --ssl-cert /path/to/cert.pem \
  --ssl-key /path/to/key.pem \
  --require-https true \
  --host 0.0.0.0 \
  --port 443
```

#### Certificate Management
```bash
# Use Let's Encrypt for automatic certificate renewal
certbot certonly --standalone -d your-domain.com

# Configure automatic renewal
echo "0 2 * * * certbot renew --quiet" | crontab -
```

#### TLS Configuration
```json
{
  "tls_version": "1.2+",
  "cipher_suites": [
    "ECDHE-RSA-AES256-GCM-SHA384",
    "ECDHE-RSA-AES128-GCM-SHA256"
  ],
  "hsts_enabled": true,
  "hsts_max_age": 31536000
}
```

### CORS Security

#### Secure CORS Configuration
```json
{
  "allowed_origins": [
    "https://your-app.com",
    "https://staging.your-app.com"
  ],
  "allow_credentials": true,
  "allow_methods": ["POST", "GET", "DELETE"],
  "allow_headers": ["Authorization", "Content-Type", "Mcp-Session-Id"],
  "max_age": 86400
}
```

#### Development vs Production
```bash
# Development (permissive)
export ALLOWED_ORIGINS="*"

# Production (restrictive)
export ALLOWED_ORIGINS="https://your-app.com,https://api.your-app.com"
```

### Firewall Configuration

#### Port Access
```bash
# Only allow necessary ports
ufw default deny incoming
ufw default allow outgoing
ufw allow 443/tcp  # HTTPS
ufw allow 22/tcp   # SSH (from specific IPs only)
ufw enable
```

#### IP Whitelisting
```bash
# Restrict access to specific IP ranges
ufw allow from 10.0.0.0/8 to any port 443
ufw allow from 192.168.0.0/16 to any port 443
```

## Rate Limiting & Abuse Prevention

### Rate Limiting Strategy

#### Per-Key Limits
```python
# Configure rate limits based on usage patterns
rate_limits = {
    "reporting": 100,      # Low-frequency reporting
    "integration": 1000,   # Normal API usage
    "batch_processing": 5000,  # High-volume processing
    "admin": 10000         # Administrative operations
}
```

#### Burst Protection
```python
# Implement burst protection
BURST_LIMIT = 10  # Maximum requests per second
SUSTAINED_LIMIT = 1000  # Maximum requests per hour
```

### Abuse Detection

#### Suspicious Patterns
```python
# Monitor for abuse patterns
abuse_indicators = [
    "excessive_error_rates",      # >50% error rate
    "unusual_access_patterns",    # Access outside normal hours
    "rapid_successive_requests",  # >100 requests/minute
    "invalid_authentication",     # Multiple auth failures
    "resource_enumeration"        # Systematic resource scanning
]
```

#### Automated Response
```python
# Automatic blocking for severe abuse
if detect_abuse(api_key):
    temporary_block(api_key, duration="1h")
    alert_administrators(api_key, reason="abuse_detected")
```

### DDoS Protection

#### Application Layer
```python
# Request size limits
MAX_REQUEST_SIZE = 1024 * 1024  # 1MB
MAX_REQUESTS_PER_IP = 100       # Per minute

# Connection limits
MAX_CONCURRENT_CONNECTIONS = 1000
```

#### Infrastructure Layer
```bash
# Use reverse proxy for additional protection
nginx_config = """
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req zone=api burst=20 nodelay;
"""
```

## Session Management

### Session Security

#### Configuration
```json
{
  "session_timeout": 3600,        // 1 hour
  "session_cleanup_interval": 300, // 5 minutes
  "max_sessions_per_key": 10,     // Prevent session exhaustion
  "secure_session_ids": true      // Cryptographically secure IDs
}
```

#### Session Validation
```python
def validate_session(session_id: str, api_key: str) -> bool:
    """Validate session security"""
    session = get_session(session_id)

    if not session:
        return False

    # Check expiration
    if session.is_expired():
        cleanup_session(session_id)
        return False

    # Verify ownership
    if session.api_key_id != api_key.key_id:
        log_security_event("session_hijack_attempt", session_id, api_key)
        return False

    return True
```

### Session Hijacking Prevention

#### Secure Session IDs
- Generated using cryptographically secure random number generators
- Minimum 128 bits of entropy
- No predictable patterns
- Regularly rotated

#### Session Binding
```python
# Bind sessions to client characteristics
session_binding = {
    "user_agent": request.headers.get("User-Agent"),
    "ip_address": request.client.host,
    "api_key_fingerprint": hash(api_key)
}
```

## Production Deployment

### Infrastructure Security

#### Reverse Proxy Configuration
```nginx
server {
    listen 443 ssl http2;
    server_name api.your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Container Security
```dockerfile
# Use non-root user
FROM python:3.11-slim
RUN useradd -m -u 1001 mcpuser
USER mcpuser

# Security scanning
RUN pip install safety
RUN safety check

# Minimal attack surface
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
```

#### Environment Security
```bash
# Secure environment variables
export ODOO_URL="https://your-odoo.com"
export ODOO_DB="production"
export ODOO_USERNAME="api_user"
export ODOO_PASSWORD="$(cat /run/secrets/odoo_password)"

# File permissions
chmod 600 /etc/odoo-mcp/config.json
chown root:root /etc/odoo-mcp/config.json
```

### Secrets Management

#### HashiCorp Vault Integration
```python
import hvac

# Initialize Vault client
client = hvac.Client(url='https://vault.your-company.com')
client.token = os.environ['VAULT_TOKEN']

# Retrieve secrets
secrets = client.secrets.kv.v2.read_secret_version(path='odoo-mcp/prod')
odoo_password = secrets['data']['data']['odoo_password']
```

#### AWS Secrets Manager
```python
import boto3

# Retrieve secrets from AWS
client = boto3.client('secretsmanager', region_name='us-east-1')
secret = client.get_secret_value(SecretId='odoo-mcp/production')
credentials = json.loads(secret['SecretString'])
```

### Network Isolation

#### VPC Configuration
```bash
# Isolate MCP server in private subnet
vpc_config = {
    "private_subnet": "10.0.1.0/24",
    "public_subnet": "10.0.2.0/24",
    "nat_gateway": true,
    "security_groups": {
        "mcp_server": {
            "ingress": [
                {"port": 8000, "source": "load_balancer_sg"}
            ]
        }
    }
}
```

## Monitoring & Logging

### Security Logging

#### Log Configuration
```python
SECURITY_LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    "handlers": {
        "file": {
            "filename": "/var/log/odoo-mcp/security.log",
            "max_bytes": 10485760,  # 10MB
            "backup_count": 5
        },
        "syslog": {
            "address": "/dev/log",
            "facility": "auth"
        }
    }
}
```

#### Security Events
```python
security_events = [
    "authentication_failure",
    "authorization_failure",
    "rate_limit_exceeded",
    "session_expired",
    "invalid_api_key",
    "suspicious_activity",
    "admin_action",
    "key_rotation",
    "session_hijack_attempt"
]
```

### Alerting

#### Critical Alerts
```python
# Configure alerts for critical security events
alerts = {
    "authentication_failures": {
        "threshold": 10,
        "window": "5m",
        "action": "notify_admins"
    },
    "rate_limit_exceeded": {
        "threshold": 5,
        "window": "1m",
        "action": "temporary_block"
    },
    "admin_actions": {
        "threshold": 1,
        "window": "1s",
        "action": "audit_log"
    }
}
```

### Metrics & Monitoring

#### Security Metrics
```python
security_metrics = [
    "authentication_success_rate",
    "authorization_failure_count",
    "rate_limit_hit_rate",
    "session_creation_rate",
    "api_key_usage_distribution",
    "error_rate_by_endpoint",
    "response_time_percentiles"
]
```

#### Dashboard Configuration
```python
# Grafana dashboard queries
queries = {
    "auth_failures": "rate(authentication_failures_total[5m])",
    "rate_limits": "rate(rate_limit_exceeded_total[5m])",
    "response_times": "histogram_quantile(0.95, response_time_seconds)"
}
```

## Incident Response

### Security Incident Playbook

#### Incident Classification
```python
incident_severity = {
    "critical": [
        "data_breach",
        "privilege_escalation",
        "system_compromise"
    ],
    "high": [
        "authentication_bypass",
        "unauthorized_access",
        "ddos_attack"
    ],
    "medium": [
        "rate_limit_abuse",
        "suspicious_activity",
        "policy_violation"
    ]
}
```

#### Response Procedures

##### Critical Incidents
1. **Immediate Response (0-15 minutes)**
   - Isolate affected systems
   - Revoke compromised credentials
   - Enable additional logging
   - Notify incident response team

2. **Assessment (15-60 minutes)**
   - Determine scope of compromise
   - Identify affected data/systems
   - Document timeline of events
   - Preserve evidence

3. **Containment (1-4 hours)**
   - Implement temporary controls
   - Block malicious IP addresses
   - Rotate all potentially compromised keys
   - Update firewall rules

4. **Recovery (4-24 hours)**
   - Restore from clean backups
   - Apply security patches
   - Verify system integrity
   - Gradually restore service

5. **Post-Incident (24+ hours)**
   - Conduct lessons learned session
   - Update security procedures
   - Improve monitoring and detection
   - Communicate with stakeholders

### Forensics

#### Log Preservation
```bash
# Preserve logs for forensic analysis
tar -czf incident-logs-$(date +%Y%m%d).tar.gz \
  /var/log/odoo-mcp/ \
  /var/log/nginx/ \
  /var/log/auth.log
```

#### Evidence Collection
```python
def collect_incident_evidence(incident_id: str):
    """Collect evidence for security incident"""
    evidence = {
        "system_state": capture_system_state(),
        "network_connections": capture_network_state(),
        "process_list": capture_process_list(),
        "file_integrity": run_integrity_check(),
        "log_snapshots": collect_relevant_logs(incident_id),
        "memory_dump": create_memory_dump()  # If warranted
    }
    return evidence
```

## Security Checklist

### Pre-Deployment Checklist

#### Authentication & Authorization
- [ ] API keys use sufficient entropy (32+ bytes)
- [ ] Keys are hashed with bcrypt (cost factor 12+)
- [ ] Scope-based access control implemented
- [ ] Principle of least privilege enforced
- [ ] Key rotation procedures documented

#### Network Security
- [ ] HTTPS/TLS properly configured
- [ ] Valid SSL certificates installed
- [ ] CORS policy restricts origins appropriately
- [ ] Firewall rules limit access to necessary ports
- [ ] DDoS protection mechanisms in place

#### Application Security
- [ ] Rate limiting configured per API key
- [ ] Request size limits enforced
- [ ] Input validation implemented
- [ ] Error messages don't leak sensitive data
- [ ] Security headers configured

#### Infrastructure Security
- [ ] Server hardening completed
- [ ] Non-root user configured for application
- [ ] File permissions properly set
- [ ] Secrets management system in use
- [ ] Network isolation implemented

#### Monitoring & Logging
- [ ] Security event logging enabled
- [ ] Log retention policy defined
- [ ] Alerting rules configured
- [ ] Monitoring dashboards created
- [ ] Incident response procedures documented

### Runtime Security Checklist

#### Daily
- [ ] Review security alerts
- [ ] Check error rates and patterns
- [ ] Monitor rate limit violations
- [ ] Verify certificate expiration dates

#### Weekly
- [ ] Analyze access patterns for anomalies
- [ ] Review API key usage statistics
- [ ] Check system resource utilization
- [ ] Update threat intelligence feeds

#### Monthly
- [ ] Rotate API keys
- [ ] Review and update security policies
- [ ] Conduct security metrics review
- [ ] Test incident response procedures

#### Quarterly
- [ ] Conduct security assessment
- [ ] Review access controls and permissions
- [ ] Update security documentation
- [ ] Perform penetration testing

### Compliance Considerations

#### Data Protection
- [ ] Data encryption in transit (TLS 1.2+)
- [ ] API key management procedures
- [ ] Access logging and audit trails
- [ ] Data retention policies

#### Industry Standards
- [ ] OWASP security guidelines followed
- [ ] ISO 27001 controls considered
- [ ] SOC 2 Type II requirements addressed
- [ ] GDPR compliance for EU users

## Additional Resources

### Security Tools
- **SAST**: Use static analysis tools for code scanning
- **DAST**: Implement dynamic security testing
- **Dependency Scanning**: Regular vulnerability scanning of dependencies
- **Container Scanning**: Security scanning of container images

### Security Training
- **Secure Coding**: Developer training on secure coding practices
- **Incident Response**: Regular incident response drills
- **Security Awareness**: General security awareness training
- **Threat Modeling**: Application threat modeling exercises

### External Resources
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [CIS Controls](https://www.cisecurity.org/controls)
- [SANS Security Policies](https://www.sans.org/information-security-policy/)

## Contact Information

For security issues and vulnerabilities:
- **Security Team**: security@your-company.com
- **Emergency Contact**: +1-XXX-XXX-XXXX
- **Bug Bounty Program**: https://bugbounty.your-company.com