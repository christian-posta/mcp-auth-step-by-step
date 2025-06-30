# Step 1: Basic FastAPI Skeleton
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Union, Dict, Any
from mcp.server import Server
import uvicorn

class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: str
    params: Optional[Dict[str, Any]] = None


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
    if mcp_request.method == "ping":
        return {"jsonrpc": "2.0", "id": mcp_request.id, "result": {}}
    return JSONResponse(status_code=400, content={
        "jsonrpc": "2.0",
        "id": mcp_request.id,
        "error": {"code": -32601, "message": f"Method not found: {mcp_request.method}"}
    })

def main():
    uvicorn.run(app, host="0.0.0.0", port=9000)

if __name__ == "__main__":
    main()