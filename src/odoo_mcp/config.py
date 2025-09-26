"""
Configuration management for Odoo MCP server

Handles both Odoo connection configuration and HTTP transport settings
"""

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class OdooConfig:
    """Odoo connection configuration"""

    url: str
    db: str
    username: str
    password: str
    timeout: int = 30
    verify_ssl: bool = True
    force_http_proxy: bool = False

    @classmethod
    def from_env(cls) -> "OdooConfig":
        """Load configuration from environment variables"""
        return cls(
            url=os.getenv("ODOO_URL", ""),
            db=os.getenv("ODOO_DB", ""),
            username=os.getenv("ODOO_USERNAME", ""),
            password=os.getenv("ODOO_PASSWORD", ""),
            timeout=int(os.getenv("ODOO_TIMEOUT", "30")),
            verify_ssl=os.getenv("ODOO_VERIFY_SSL", "true").lower() == "true",
            force_http_proxy=os.getenv("HTTP_PROXY", "").lower() == "true",
        )

    @classmethod
    def from_file(cls, config_path: str = "odoo_config.json") -> "OdooConfig":
        """Load configuration from JSON file"""
        try:
            with open(config_path, "r") as f:
                config_data = json.load(f)
            return cls(**config_data)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")

    def is_valid(self) -> bool:
        """Check if configuration is valid"""
        required_fields = ["url", "db", "username", "password"]
        return all(getattr(self, field) for field in required_fields)


@dataclass
class HTTPConfig:
    """HTTP transport configuration"""

    # Server settings
    host: str = "127.0.0.1"
    port: int = 8000
    path: str = "/mcp"

    # Security settings
    require_https: bool = False
    allowed_origins: List[str] = field(default_factory=lambda: ["*"])
    api_key_header: str = "Authorization"

    # TLS/SSL settings
    ssl_certfile: Optional[str] = None
    ssl_keyfile: Optional[str] = None
    ssl_ca_certs: Optional[str] = None

    # Rate limiting
    default_rate_limit: int = 1000  # requests per hour
    rate_limit_storage: str = "memory"  # "memory" or "redis"

    # Session settings
    session_timeout: int = 3600  # 1 hour in seconds
    max_sessions: int = 100

    # CORS settings
    allow_credentials: bool = True
    allow_methods: List[str] = field(default_factory=lambda: ["GET", "POST", "OPTIONS"])
    allow_headers: List[str] = field(
        default_factory=lambda: [
            "Authorization",
            "Content-Type",
            "Mcp-Session-Id",
            "Accept",
        ]
    )
    expose_headers: List[str] = field(
        default_factory=lambda: ["Mcp-Session-Id", "Content-Type"]
    )
    max_age: int = 600  # CORS preflight cache time

    # Request settings
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    request_timeout: int = 300  # 5 minutes

    @classmethod
    def from_env(cls) -> "HTTPConfig":
        """Load HTTP configuration from environment variables"""
        return cls(
            host=os.getenv("HTTP_HOST", "127.0.0.1"),
            port=int(os.getenv("HTTP_PORT", "8000")),
            path=os.getenv("HTTP_PATH", "/mcp"),
            require_https=os.getenv("REQUIRE_HTTPS", "false").lower() == "true",
            allowed_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
            ssl_certfile=os.getenv("SSL_CERTFILE"),
            ssl_keyfile=os.getenv("SSL_KEYFILE"),
            ssl_ca_certs=os.getenv("SSL_CA_CERTS"),
            default_rate_limit=int(os.getenv("DEFAULT_RATE_LIMIT", "1000")),
            session_timeout=int(os.getenv("SESSION_TIMEOUT", "3600")),
            max_sessions=int(os.getenv("MAX_SESSIONS", "100")),
            max_request_size=int(os.getenv("MAX_REQUEST_SIZE", str(10 * 1024 * 1024))),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "300")),
        )

    @classmethod
    def from_file(cls, config_path: str = "http_config.json") -> "HTTPConfig":
        """Load HTTP configuration from JSON file"""
        try:
            with open(config_path, "r") as f:
                config_data = json.load(f)
            return cls(**config_data)
        except FileNotFoundError:
            # Return default configuration if file doesn't exist
            return cls()
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in HTTP configuration file: {e}")

    def get_ssl_context(self) -> Optional[dict]:
        """Get SSL context configuration for uvicorn"""
        if self.ssl_certfile and self.ssl_keyfile:
            ssl_config = {
                "ssl_certfile": self.ssl_certfile,
                "ssl_keyfile": self.ssl_keyfile,
            }
            if self.ssl_ca_certs:
                ssl_config["ssl_ca_certs"] = self.ssl_ca_certs
            return ssl_config
        return None

    def is_ssl_enabled(self) -> bool:
        """Check if SSL is enabled"""
        return bool(self.ssl_certfile and self.ssl_keyfile)


@dataclass
class AppConfig:
    """Complete application configuration"""

    odoo: OdooConfig
    http: HTTPConfig

    @classmethod
    def load(
        cls,
        odoo_config_path: str = "odoo_config.json",
        http_config_path: str = "http_config.json",
        prefer_env: bool = True,
    ) -> "AppConfig":
        """
        Load complete application configuration

        Args:
            odoo_config_path: Path to Odoo configuration file
            http_config_path: Path to HTTP configuration file
            prefer_env: Whether to prefer environment variables over file config

        Returns:
            Complete application configuration
        """
        if prefer_env:
            # Try environment first, fall back to files
            try:
                odoo_config = OdooConfig.from_env()
                if not odoo_config.is_valid():
                    odoo_config = OdooConfig.from_file(odoo_config_path)
            except FileNotFoundError:
                odoo_config = OdooConfig.from_env()

            http_config = HTTPConfig.from_env()
        else:
            # Try files first, fall back to environment
            try:
                odoo_config = OdooConfig.from_file(odoo_config_path)
            except FileNotFoundError:
                odoo_config = OdooConfig.from_env()

            try:
                http_config = HTTPConfig.from_file(http_config_path)
            except FileNotFoundError:
                http_config = HTTPConfig.from_env()

        return cls(odoo=odoo_config, http=http_config)

    def save_http_config(self, config_path: str = "http_config.json") -> None:
        """Save HTTP configuration to file"""
        config_dict = {
            "host": self.http.host,
            "port": self.http.port,
            "path": self.http.path,
            "require_https": self.http.require_https,
            "allowed_origins": self.http.allowed_origins,
            "ssl_certfile": self.http.ssl_certfile,
            "ssl_keyfile": self.http.ssl_keyfile,
            "ssl_ca_certs": self.http.ssl_ca_certs,
            "default_rate_limit": self.http.default_rate_limit,
            "session_timeout": self.http.session_timeout,
            "max_sessions": self.http.max_sessions,
            "allow_credentials": self.http.allow_credentials,
            "allow_methods": self.http.allow_methods,
            "allow_headers": self.http.allow_headers,
            "expose_headers": self.http.expose_headers,
            "max_age": self.http.max_age,
            "max_request_size": self.http.max_request_size,
            "request_timeout": self.http.request_timeout,
        }

        with open(config_path, "w") as f:
            json.dump(config_dict, f, indent=2)

    def validate(self) -> None:
        """Validate the complete configuration"""
        if not self.odoo.is_valid():
            raise ValueError("Invalid Odoo configuration")

        if self.http.require_https and not self.http.is_ssl_enabled():
            raise ValueError(
                "HTTPS is required but SSL certificates are not configured"
            )

        if self.http.port < 1 or self.http.port > 65535:
            raise ValueError("Invalid HTTP port number")


def get_config() -> AppConfig:
    """Get application configuration using default paths and precedence"""
    return AppConfig.load()


def create_default_http_config() -> None:
    """Create a default HTTP configuration file"""
    config = HTTPConfig()
    app_config = AppConfig(odoo=OdooConfig.from_env(), http=config)
    app_config.save_http_config()
    print("Created default HTTP configuration file: http_config.json")


if __name__ == "__main__":
    # CLI for creating default config
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "create-http-config":
        create_default_http_config()
    else:
        config = get_config()
        print("Current configuration:")
        print(f"Odoo URL: {config.odoo.url}")
        print(f"HTTP Server: {config.http.host}:{config.http.port}{config.http.path}")
        print(f"HTTPS: {'Enabled' if config.http.is_ssl_enabled() else 'Disabled'}")
