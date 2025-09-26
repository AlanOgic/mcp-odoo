"""
HTTP Server entry point for Odoo MCP

Provides a standalone HTTP server for the Odoo MCP with secure transport
"""

import asyncio
import signal
import sys
from typing import Optional

import uvicorn

from .config import AppConfig
from .http_transport import HTTPTransport
from .security import security_manager
from .server import mcp


class HTTPServer:
    """HTTP server wrapper with lifecycle management"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.transport = HTTPTransport(config.http, mcp)
        self.app = self.transport.app
        self.server: Optional[uvicorn.Server] = None
        self.cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the HTTP server"""
        # Setup graceful shutdown
        self._setup_signal_handlers()

        # Start session cleanup task
        self.cleanup_task = asyncio.create_task(self._periodic_cleanup())

        # Configure uvicorn
        uvicorn_config = uvicorn.Config(
            app=self.app,
            host=self.config.http.host,
            port=self.config.http.port,
            log_level="info",
            access_log=True,
        )

        # Add SSL configuration if available
        ssl_config = self.config.http.get_ssl_context()
        if ssl_config:
            uvicorn_config.ssl_certfile = ssl_config["ssl_certfile"]
            uvicorn_config.ssl_keyfile = ssl_config["ssl_keyfile"]
            if "ssl_ca_certs" in ssl_config:
                uvicorn_config.ssl_ca_certs = ssl_config["ssl_ca_certs"]

        self.server = uvicorn.Server(uvicorn_config)

        print("Starting Odoo MCP HTTP server...")
        print(
            f"URL: {'https' if ssl_config else 'http'}://{self.config.http.host}:{self.config.http.port}{self.config.http.path}"
        )
        print(
            f"Health check: {'https' if ssl_config else 'http'}://{self.config.http.host}:{self.config.http.port}/health"
        )
        print(
            f"API documentation: {'https' if ssl_config else 'http'}://{self.config.http.host}:{self.config.http.port}/docs"
        )

        # Display default API key for development
        api_keys = security_manager.list_api_keys()
        if api_keys:
            print("\nDefault API key available for testing:")
            print(
                "Note: In production, create dedicated API keys with appropriate scopes"
            )

        await self.server.serve()

    async def stop(self):
        """Stop the HTTP server"""
        print("\nShutting down HTTP server...")

        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        if self.server:
            self.server.should_exit = True

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            print(f"\nReceived signal {signum}, shutting down...")
            asyncio.create_task(self.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _periodic_cleanup(self):
        """Periodic cleanup task for expired sessions"""
        while True:
            try:
                await asyncio.sleep(300)  # Clean up every 5 minutes
                self.transport.cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in cleanup task: {e}")


def run_http_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    config_file: Optional[str] = None,
    ssl_cert: Optional[str] = None,
    ssl_key: Optional[str] = None,
    cors_origins: Optional[str] = None,
):
    """
    Run the HTTP server with command line options

    Args:
        host: Host to bind to
        port: Port to bind to
        config_file: Path to HTTP configuration file
        ssl_cert: SSL certificate file path
        ssl_key: SSL key file path
        cors_origins: Comma-separated list of allowed CORS origins
    """
    try:
        # Load configuration
        if config_file:
            config = AppConfig.load(http_config_path=config_file)
        else:
            config = AppConfig.load()

        # Override with command line arguments
        config.http.host = host
        config.http.port = port

        if ssl_cert and ssl_key:
            config.http.ssl_certfile = ssl_cert
            config.http.ssl_keyfile = ssl_key
            config.http.require_https = True

        if cors_origins:
            config.http.allowed_origins = [
                origin.strip() for origin in cors_origins.split(",")
            ]

        # Validate configuration
        config.validate()

        # Create and start server
        server = HTTPServer(config)

        # Run the server
        asyncio.run(server.start())

    except KeyboardInterrupt:
        print("\nShutdown complete")
    except Exception as e:
        print(f"Server error: {e}")
        sys.exit(1)


async def create_development_server():
    """Create a development server for testing"""
    from .config import HTTPConfig

    # Development configuration
    http_config = HTTPConfig(
        host="127.0.0.1",
        port=8000,
        allowed_origins=["*"],
        require_https=False,
    )

    config = AppConfig.load()
    config.http = http_config

    server = HTTPServer(config)
    return server


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Odoo MCP HTTP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--config", help="HTTP configuration file path")
    parser.add_argument("--ssl-cert", help="SSL certificate file path")
    parser.add_argument("--ssl-key", help="SSL key file path")
    parser.add_argument("--cors-origins", help="Comma-separated allowed CORS origins")
    parser.add_argument("--dev", action="store_true", help="Run in development mode")

    args = parser.parse_args()

    if args.dev:
        print("Running in development mode...")
        args.host = "127.0.0.1"
        args.cors_origins = "*"

    run_http_server(
        host=args.host,
        port=args.port,
        config_file=args.config,
        ssl_cert=args.ssl_cert,
        ssl_key=args.ssl_key,
        cors_origins=args.cors_origins,
    )
