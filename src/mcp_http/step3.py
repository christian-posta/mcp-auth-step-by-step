# Step 3: MCP Tools and Prompts
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Union, Dict, Any
from mcp.server import Server
import uvicorn

from mcp.types import Tool, Prompt, PromptArgument, TextContent, PromptMessage, GetPromptResult
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

    if not origin:
        print("✅ No Origin header - allowing for MCP client")
        response = await call_next(request)
        return response
    # Validate the origin - allow localhost and 127.0.0.1 on any port
    if not origin or (not origin.startswith("http://localhost") and not origin.startswith("http://127.0.0.1")):
        return JSONResponse(
            status_code=403,
            content={"detail": f"Origin '{origin}' is not allowed. Only localhost and 127.0.0.1 are permitted."}
        )
    
    response = await call_next(request)
    return response

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/mcp")
async def handle_mcp_request(request: Request):
    body = await request.json()
    mcp_request = MCPRequest(**body)
    if mcp_request.method == "ping":
        return {"jsonrpc": "2.0", "id": mcp_request.id, "result": {}}
    return JSONResponse(status_code=400, content={
        "jsonrpc": "2.0",
        "id": mcp_request.id,
        "error": {"code": -32601, "message": f"Method not found: {mcp_request.method}"}
    })

@server.list_tools()
async def list_tools() -> List[Tool]:
    return [Tool(name="echo", description="Echo a message", inputSchema=EchoRequest.model_json_schema())]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    args = EchoRequest(**arguments)
    return [TextContent(type="text", text=args.message * args.repeat_count)]

@server.list_prompts()
async def list_prompts() -> List[Prompt]:
    return [Prompt(name="echo_prompt", description="Echo prompt", arguments=[
        PromptArgument(name="message", description="Message", required=True)])]

@server.get_prompt()
async def get_prompt(name: str, arguments: Optional[Dict[str, str]]) -> GetPromptResult:
    msg = arguments.get("message", "Hello") if arguments else "Hello"
    return GetPromptResult(messages=[
        PromptMessage(role="user", content=[TextContent(type="text", text=f"Please echo: {msg}")])
    ])

def main():
    uvicorn.run(app, host="0.0.0.0", port=9000)

if __name__ == "__main__":
    main()