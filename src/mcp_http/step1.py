# Step 1: Basic FastAPI Skeleton with Origin Header Validation
from fastapi import FastAPI, Request, HTTPException
from mcp.server import Server
import uvicorn
from fastapi.responses import JSONResponse

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

def main():
    uvicorn.run(app, host="0.0.0.0", port=9000)

if __name__ == "__main__":
    main()