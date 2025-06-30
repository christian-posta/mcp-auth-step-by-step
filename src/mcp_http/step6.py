# Step 6: JWT Token Validation
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Union, Dict, Any
from mcp.server import Server
import uvicorn
import os
import logging
import jwt
import time

from mcp.types import Tool, TextContent
from pydantic import Field
from typing import List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# JWT Configuration
JWT_ISSUER = "mcp-simple-auth"
JWT_AUDIENCE = "mcp-server"

# Security scheme
security = HTTPBearer(auto_error=False)

class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: str
    params: Optional[Dict[str, Any]] = None

class EchoRequest(BaseModel):
    message: str = Field(..., description="Message to echo")
    repeat_count: int = Field(1, ge=1, le=10)

class JWTMCPServer:
    """MCP Server with JWT token validation."""
    
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
        """Setup Origin validation middleware."""
        
        @self.app.middleware("http")
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
                logger.info("✅ No Origin header - allowing for MCP client")
                response = await call_next(request)
                return response
            
            # Validate the origin - allow localhost and 127.0.0.1 on any port
            if not origin.startswith("http://localhost") and not origin.startswith("http://127.0.0.1"):
                logger.warning(f"❌ Origin '{origin}' rejected")
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"Origin '{origin}' is not allowed. Only localhost and 127.0.0.1 are permitted."}
                )
            
            logger.info(f"✅ Origin '{origin}' accepted")
            response = await call_next(request)
            return response
    
    async def verify_token(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
    ) -> Dict[str, Any]:
        """Verify JWT token."""
        if not self.public_key:
            logger.warning("JWT validation disabled - no public key loaded")
            return {"preferred_username": "anonymous", "scopes": [], "roles": []}
        
        if not credentials:
            raise HTTPException(
                status_code=401,
                detail="Authorization header missing",
                headers=self.get_www_authenticate_header()
            )
        
        token = credentials.credentials
        
        try:
            # Verify and decode token
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=["RS256"],
                audience=JWT_AUDIENCE,
                issuer=JWT_ISSUER,
                options={"verify_signature": True, "verify_exp": True, "verify_iat": False}
            )
            
            logger.info(f"Token validated for user: {payload.get('preferred_username', 'unknown')}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise HTTPException(
                status_code=401,
                detail="Token has expired",
                headers=self.get_www_authenticate_header()
            )
        except jwt.InvalidAudienceError:
            logger.warning(f"Invalid audience. Expected: {JWT_AUDIENCE}")
            raise HTTPException(
                status_code=401,
                detail="Invalid token audience",
                headers=self.get_www_authenticate_header()
            )
        except jwt.InvalidIssuerError:
            logger.warning(f"Invalid issuer. Expected: {JWT_ISSUER}")
            raise HTTPException(
                status_code=401,
                detail="Invalid token issuer",
                headers=self.get_www_authenticate_header()
            )
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            raise HTTPException(
                status_code=401,
                detail="Invalid token",
                headers=self.get_www_authenticate_header()
            )
    
    def get_www_authenticate_header(self) -> Dict[str, str]:
        """Get WWW-Authenticate header for 401 responses."""
        return {
            "WWW-Authenticate": f'Bearer realm="mcp-server", resource_metadata="http://localhost:9000/.well-known/oauth-protected-resource"'
        }
    
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
                "jwks_available": self.public_key_jwk is not None,
                "auth_required": True
            }
        
        @self.app.get("/mcp")
        async def handle_mcp_get(request: Request):
            """Handle GET requests to MCP endpoint."""
            # Return 405 Method Not Allowed as per MCP spec for servers that don't support SSE
            return JSONResponse(
                status_code=405,
                content={"detail": "Method Not Allowed - This server does not support server-initiated streaming"}
            )
        
        @self.app.post("/mcp")
        async def handle_mcp_request(
            request: Request,
            token_info: Dict[str, Any] = Depends(self.verify_token)
        ):
            """Handle MCP requests with JWT protection."""
            body = await request.json()
            mcp_request = MCPRequest(**body)
            
            username = token_info.get("preferred_username", "unknown")
            logger.info(f"Authenticated request from user: {username}")
            
            # Handle notifications (no response)
            if mcp_request.id is None:
                logger.info(f"Handling notification: {mcp_request.method}")
                return JSONResponse(status_code=202, content=None)

            try:
                if mcp_request.method == "initialize":
                    result = {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {
                            "name": "mcp-echo",
                            "version": "0.1.0",
                            "jwt_enabled": self.public_key is not None,
                            "authenticatedUser": username
                        }
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
                elif mcp_request.method == "ping":
                    result = {
                        "pong": True,
                        "timestamp": time.time(),
                        "user": username,
                        "authenticated": True
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

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            args = EchoRequest(**arguments)
            return [TextContent(type="text", text=args.message * args.repeat_count)]

    def main(self):
        uvicorn.run(self.app, host="0.0.0.0", port=9000)

def main():
    server = JWTMCPServer()
    server.main()

if __name__ == "__main__":
    main() 