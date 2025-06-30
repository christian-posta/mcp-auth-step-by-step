import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp.server import Server
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    InitializeResult,
    ListPromptsResult,
    ListToolsResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
    Tool,
)
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EchoRequest(BaseModel):
    """Parameters for the echo tool."""
    message: str = Field(description="The message to echo back")
    repeat_count: int = Field(default=1, description="Number of times to repeat the message", ge=1, le=10)


from typing import Union

class MCPRequest(BaseModel):
    """MCP request wrapper for HTTP transport."""
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None  # Optional for notifications
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPResponse(BaseModel):
    """MCP response wrapper for HTTP transport."""
    jsonrpc: str = "2.0"
    id: Union[str, int]  # JSON-RPC allows both string and integer IDs
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class HTTPMCPServer:
    """HTTP-based MCP server implementation with CORS and OAuth discovery."""
    
    def __init__(self):
        logger.info("Initializing HTTPMCPServer")
        self.server = Server("mcp-echo")
        logger.info("Created MCP Server instance")
        self.app = FastAPI(title="MCP Echo Server", version="0.1.0")
        logger.info("Created FastAPI app")
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # In production, be more specific
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        logger.info("Added CORS middleware")
        
        self.setup_routes()
        logger.info("Setup FastAPI routes")
        self.setup_mcp_handlers()
        logger.info("Setup MCP handlers")
        logger.info("HTTPMCPServer initialization complete")
    
    def setup_routes(self):
        """Setup FastAPI routes."""
        logger.info("Setting up FastAPI routes")
        
        @self.app.post("/mcp")
        async def handle_mcp_request(request: Request):
            """Handle MCP requests over HTTP."""
            try:
                body = await request.json()
                logger.info(f"Received MCP request: {body.get('method', 'unknown')} with id {body.get('id', 'unknown')}")
                
                mcp_request = MCPRequest(**body)
                logger.debug(f"Parsed MCP request: method={mcp_request.method}, params={mcp_request.params}")
                
                # Handle notifications (no ID, no response required)
                if mcp_request.id is None:
                    logger.info(f"Handling notification: {mcp_request.method}")
                    if mcp_request.method == "notifications/initialized":
                        logger.info("Client has completed initialization")
                    elif mcp_request.method == "notifications/cancelled":
                        logger.info("Client cancelled a request")
                    else:
                        logger.warning(f"Unknown notification: {mcp_request.method}")
                    
                    # Notifications get 202 Accepted with no body
                    return JSONResponse(status_code=202, content=None)
                
                # Handle requests (have ID, need response)
                result = None
                if mcp_request.method == "initialize":
                    logger.info("Handling initialize request")
                    result = await self.handle_initialize(mcp_request.params or {})
                elif mcp_request.method == "tools/list":
                    logger.info("Handling tools/list request")
                    result = await self.handle_list_tools()
                elif mcp_request.method == "tools/call":
                    logger.info("Handling tools/call request")
                    result = await self.handle_call_tool(mcp_request.params or {})
                elif mcp_request.method == "prompts/list":
                    logger.info("Handling prompts/list request")
                    result = await self.handle_list_prompts()
                elif mcp_request.method == "prompts/get":
                    logger.info("Handling prompts/get request")
                    result = await self.handle_get_prompt(mcp_request.params or {})
                elif mcp_request.method == "ping":
                    logger.info("Handling ping request")
                    result = {}
                else:
                    logger.warning(f"Unknown method: {mcp_request.method}")
                    return JSONResponse(
                        status_code=400,
                        content={
                            "jsonrpc": "2.0",
                            "id": mcp_request.id,
                            "error": {
                                "code": -32601,
                                "message": f"Method not found: {mcp_request.method}"
                            }
                        }
                    )
                
                logger.info(f"Successfully handled {mcp_request.method} request")
                logger.debug(f"Response result: {result}")
                
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": mcp_request.id,
                    "result": result
                })
                
            except Exception as e:
                logger.error(f"Error handling MCP request: {e}", exc_info=True)
                return JSONResponse(
                    status_code=500,
                    content={
                        "jsonrpc": "2.0",
                        "id": body.get("id", "unknown") if body.get("id") is not None else None,
                        "error": {
                            "code": -32603,
                            "message": f"Internal error: {str(e)}"
                        }
                    }
                )
        
        @self.app.get("/mcp")
        async def handle_mcp_get(request: Request):
            """Handle GET requests to MCP endpoint."""
            logger.info("GET request to MCP endpoint")
            return JSONResponse(content={
                "server": "mcp-echo",
                "transport": "streamable-http",
                "version": "0.1.0"
            })
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            logger.info("Health check requested")
            return {"status": "healthy", "server": "mcp-echo"}
        
        # OAuth 2.0 discovery endpoints (empty responses for no-auth servers)
        @self.app.get("/.well-known/oauth-protected-resource")
        async def oauth_protected_resource():
            """OAuth 2.0 Protected Resource Metadata."""
            logger.info("OAuth protected resource metadata requested")
            return JSONResponse(content={
                "resource": "http://localhost:9000/mcp",
                # Empty means no authorization required
            })
        
        @self.app.get("/.well-known/oauth-authorization-server")
        @self.app.get("/.well-known/oauth-authorization-server/mcp")
        async def oauth_authorization_server():
            """OAuth 2.0 Authorization Server Metadata."""
            logger.info("OAuth authorization server metadata requested")
            return JSONResponse(content={
                # Empty means no authorization server configured
            })
        
        # Handle CORS preflight requests
        @self.app.options("/{path:path}")
        async def options_handler(path: str):
            """Handle CORS preflight requests."""
            logger.info(f"CORS preflight request for path: {path}")
            return JSONResponse(
                content={},
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                }
            )
        
        logger.info("FastAPI routes setup complete")
    
    def setup_mcp_handlers(self):
        """Setup MCP server handlers."""
        logger.info("Setting up MCP handlers")
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            logger.info("list_tools handler called")
            tools = [
                Tool(
                    name="echo",
                    description="Echo back a message with optional repetition",
                    inputSchema=EchoRequest.model_json_schema(),
                )
            ]
            logger.info(f"Returning {len(tools)} tools from list_tools handler")
            return tools
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            logger.info(f"call_tool handler called with name={name}, arguments={arguments}")
            if name == "echo":
                echo_args = EchoRequest(**arguments)
                repeated_message = echo_args.message * echo_args.repeat_count
                logger.info(f"Echo tool returning: {repeated_message}")
                return [TextContent(type="text", text=repeated_message)]
            else:
                logger.error(f"Unknown tool: {name}")
                raise ValueError(f"Unknown tool: {name}")
        
        @self.server.list_prompts()
        async def list_prompts() -> List[Prompt]:
            logger.info("list_prompts handler called")
            prompts = [
                Prompt(
                    name="echo_prompt",
                    description="A prompt that demonstrates echo functionality",
                    arguments=[
                        PromptArgument(
                            name="message",
                            description="The message to echo",
                            required=True
                        )
                    ]
                )
            ]
            logger.info(f"Returning {len(prompts)} prompts from list_prompts handler")
            return prompts
        
        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: Optional[Dict[str, str]] = None) -> GetPromptResult:
            logger.info(f"get_prompt handler called with name={name}, arguments={arguments}")
            if name == "echo_prompt":
                message = arguments.get("message", "Hello, World!") if arguments else "Hello, World!"
                logger.info(f"Echo prompt returning message: {message}")
                return GetPromptResult(
                    messages=[
                        PromptMessage(
                            role="user",
                            content=[TextContent(type="text", text=f"Please echo: {message}")]
                        )
                    ]
                )
            else:
                logger.error(f"Unknown prompt: {name}")
                raise ValueError(f"Unknown prompt: {name}")
        
        logger.info("MCP handlers setup complete")
    
    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        return {
            "protocolVersion": "2025-06-18",
            "capabilities": {
                "tools": {"listChanged": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": {
                "name": "mcp-echo",
                "version": "0.1.0"
            }
        }
    
    async def handle_list_tools(self) -> Dict[str, Any]:
        """Handle tools/list request."""
        try:
            logger.info("Handling tools/list request directly")
            
            tools = [
                {
                    "name": "echo",
                    "description": "Echo back a message with optional repetition",
                    "inputSchema": EchoRequest.model_json_schema(),
                }
            ]
            
            logger.info(f"Returning {len(tools)} tools")
            return {"tools": tools}
        except Exception as e:
            logger.error(f"Error in handle_list_tools: {e}", exc_info=True)
            raise
    
    async def handle_call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        try:
            name = params.get("name")
            arguments = params.get("arguments", {})
            
            logger.info(f"Calling tool: {name} with arguments: {arguments}")
            
            if not name:
                logger.error("Tool name is required but not provided")
                raise ValueError("Tool name is required")
            
            if name == "echo":
                echo_args = EchoRequest(**arguments)
                repeated_message = echo_args.message * echo_args.repeat_count
                logger.info(f"Echo tool returning: {repeated_message}")
                
                content = [{"type": "text", "text": repeated_message}]
                
                result = {
                    "content": content,
                    "isError": False
                }
                logger.info(f"Returning tool call result for {name}")
                return result
            else:
                logger.error(f"Unknown tool: {name}")
                raise ValueError(f"Unknown tool: {name}")
                
        except Exception as e:
            logger.error(f"Error in handle_call_tool: {e}", exc_info=True)
            raise
    
    async def handle_list_prompts(self) -> Dict[str, Any]:
        """Handle prompts/list request."""
        try:
            logger.info("Handling prompts/list request directly")
            
            prompts = [
                {
                    "name": "echo_prompt",
                    "description": "A prompt that demonstrates echo functionality",
                    "arguments": [
                        {
                            "name": "message",
                            "description": "The message to echo",
                            "required": True
                        }
                    ]
                }
            ]
            
            logger.info(f"Returning {len(prompts)} prompts")
            return {"prompts": prompts}
        except Exception as e:
            logger.error(f"Error in handle_list_prompts: {e}", exc_info=True)
            raise
    
    async def handle_get_prompt(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get request."""
        try:
            name = params.get("name")
            arguments = params.get("arguments")
            
            logger.info(f"Getting prompt: {name} with arguments: {arguments}")
            
            if not name:
                logger.error("Prompt name is required but not provided")
                raise ValueError("Prompt name is required")
            
            if name == "echo_prompt":
                message = arguments.get("message", "Hello, World!") if arguments else "Hello, World!"
                logger.info(f"Echo prompt returning message: {message}")
                
                result = {
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": f"Please echo: {message}"}]
                        }
                    ]
                }
                logger.info(f"Retrieved prompt {name}")
                return result
            else:
                logger.error(f"Unknown prompt: {name}")
                raise ValueError(f"Unknown prompt: {name}")
                
        except Exception as e:
            logger.error(f"Error in handle_get_prompt: {e}", exc_info=True)
            raise
    
    def run(self, host: str = "127.0.0.1", port: int = 9000):
        """Run the HTTP server."""
        logger.info(f"Starting HTTP server on {host}:{port}")
        uvicorn.run(self.app, host=host, port=port, log_level="info")


def serve(host: str = "127.0.0.1", port: int = 9000) -> None:
    """Run the echo MCP server."""
    logger.info(f"Starting MCP Echo Server on {host}:{port}")
    server = HTTPMCPServer()
    logger.info("HTTPMCPServer created, starting server")
    server.run(host=host, port=port)


if __name__ == "__main__":
    logger.info("Starting MCP Echo Server from __main__")
    serve()