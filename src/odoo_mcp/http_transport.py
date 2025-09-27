"""
HTTP Transport for Odoo MCP Server

Implements the MCP HTTP transport specification with FastAPI,
supporting both JSON and Server-Sent Events for streaming responses.
"""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .config import AppConfig, HTTPConfig
from .security import APIKey, APIKeyAuth, security_manager


class MCPRequest(BaseModel):
    """MCP request model following JSON-RPC 2.0 specification"""

    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: Optional[Union[str, int]] = Field(description="Request ID")
    method: str = Field(description="Method name")
    params: Optional[Dict[str, Any]] = Field(
        default=None, description="Method parameters"
    )


class MCPResponse(BaseModel):
    """MCP response model following JSON-RPC 2.0 specification"""

    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: Optional[Union[str, int]] = Field(description="Request ID")
    result: Optional[Any] = Field(default=None, description="Method result")
    error: Optional[Dict[str, Any]] = Field(
        default=None, description="Error information"
    )


class MCPError(BaseModel):
    """MCP error model"""

    code: int = Field(description="Error code")
    message: str = Field(description="Error message")
    data: Optional[Any] = Field(default=None, description="Additional error data")


class SessionInfo(BaseModel):
    """MCP session information"""

    session_id: str = Field(description="Session ID")
    created_at: datetime = Field(description="Session creation time")
    last_activity: datetime = Field(description="Last activity time")
    api_key_id: str = Field(description="Associated API key ID")
    client_info: Optional[Dict[str, Any]] = Field(
        default=None, description="Client information"
    )


class HTTPTransport:
    """HTTP Transport implementation for MCP"""

    def __init__(self, config: HTTPConfig, mcp_server: Any) -> None:
        self.config = config
        self.mcp_server = mcp_server
        self.sessions: Dict[str, SessionInfo] = {}
        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        """Create and configure FastAPI application"""

        @asynccontextmanager
        async def lifespan(app: FastAPI):  # type: ignore
            """Application lifespan manager"""
            print(
                f"Starting HTTP transport server on {self.config.host}:{self.config.port}"
            )
            yield
            print("Shutting down HTTP transport server")

        app = FastAPI(
            title="Odoo MCP HTTP Server",
            description="HTTP transport for Odoo Model Context Protocol server",
            version="1.0.0",
            lifespan=lifespan,
        )

        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.allowed_origins,
            allow_credentials=self.config.allow_credentials,
            allow_methods=self.config.allow_methods,
            allow_headers=self.config.allow_headers,
            expose_headers=self.config.expose_headers,
            max_age=self.config.max_age,
        )

        # Add request size middleware
        @app.middleware("http")
        async def limit_request_size(request: Request, call_next):  # type: ignore
            """Middleware to limit request size"""
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.config.max_request_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"Request too large. Maximum size: {self.config.max_request_size} bytes",
                )
            return await call_next(request)

        # Authentication dependency
        auth = APIKeyAuth()

        # Routes
        @app.get("/health")
        async def health_check() -> Dict[str, Any]:
            """Health check endpoint"""
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0",
            }

        @app.post("/auth/token")
        async def create_token(api_key: APIKey = Depends(auth)) -> Dict[str, Any]:
            """Create a new session token"""
            session_id = str(uuid.uuid4())
            session_info = SessionInfo(
                session_id=session_id,
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                api_key_id=api_key.key_id,
            )
            self.sessions[session_id] = session_info

            return {"session_id": session_id, "expires_in": self.config.session_timeout}

        @app.post(self.config.path)
        async def mcp_endpoint(  # type: ignore
            request: Request,
            mcp_request: MCPRequest,
            session_id: Optional[str] = None,
            api_key: APIKey = Depends(auth),
        ):
            """Main MCP endpoint for handling requests"""

            # Get session ID from header if not in body
            if not session_id:
                session_id = request.headers.get("mcp-session-id")

            # Validate session if provided
            if session_id and session_id in self.sessions:
                session = self.sessions[session_id]
                session.last_activity = datetime.utcnow()

                # Check session timeout
                if (
                    datetime.utcnow() - session.created_at
                ).total_seconds() > self.config.session_timeout:
                    del self.sessions[session_id]
                    raise HTTPException(status_code=401, detail="Session expired")

            # Process MCP request
            try:
                result = await self._process_mcp_request(mcp_request, api_key)

                # Check if client accepts streaming
                accept_header = request.headers.get("accept", "")
                if "text/event-stream" in accept_header and isinstance(
                    result.result, list
                ):
                    # Stream multiple results
                    return StreamingResponse(
                        self._stream_results(result, mcp_request.id),
                        media_type="text/event-stream",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                        },
                    )
                else:
                    # Return single JSON response
                    response_headers = {}
                    if session_id:
                        response_headers["Mcp-Session-Id"] = session_id

                    return JSONResponse(
                        content=result.dict(exclude_none=True), headers=response_headers
                    )

            except Exception as e:
                error_response = MCPResponse(
                    id=mcp_request.id,
                    error=MCPError(
                        code=-32603, message="Internal error", data=str(e)
                    ).dict(),
                )
                return JSONResponse(
                    content=error_response.dict(exclude_none=True), status_code=500
                )

        @app.get(f"{self.config.path}/sessions")
        async def list_sessions(
            api_key: APIKey = Depends(auth),
        ) -> Dict[str, List[Dict[str, Any]]]:
            """List active sessions (admin only)"""
            if "admin" not in api_key.scopes:
                raise HTTPException(status_code=403, detail="Admin access required")

            return {
                "sessions": [
                    {
                        "session_id": session.session_id,
                        "created_at": session.created_at.isoformat(),
                        "last_activity": session.last_activity.isoformat(),
                        "api_key_id": session.api_key_id,
                    }
                    for session in self.sessions.values()
                ]
            }

        @app.delete(f"{self.config.path}/sessions/{{session_id}}")
        async def delete_session(
            session_id: str, api_key: APIKey = Depends(auth)
        ) -> Dict[str, str]:
            """Delete a session"""
            if session_id not in self.sessions:
                raise HTTPException(status_code=404, detail="Session not found")

            session = self.sessions[session_id]

            # Check if user can delete this session
            if session.api_key_id != api_key.key_id and "admin" not in api_key.scopes:
                raise HTTPException(
                    status_code=403,
                    detail="Cannot delete session owned by another user",
                )

            del self.sessions[session_id]
            return {"message": "Session deleted"}

        @app.get("/api-keys")
        async def list_api_keys(
            api_key: APIKey = Depends(auth),
        ) -> Dict[str, List[Dict[str, Any]]]:
            """List API keys (admin only)"""
            if "admin" not in api_key.scopes:
                raise HTTPException(status_code=403, detail="Admin access required")

            return {"api_keys": security_manager.list_api_keys()}

        @app.post("/api-keys")
        async def create_api_key(
            name: str,
            scopes: List[str] = [],
            rate_limit: int = 1000,
            api_key: APIKey = Depends(auth),
        ) -> Dict[str, Any]:
            """Create a new API key (admin only)"""
            if "admin" not in api_key.scopes:
                raise HTTPException(status_code=403, detail="Admin access required")

            new_key = security_manager.create_api_key(
                name=name, scopes=set(scopes), rate_limit=rate_limit
            )

            return {
                "message": "API key created successfully",
                "api_key": new_key,
                "warning": "Store this key securely. It cannot be retrieved again.",
            }

        return app

    async def _process_mcp_request(
        self, request: MCPRequest, api_key: APIKey
    ) -> MCPResponse:
        """Process an MCP request and return response"""

        # Map MCP methods to server functions
        if request.method == "tools/list":
            # List available tools
            tools = self._get_available_tools()
            return MCPResponse(id=request.id, result={"tools": tools})

        elif request.method == "tools/call":
            # Call a tool
            if not request.params or "name" not in request.params:
                raise ValueError("Missing tool name")

            tool_name = request.params["name"]
            tool_args = request.params.get("arguments", {})

            # Check if user has permission for this tool
            required_scope = self._get_tool_scope(tool_name)
            if required_scope and required_scope not in api_key.scopes:
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions for tool: {tool_name}",
                )

            result = await self._call_tool(tool_name, tool_args)
            return MCPResponse(id=request.id, result=result)

        elif request.method == "resources/list":
            # List available resources
            resources = self._get_available_resources()
            return MCPResponse(id=request.id, result={"resources": resources})

        elif request.method == "resources/read":
            # Read a resource
            if not request.params or "uri" not in request.params:
                raise ValueError("Missing resource URI")

            uri = request.params["uri"]
            result = await self._read_resource(uri)
            return MCPResponse(id=request.id, result=result)

        else:
            raise ValueError(f"Unknown method: {request.method}")

    def _get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools from MCP server"""
        # This would integrate with your existing MCP server
        # For now, return a basic list
        return [
            {
                "name": "execute_method",
                "description": "Execute a custom method on an Odoo model",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "method": {"type": "string"},
                        "args": {"type": "array"},
                        "kwargs": {"type": "object"},
                    },
                    "required": ["model", "method"],
                },
            },
            {
                "name": "search_employee",
                "description": "Search for employees by name",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "limit": {"type": "integer", "default": 20},
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "search_holidays",
                "description": "Search for holidays within a date range",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"},
                        "employee_id": {"type": "integer"},
                    },
                    "required": ["start_date", "end_date"],
                },
            },
        ]

    def _get_available_resources(self) -> List[Dict[str, Any]]:
        """Get list of available resources from MCP server"""
        return [
            {
                "uri": "odoo://models",
                "name": "List all available models",
                "description": "List all available models in the Odoo system",
                "mimeType": "application/json",
            },
            {
                "uri": "odoo://model/{model_name}",
                "name": "Get model information",
                "description": "Get detailed information about a specific model",
                "mimeType": "application/json",
            },
            {
                "uri": "odoo://record/{model_name}/{record_id}",
                "name": "Get record information",
                "description": "Get detailed information of a specific record by ID",
                "mimeType": "application/json",
            },
            {
                "uri": "odoo://search/{model_name}/{domain}",
                "name": "Search records",
                "description": "Search for records matching the domain",
                "mimeType": "application/json",
            },
        ]

    def _get_tool_scope(self, tool_name: str) -> Optional[str]:
        """Get required scope for a tool"""
        scope_mapping = {
            "execute_method": "write",
            "search_employee": "read",
            "search_holidays": "read",
        }
        return scope_mapping.get(tool_name)

    async def _call_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool and return the result"""
        try:
            # Create a mock context for the tool call
            from mcp.server.fastmcp import Context

            from .odoo_client import get_odoo_client
            from .server import AppContext

            # Create app context
            app_context = AppContext(odoo=get_odoo_client())

            # Create mock request context
            class MockRequestContext:
                def __init__(self, lifespan_context):
                    self.lifespan_context = lifespan_context

            # Create mock context
            mock_context: Any = Context(request_context=MockRequestContext(app_context))  # type: ignore

            # Call the appropriate tool
            if tool_name == "execute_method":
                from .server import execute_method

                result = execute_method(
                    mock_context,
                    model=args.get("model"),
                    method=args.get("method"),
                    args=args.get("args"),
                    kwargs=args.get("kwargs"),
                )
            elif tool_name == "search_employee":
                from .server import search_employee

                result = search_employee(
                    mock_context, name=args.get("name"), limit=args.get("limit", 20)
                )
            elif tool_name == "search_holidays":
                from .server import search_holidays

                result = search_holidays(
                    mock_context,
                    start_date=args.get("start_date"),
                    end_date=args.get("end_date"),
                    employee_id=args.get("employee_id"),
                )
            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            # Convert result to MCP format
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            result.dict() if hasattr(result, "dict") else result,
                            indent=2,
                        ),
                    }
                ]
            }

        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error calling tool {tool_name}: {str(e)}",
                    }
                ],
                "isError": True,
            }

    async def _read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a resource and return the content"""
        try:
            # Parse the URI and call the appropriate resource function
            if uri == "odoo://models":
                from .server import get_models

                content = get_models()
            elif uri.startswith("odoo://model/"):
                model_name = uri.split("/")[-1]
                from .server import get_model_info

                content = get_model_info(model_name)
            elif uri.startswith("odoo://record/"):
                parts = uri.split("/")
                if len(parts) >= 4:
                    model_name = parts[-2]
                    record_id = parts[-1]
                    from .server import get_record

                    content = get_record(model_name, record_id)
                else:
                    raise ValueError("Invalid record URI format")
            elif uri.startswith("odoo://search/"):
                parts = uri.split("/")
                if len(parts) >= 4:
                    model_name = parts[-2]
                    domain = parts[-1]
                    from .server import search_records_resource

                    content = search_records_resource(model_name, domain)
                else:
                    raise ValueError("Invalid search URI format")
            else:
                raise ValueError(f"Unknown resource URI: {uri}")

            return {
                "contents": [
                    {"uri": uri, "mimeType": "application/json", "text": content}
                ]
            }

        except Exception as e:
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps({"error": str(e)}, indent=2),
                    }
                ],
                "isError": True,
            }

    async def _stream_results(
        self, response: MCPResponse, request_id: Optional[Union[str, int]]
    ):  # type: ignore
        """Stream results as Server-Sent Events"""
        if not isinstance(response.result, list):
            # Single result
            yield f"data: {json.dumps(response.dict(exclude_none=True))}\n\n"
        else:
            # Multiple results
            for i, item in enumerate(response.result):
                chunk_response = MCPResponse(id=request_id, result=item)
                yield f"data: {json.dumps(chunk_response.dict(exclude_none=True))}\n\n"

                # Small delay between chunks
                await asyncio.sleep(0.01)

        # End of stream
        yield "data: [DONE]\n\n"

    def cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions"""
        now = datetime.utcnow()
        expired_sessions = [
            session_id
            for session_id, session in self.sessions.items()
            if (now - session.last_activity).total_seconds()
            > self.config.session_timeout
        ]

        for session_id in expired_sessions:
            del self.sessions[session_id]

        if expired_sessions:
            print(f"Cleaned up {len(expired_sessions)} expired sessions")


def create_http_app(config: AppConfig, mcp_server: Any) -> FastAPI:
    """Create HTTP transport FastAPI application"""
    transport = HTTPTransport(config.http, mcp_server)
    return transport.app
