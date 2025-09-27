# Security Configuration

## Important: Credentials Removed

Hardcoded credentials have been removed from the repository for security.

## Setup Instructions

1. **Copy the example config file:**
   ```bash
   cp odoo_config.json.example odoo_config.json
   ```

2. **Edit with your actual credentials:**
   ```bash
   nano odoo_config.json
   ```

3. **Or use environment variables (recommended):**
   ```bash
   export ODOO_URL="https://your-odoo-instance.com"
   export ODOO_DB="your_database_name"
   export ODOO_USERNAME="your_username@example.com"
   export ODOO_PASSWORD="your_password_here"
   ```

## Files to Keep Private

- `odoo_config.json` (contains credentials)
- `odoo_config.json.backup` (backup with original credentials)
- Any files with API keys or passwords

These files are now in .gitignore to prevent accidental commits.