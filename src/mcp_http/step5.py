# Step 5: Basic JWT Infrastructure
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Union, Dict, Any
from mcp.server import Server
import uvicorn
import os
import logging

from mcp.types import Tool, Prompt, PromptArgument, TextContent, PromptMessage, GetPromptResult
from pydantic import Field
from typing import List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: str
    params: Optional[Dict[str, Any]] = None

class EchoRequest(BaseModel):
    message: str = Field(..., description="Message to echo")
    repeat_count: int = Field(1, ge=1, le=10)

class JWTMCPServer:
    """MCP Server with basic JWT infrastructure."""
    
    def __init__(self):
        self.app = FastAPI(title="JWT MCP Server", version="0.1.0")
        self.server = Server("mcp-echo")
        self.public_key = None
        self.public_key_jwk = None
        self.load_public_key()
        self.setup_middleware()
        self.setup_routes()
        
    def load_public_key(self):
        """Load RSA public key for JWT validation."""
        key_file = "mcp_public_key.pem"
        
        if os.path.exists(key_file):
            logger.info("Loading RSA public key...")
            try:
                from cryptography.hazmat.primitives import serialization
                with open(key_file, "rb") as f:
                    self.public_key = serialization.load_pem_public_key(f.read())
                logger.info("✅ RSA public key loaded successfully")
                self.generate_jwk()
            except Exception as e:
                logger.warning(f"Failed to load public key file: {e}")
                logger.info("⚠️  JWT validation will be disabled")
        else:
            logger.info("⚠️  No public key file found. JWT validation will be disabled")
            logger.info(f"📝 Create {key_file} to enable JWT validation")
    
    def generate_jwk(self):
        """Generate JWK from public key."""
        if not self.public_key:
            return
            
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            public_numbers = self.public_key.public_numbers()
            
            def int_to_base64url_uint(val):
                """Convert integer to base64url-encoded bytes."""
                import base64
                val_bytes = val.to_bytes((val.bit_length() + 7) // 8, 'big')
                return base64.urlsafe_b64encode(val_bytes).decode('ascii').rstrip('=')
            
            self.public_key_jwk = {
                "kty": "RSA",
                "use": "sig",
                "kid": "mcp-key-1",
                "alg": "RS256",
                "n": int_to_base64url_uint(public_numbers.n),
                "e": int_to_base64url_uint(public_numbers.e)
            }
            logger.info("✅ JWK generated successfully")
        except Exception as e:
            logger.error(f"Failed to generate JWK: {e}")
    
    def setup_middleware(self):
        """Setup CORS middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def setup_routes(self):
        """Setup server routes."""
        
        @self.app.get("/.well-known/jwks.json")
        async def jwks_endpoint():
            """JSON Web Key Set endpoint."""
            if self.public_key_jwk:
                return {"keys": [self.public_key_jwk]}
            else:
                return JSONResponse(
                    status_code=503,
                    content={"error": "JWKS not available - no public key loaded"}
                )
        
        @self.app.get("/health")
        async def health():
            return {
                "status": "healthy",
                "jwt_enabled": self.public_key is not None,
                "jwks_available": self.public_key_jwk is not None
            }
        
        @self.app.post("/mcp")
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
                        "serverInfo": {
                            "name": "mcp-echo",
                            "version": "0.1.0",
                            "jwt_enabled": self.public_key is not None
                        }
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

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [Tool(name="echo", description="Echo a message", inputSchema=EchoRequest.model_json_schema())]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            args = EchoRequest(**arguments)
            return [TextContent(type="text", text=args.message * args.repeat_count)]

        @self.server.list_prompts()
        async def list_prompts() -> List[Prompt]:
            return [Prompt(name="echo_prompt", description="Echo prompt", arguments=[
                PromptArgument(name="message", description="Message", required=True)])]

        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: Optional[Dict[str, str]]) -> GetPromptResult:
            msg = arguments.get("message", "Hello") if arguments else "Hello"
            return GetPromptResult(messages=[
                PromptMessage(role="user", content=[TextContent(type="text", text=f"Please echo: {msg}")])
            ])

    def main(self):
        uvicorn.run(self.app, host="0.0.0.0", port=9000)

def main():
    server = JWTMCPServer()
    server.main()

if __name__ == "__main__":
    main() 