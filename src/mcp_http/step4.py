# Step 4: MCP Tools Dispatching
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Union, Dict, Any
from mcp.server import Server
import uvicorn

from mcp.types import Tool, TextContent
from pydantic import Field
from typing import List

class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: str
    params: Optional[Dict[str, Any]] = None

class EchoRequest(BaseModel):
    message: str = Field(..., description="Message to echo")
    repeat_count: int = Field(1, ge=1, le=10)


app = FastAPI(title="MCP Echo Server", version="0.1.0")
server = Server("mcp-echo")

@app.middleware("http")
async def origin_validation_middleware(request: Request, call_next):
    """
    Middleware to validate Origin header according to MCP specification.
    This prevents DNS rebinding attacks by ensuring requests come from trusted origins.
    """
    # Skip validation for health check endpoint (optional)
    if request.url.path == "/health":
        response = await call_next(request)
        return response

    # Get the Origin header
    origin = request.headers.get("origin")
    
    # Allow requests with no Origin header to allow mcp-inspector to work
    if not origin:
        print("✅ No Origin header - allowing for MCP client")
        response = await call_next(request)
        return response
    
    # Validate the origin - allow localhost and 127.0.0.1 on any port
    if not origin.startswith("http://localhost") and not origin.startswith("http://127.0.0.1"):
        print(f"❌ Origin '{origin}' rejected")
        return JSONResponse(
            status_code=403,
            content={"detail": f"Origin '{origin}' is not allowed. Only localhost and 127.0.0.1 are permitted."}
        )
    
    print(f"✅ Origin '{origin}' accepted")
    response = await call_next(request)
    return response

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/mcp")
async def handle_mcp_get(request: Request):
    """Handle GET requests to MCP endpoint."""
    # Return 405 Method Not Allowed as per MCP spec for servers that don't support SSE
    return JSONResponse(
        status_code=405,
        content={"detail": "Method Not Allowed - This server does not support server-initiated streaming"}
    )

@app.post("/mcp")
async def handle_mcp_request(request: Request):
    body = await request.json()
    mcp_request = MCPRequest(**body)
    if mcp_request.id is None:
        return JSONResponse(status_code=202, content=None)

    try:
        if mcp_request.method == "initialize":
            result = {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "mcp-echo", "version": "0.1.0"}
            }
        elif mcp_request.method == "tools/list":
            tools = await list_tools()
            result = {
                "tools": [tool.model_dump() for tool in tools]
            }
        elif mcp_request.method == "tools/call":
            content = await call_tool(mcp_request.params["name"], mcp_request.params["arguments"])
            result = {
                "content": [item.model_dump() for item in content],
                "isError": False
            }
        else:
            raise ValueError("Unsupported method")

        return JSONResponse(content={"jsonrpc": "2.0", "id": mcp_request.id, "result": result})

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"jsonrpc": "2.0", "id": mcp_request.id, "error": {"code": -32603, "message": str(e)}}
        )

@server.list_tools()
async def list_tools() -> List[Tool]:
    return [Tool(
        name="echo", 
        description="Echo a message", 
        title="Echo Tool",
        inputSchema=EchoRequest.model_json_schema(),
        outputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The echoed message"}
            }
        },
        annotations={
            "title": "Echo Tool",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        }
    )]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    args = EchoRequest(**arguments)
    return [TextContent(type="text", text=args.message * args.repeat_count)]

def main():
    uvicorn.run(app, host="0.0.0.0", port=9000)

if __name__ == "__main__":
    main()