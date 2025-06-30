# Step 1: Basic FastAPI Skeleton
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "healthy"}

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
                "capabilities": {"tools": {"listChanged": False}, "prompts": {"listChanged": False}},
                "serverInfo": {"name": "mcp-echo", "version": "0.1.0"}
            }
        elif mcp_request.method == "tools/list":
            tools = await list_tools()
            result = [tool.model_dump() for tool in tools]
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