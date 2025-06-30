# Step 2: Basic FastAPI Skeleton with Origin Header Validation
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
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

def main():
    uvicorn.run(app, host="0.0.0.0", port=9000)

if __name__ == "__main__":
    main()