"""
Command line entry point for the Odoo MCP Server
"""

import argparse
import os
import sys
import traceback

from .server import mcp


def main() -> int:
    """
    Run the MCP server with transport selection
    """
    parser = argparse.ArgumentParser(description="Odoo MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport method (default: stdio)",
    )

    # HTTP transport options
    parser.add_argument(
        "--host", default="127.0.0.1", help="HTTP host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="HTTP port (default: 8000)"
    )
    parser.add_argument("--config", help="HTTP configuration file path")
    parser.add_argument("--ssl-cert", help="SSL certificate file path")
    parser.add_argument("--ssl-key", help="SSL key file path")
    parser.add_argument("--cors-origins", help="Comma-separated allowed CORS origins")
    parser.add_argument(
        "--dev", action="store_true", help="Run HTTP transport in development mode"
    )

    # API key management
    parser.add_argument("--create-api-key", help="Create a new API key with given name")
    parser.add_argument(
        "--list-api-keys", action="store_true", help="List all API keys"
    )

    args = parser.parse_args()

    try:
        print("=== ODOO MCP SERVER STARTING ===", file=sys.stderr)
        print(f"Python version: {sys.version}", file=sys.stderr)
        print(f"Transport: {args.transport}", file=sys.stderr)

        # Handle API key management
        if args.create_api_key:
            from .security import security_manager

            key = security_manager.create_api_key(
                name=args.create_api_key, scopes={"read", "write"}, rate_limit=1000
            )
            print(f"Created API key: {key}")
            print("Store this key securely. It cannot be retrieved again.")
            return 0

        if args.list_api_keys:
            from .security import security_manager

            keys = security_manager.list_api_keys()
            print("API Keys:")
            for key in keys:
                print(
                    f"  {key['name']} (ID: {key['key_id']}) - Scopes: {key['scopes']}"
                )
            return 0

        print("Environment variables:", file=sys.stderr)
        for key, value in os.environ.items():
            if key.startswith("ODOO_"):
                if key == "ODOO_PASSWORD":
                    print(f"  {key}: ***hidden***", file=sys.stderr)
                else:
                    print(f"  {key}: {value}", file=sys.stderr)

        if args.transport == "stdio":
            print("Starting MCP server with stdio transport...", file=sys.stderr)
            sys.stderr.flush()

            # Use the run() method for stdio transport
            mcp.run()

        elif args.transport == "http":
            print("Starting MCP server with HTTP transport...", file=sys.stderr)
            sys.stderr.flush()

            # Use HTTP transport
            from .http_server import run_http_server

            run_http_server(
                host=args.host,
                port=args.port,
                config_file=args.config,
                ssl_cert=args.ssl_cert,
                ssl_key=args.ssl_key,
                cors_origins=args.cors_origins if not args.dev else "*",
            )

        print("MCP server stopped normally", file=sys.stderr)
        return 0

    except KeyboardInterrupt:
        print("MCP server stopped by user", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"Error starting server: {e}", file=sys.stderr)
        print("Exception details:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
