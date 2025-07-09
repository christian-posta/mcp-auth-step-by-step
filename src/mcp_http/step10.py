# Step 9: Keycloak Integration - Basic Setup
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Union, Dict, Any, List
from mcp.server import Server
import uvicorn
import os
import logging
import jwt
import time
import httpx
import json
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware

from mcp.types import Tool, Prompt, PromptArgument, TextContent, PromptMessage, GetPromptResult
from pydantic import Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Keycloak Configuration
KEYCLOAK_URL = "http://localhost:9090"
KEYCLOAK_REALM = "mcp-realm"
JWT_ISSUER = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"
JWT_AUDIENCE = ["echo-mcp-server"]  # Accept tokens with echo-mcp-server audience
MCP_SERVER_URL = "http://localhost:9000"

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

class KeycloakMCPServer:
    """MCP Server with Keycloak JWT token validation and scope-based authorization."""
    
    def __init__(self):
        self.app = FastAPI(title="Keycloak MCP Server", version="0.1.0")
        # Add CORS middleware before custom middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost",
                "http://127.0.0.1",
                "http://localhost:9000",
                "http://127.0.0.1:9000",
                "http://localhost:6274"  # <-- Add your client origin here!
            ],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )
        self.server = Server("mcp-echo")
        self.jwks_cache = {}
        self.jwks_cache_time = None
        self.jwks_cache_duration = timedelta(minutes=5)  # Cache for 5 minutes
        self.setup_middleware()
        self.setup_routes()
        
    async def fetch_keycloak_jwks(self) -> Dict[str, Any]:
        """Fetch JWKS from Keycloak with caching."""
        now = datetime.now()
        
        # Return cached JWKS if still valid
        if (self.jwks_cache_time and 
            now - self.jwks_cache_time < self.jwks_cache_duration and 
            self.jwks_cache):
            logger.debug("Using cached JWKS")
            return self.jwks_cache
        
        jwks_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
        logger.info(f"Fetching JWKS from Keycloak: {jwks_url}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(jwks_url)
                response.raise_for_status()
                jwks_data = response.json()
                
                # Cache the JWKS
                self.jwks_cache = jwks_data
                self.jwks_cache_time = now
                
                logger.info(f"✅ JWKS fetched successfully with {len(jwks_data.get('keys', []))} keys")
                return jwks_data
                
        except Exception as e:
            logger.error(f"Failed to fetch JWKS from Keycloak: {e}")
            raise HTTPException(
                status_code=503,
                detail="Unable to fetch JWKS from Keycloak"
            )
    
    def get_public_key_from_jwks(self, jwks_data: Dict[str, Any], kid: str) -> Optional[str]:
        """Extract public key from JWKS by key ID."""
        for key in jwks_data.get('keys', []):
            if key.get('kid') == kid:
                # Convert JWK to PEM format
                try:
                    from cryptography.hazmat.primitives.asymmetric import rsa
                    from cryptography.hazmat.primitives import serialization
                    import base64
                    
                    # Extract RSA components
                    n = int.from_bytes(base64.urlsafe_b64decode(key['n'] + '=='), 'big')
                    e = int.from_bytes(base64.urlsafe_b64decode(key['e'] + '=='), 'big')
                    
                    # Create RSA public key
                    public_numbers = rsa.RSAPublicNumbers(e, n)
                    public_key = public_numbers.public_key()
                    
                    # Convert to PEM
                    pem = public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
                    
                    return pem.decode('utf-8')
                    
                except Exception as e:
                    logger.error(f"Failed to convert JWK to PEM: {e}")
                    return None
        
        logger.warning(f"Key with kid '{kid}' not found in JWKS")
        return None
    
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
        """Verify JWT token using Keycloak."""
        logger.info("=== Token Validation Debug ===")
        
        if not credentials:
            logger.error("No credentials provided")
            raise HTTPException(
                status_code=401,
                detail="Authorization header missing",
                headers=self.get_www_authenticate_header()
            )
        
        token = credentials.credentials
        logger.info(f"Raw token received: {token[:50]}...{token[-50:] if len(token) > 100 else ''}")
        logger.info(f"Token length: {len(token)}")
        
        # Check for common token issues
        if not token or token.strip() == "":
            logger.error("Empty token received")
            raise HTTPException(
                status_code=401,
                detail="Empty token",
                headers=self.get_www_authenticate_header()
            )
        
        # Check for invalid characters
        if '\n' in token or '\r' in token:
            logger.error("Token contains newline characters")
            raise HTTPException(
                status_code=401,
                detail="Invalid token format",
                headers=self.get_www_authenticate_header()
            )
        
        try:
            # Decode token header to get key ID
            logger.info("Decoding token header...")
            header = jwt.get_unverified_header(token)
            logger.info(f"Token header: {header}")
            
            kid = header.get('kid')
            if not kid:
                logger.error("Token missing key ID")
                raise HTTPException(
                    status_code=401,
                    detail="Token missing key ID",
                    headers=self.get_www_authenticate_header()
                )
            
            logger.info(f"Token key ID: {kid}")
            
            # Fetch JWKS from Keycloak
            logger.info("Fetching JWKS from Keycloak...")
            jwks_data = await self.fetch_keycloak_jwks()
            
            # Get public key for this token
            logger.info("Extracting public key from JWKS...")
            public_key_pem = self.get_public_key_from_jwks(jwks_data, kid)
            if not public_key_pem:
                logger.error("Unable to get public key from JWKS")
                raise HTTPException(
                    status_code=401,
                    detail="Unable to verify token signature",
                    headers=self.get_www_authenticate_header()
                )
            
            logger.info("Public key extracted successfully")
            
            # Verify and decode token
            logger.info("Verifying and decoding token...")
            logger.info(f"Expected audiences: {JWT_AUDIENCE}")
            logger.info(f"Expected issuer: {JWT_ISSUER}")
            
            # Handle multiple audiences
            if isinstance(JWT_AUDIENCE, list):
                # Try each audience
                payload = None
                for audience in JWT_AUDIENCE:
                    try:
                        payload = jwt.decode(
                            token,
                            public_key_pem,
                            algorithms=["RS256"],
                            audience=audience,
                            issuer=JWT_ISSUER,
                            options={"verify_signature": True, "verify_exp": True, "verify_iat": False}
                        )
                        logger.info(f"Token validated with audience: {audience}")
                        break
                    except jwt.InvalidAudienceError:
                        logger.debug(f"Token validation failed for audience: {audience}")
                        continue
                
                if payload is None:
                    logger.warning(f"Token validation failed for all audiences: {JWT_AUDIENCE}")
                    raise jwt.InvalidAudienceError("Invalid token audience")
            else:
                # Single audience
                payload = jwt.decode(
                    token,
                    public_key_pem,
                    algorithms=["RS256"],
                    audience=JWT_AUDIENCE,
                    issuer=JWT_ISSUER,
                    options={"verify_signature": True, "verify_exp": True, "verify_iat": False}
                )
            
            logger.info(f"Token payload: {json.dumps(payload, indent=2)}")
            
            # Extract scopes from token
            scopes = []
            if 'scope' in payload:
                scopes = payload['scope'].split(' ')
            elif 'scopes' in payload:
                scopes = payload['scopes']
            
            # Add scopes to payload for consistency
            payload['scopes'] = scopes
            
            username = payload.get('preferred_username', payload.get('sub', 'unknown'))
            logger.info(f"Token validated for user: {username}")
            logger.info(f"Scopes: {scopes}")
            
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
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Token validation traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=401,
                detail="Invalid token",
                headers=self.get_www_authenticate_header()
            )
    
    def get_www_authenticate_header(self) -> Dict[str, str]:
        """Get WWW-Authenticate header for 401 responses."""
        return {
            "WWW-Authenticate": f'Bearer realm="mcp-server", resource_metadata="{MCP_SERVER_URL}/.well-known/oauth-protected-resource"'
        }
    
    def check_permission(self, scopes: List[str], resource: str, action: str) -> bool:
        """Check if user has permission for a resource/action based on scopes."""
        # Check specific scope for the resource
        if f"mcp:{resource}" in scopes:
            logger.info(f"Scope access granted for {resource}:{action}")
            return True
        
        # Check read scope for basic read operations only (not resource-specific)
        # mcp:read should only grant access to basic operations like ping, not prompts/list
        if action == "read" and "mcp:read" in scopes:
            # Only allow mcp:read for basic operations, not resource-specific ones
            if resource in ["tools", "prompts"]:
                logger.warning(f"Access denied for {resource}:{action}. Resource-specific scope required. Scopes: {scopes}")
                return False
            logger.info(f"Read scope access granted for {resource}:{action}")
            return True
        
        logger.warning(f"Access denied for {resource}:{action}. Scopes: {scopes}")
        return False
    
    def forbidden_response(self, detail: str):
        """Return 403 Forbidden response."""
        return JSONResponse(
            status_code=403,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32001,
                    "message": "Forbidden",
                    "data": {"detail": detail}
                }
            }
        )
    
    def setup_routes(self):
        """Setup server routes."""
        
        @self.app.get("/.well-known/oauth-protected-resource")
        async def protected_resource_metadata():
            """OAuth 2.0 Protected Resource Metadata (RFC 9728)."""
            return {
                "resource": MCP_SERVER_URL,
                "authorization_servers": [f"{JWT_ISSUER}"],
                "scopes_supported": ["echo-mcp-server-audience", "mcp:read", "mcp:tools", "mcp:prompts"],
                "bearer_methods_supported": ["header"],
                "resource_documentation": f"{MCP_SERVER_URL}/docs",
                "mcp_protocol_version": "2025-06-18",
                "resource_type": "mcp-server"
            }
        

        

        
        @self.app.get("/health")
        async def health():
            try:
                jwks_data = await self.fetch_keycloak_jwks()
                jwks_available = len(jwks_data.get('keys', [])) > 0
            except:
                jwks_available = False
                
            return {
                "status": "healthy",
                "keycloak_integration": True,
                "jwks_available": jwks_available,
                "auth_required": True,
                "scope_based_auth": True,
                "keycloak_config": {
                    "url": KEYCLOAK_URL,
                    "realm": KEYCLOAK_REALM,
                    "issuer": JWT_ISSUER,
                    "jwks_url": f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
                },
                "oauth_metadata": {
                    "protected_resource": f"{MCP_SERVER_URL}/.well-known/oauth-protected-resource",
                    "authorization_server": f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/.well-known/oauth-authorization-server",
                    "jwks": f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
                }
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
            """Handle MCP requests with Keycloak JWT protection and scope-based authorization."""
            # Debug: Log request details
            logger.info(f"=== MCP Request Debug ===")
            logger.info(f"Request method: {request.method}")
            logger.info(f"Request URL: {request.url}")
            logger.info(f"Request headers: {dict(request.headers)}")
            
            # Debug: Log request body
            try:
                body_bytes = await request.body()
                body_text = body_bytes.decode('utf-8')
                logger.info(f"Request body (raw): {body_text}")
                
                # Try to parse as JSON
                try:
                    body_json = json.loads(body_text)
                    logger.info(f"Request body (parsed): {json.dumps(body_json, indent=2)}")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse request body as JSON: {e}")
                    logger.error(f"Body content: {repr(body_text)}")
                    return JSONResponse(
                        status_code=400,
                        content={"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error", "data": {"detail": str(e)}}}
                    )
            except Exception as e:
                logger.error(f"Failed to read request body: {e}")
                return JSONResponse(
                    status_code=400,
                    content={"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error", "data": {"detail": str(e)}}}
                )
            
            # Parse MCP request
            try:
                mcp_request = MCPRequest(**body_json)
                logger.info(f"MCP request parsed: method={mcp_request.method}, id={mcp_request.id}")
            except Exception as e:
                logger.error(f"Failed to parse MCP request: {e}")
                return JSONResponse(
                    status_code=400,
                    content={"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request", "data": {"detail": str(e)}}}
                )
            
            username = token_info.get("preferred_username", token_info.get("sub", "unknown"))
            scopes = token_info.get("scopes", [])
            
            logger.info(f"Authenticated request from user: {username}")
            logger.info(f"Scopes: {scopes}")
            
            # Handle notifications (no response)
            if mcp_request.id is None:
                logger.info(f"Handling notification: {mcp_request.method}")
                return JSONResponse(status_code=202, content=None)

            try:
                logger.info(f"Processing MCP method: {mcp_request.method}")
                
                if mcp_request.method == "initialize":
                    result = {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {"tools": {"listChanged": False}, "prompts": {"listChanged": False}},
                        "serverInfo": {
                            "name": "mcp-echo",
                            "version": "0.1.0",
                            "keycloak_integration": True,
                            "authenticatedUser": username,
                            "userScopes": scopes,
                            "keycloak_config": {
                                "realm": KEYCLOAK_REALM,
                                "issuer": JWT_ISSUER
                            },
                            "oauth_metadata": {
                                "protected_resource": f"{MCP_SERVER_URL}/.well-known/oauth-protected-resource",
                                "authorization_server": f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/.well-known/oauth-authorization-server"
                            }
                        }
                    }
                elif mcp_request.method == "tools/list":
                    if not self.check_permission(scopes, "tools", "read"):
                        return self.forbidden_response("Insufficient permissions for tools access")
                    tools = await list_tools()
                    result = {
                        "tools": [tool.model_dump() for tool in tools]
                    }
                elif mcp_request.method == "tools/call":
                    if not self.check_permission(scopes, "tools", "execute"):
                        return self.forbidden_response("Insufficient permissions for tool execution")
                    content = await call_tool(mcp_request.params["name"], mcp_request.params["arguments"])
                    result = {
                        "content": [item.model_dump() for item in content],
                        "isError": False
                    }
                elif mcp_request.method == "prompts/list":
                    if not self.check_permission(scopes, "prompts", "read"):
                        return self.forbidden_response("Insufficient permissions for prompts access")
                    prompts = await list_prompts()
                    result = {
                        "prompts": [prompt.model_dump() for prompt in prompts]
                    }
                elif mcp_request.method == "prompts/get":
                    if not self.check_permission(scopes, "prompts", "read"):
                        return self.forbidden_response("Insufficient permissions for prompts access")
                    prompt_result = await get_prompt(mcp_request.params["name"], mcp_request.params.get("arguments"))
                    result = prompt_result.model_dump()
                elif mcp_request.method == "ping":
                    result = {
                        "pong": True,
                        "timestamp": time.time(),
                        "user": username,
                        "authenticated": True,
                        "keycloak_integration": True,
                        "userScopes": scopes,
                        "keycloak_config": {
                            "realm": KEYCLOAK_REALM,
                            "issuer": JWT_ISSUER
                        }
                    }
                else:
                    raise ValueError("Unsupported method")

                logger.info(f"Method {mcp_request.method} completed successfully")
                response_content = {"jsonrpc": "2.0", "id": mcp_request.id, "result": result}
                logger.info(f"Response: {json.dumps(response_content, indent=2)}")
                return JSONResponse(content=response_content)

            except Exception as e:
                logger.error(f"Error processing MCP method {mcp_request.method}: {e}")
                logger.error(f"Exception type: {type(e).__name__}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
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

        @self.server.list_prompts()
        async def list_prompts() -> List[Prompt]:
            return [Prompt(name="echo_prompt", description="Echo prompt", arguments=[
                PromptArgument(name="message", description="Message", required=True)])]

        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: Optional[Dict[str, str]]) -> GetPromptResult:
            msg = arguments.get("message", "Hello") if arguments else "Hello"
            return GetPromptResult(messages=[
                PromptMessage(role="user", content=TextContent(type="text", text=f"Please echo: {msg}"))
            ])

    def main(self):
        uvicorn.run(self.app, host="0.0.0.0", port=9000)

def main():
    server = KeycloakMCPServer()
    server.main()

if __name__ == "__main__":
    main() 