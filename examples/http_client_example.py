#!/usr/bin/env python3
"""
Example HTTP client for Odoo MCP Server

This example demonstrates how to connect to and use the Odoo MCP server
over HTTP transport with API key authentication.
"""

import json
import requests
from typing import Dict, Any, Optional


class OdooMCPClient:
    """HTTP client for Odoo MCP server"""

    def __init__(self, base_url: str, api_key: str):
        """
        Initialize the client

        Args:
            base_url: Base URL of the MCP server (e.g., "http://localhost:8000")
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        self.session_id: Optional[str] = None

    def health_check(self) -> Dict[str, Any]:
        """Check server health"""
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    def create_session(self) -> str:
        """Create a new MCP session"""
        response = self.session.post(f"{self.base_url}/auth/token")
        response.raise_for_status()
        data = response.json()
        self.session_id = data["session_id"]
        return self.session_id

    def mcp_request(self, method: str, params: Optional[Dict[str, Any]] = None, request_id: str = "1") -> Dict[str, Any]:
        """
        Send an MCP request

        Args:
            method: MCP method name
            params: Method parameters
            request_id: Request ID

        Returns:
            MCP response
        """
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {}
        }

        headers = {"Content-Type": "application/json"}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        response = self.session.post(
            f"{self.base_url}/mcp",
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        return response.json()

    def list_tools(self) -> Dict[str, Any]:
        """List available tools"""
        return self.mcp_request("tools/list")

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool"""
        return self.mcp_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })

    def list_resources(self) -> Dict[str, Any]:
        """List available resources"""
        return self.mcp_request("resources/list")

    def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a resource"""
        return self.mcp_request("resources/read", {"uri": uri})

    def execute_odoo_method(self, model: str, method: str, args: list = None, kwargs: dict = None) -> Dict[str, Any]:
        """Execute an Odoo method"""
        return self.call_tool("execute_method", {
            "model": model,
            "method": method,
            "args": args or [],
            "kwargs": kwargs or {}
        })

    def search_employee(self, name: str, limit: int = 20) -> Dict[str, Any]:
        """Search for employees"""
        return self.call_tool("search_employee", {
            "name": name,
            "limit": limit
        })

    def search_holidays(self, start_date: str, end_date: str, employee_id: Optional[int] = None) -> Dict[str, Any]:
        """Search for holidays"""
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        if employee_id:
            params["employee_id"] = employee_id

        return self.call_tool("search_holidays", params)


def main():
    """Example usage of the Odoo MCP HTTP client"""

    # Configuration
    SERVER_URL = "http://localhost:8000"
    API_KEY = "odoo_mcp_your_api_key_here"  # Replace with your actual API key

    try:
        # Create client
        client = OdooMCPClient(SERVER_URL, API_KEY)

        # Check server health
        print("🏥 Checking server health...")
        health = client.health_check()
        print(f"Server status: {health['status']}")

        # Create session
        print("\n🔑 Creating session...")
        session_id = client.create_session()
        print(f"Session ID: {session_id}")

        # List available tools
        print("\n🔧 Available tools:")
        tools_response = client.list_tools()
        if "result" in tools_response and "tools" in tools_response["result"]:
            for tool in tools_response["result"]["tools"]:
                print(f"  - {tool['name']}: {tool['description']}")

        # List available resources
        print("\n📚 Available resources:")
        resources_response = client.list_resources()
        if "result" in resources_response and "resources" in resources_response["result"]:
            for resource in resources_response["result"]["resources"]:
                print(f"  - {resource['uri']}: {resource['description']}")

        # Example: Get list of Odoo models
        print("\n📋 Getting Odoo models...")
        models_response = client.read_resource("odoo://models")
        if "result" in models_response:
            models_data = json.loads(models_response["result"]["contents"][0]["text"])
            print(f"Found {len(models_data.get('model_names', []))} models")

        # Example: Execute Odoo method - get users
        print("\n👥 Getting Odoo users...")
        users_response = client.execute_odoo_method(
            "res.users",
            "search_read",
            args=[[["id", ">", 0]]],
            kwargs={"limit": 5, "fields": ["id", "name", "login"]}
        )
        if "result" in users_response:
            result_text = users_response["result"]["content"][0]["text"]
            result_data = json.loads(result_text)
            if result_data.get("success"):
                users = result_data["result"]
                print(f"Found {len(users)} users:")
                for user in users:
                    print(f"  - {user['name']} ({user['login']})")

        # Example: Search employees (if HR module is installed)
        print("\n🧑‍💼 Searching employees...")
        employees_response = client.search_employee("admin")
        if "result" in employees_response:
            result_text = employees_response["result"]["content"][0]["text"]
            result_data = json.loads(result_text)
            if result_data.get("success"):
                employees = result_data.get("result", [])
                print(f"Found {len(employees)} employees matching 'admin'")
            else:
                print(f"Search failed: {result_data.get('error')}")

        print("\n✅ All examples completed successfully!")

    except requests.exceptions.RequestException as e:
        print(f"❌ HTTP request failed: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()