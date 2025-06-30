import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MCP_SERVER_URL = "http://localhost:9000"
JWT_ISSUER = "mcp-simple-auth"
JWT_AUDIENCE = "mcp-server"

security = HTTPBearer(auto_error=False)

class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: str
    params: Optional[Dict[str, Any]] = None

class TokenRequest(BaseModel):
    username: str
    scopes: Optional[List[str]] = ["mcp:read", "mcp:tools", "mcp:prompts"]

class SimpleMCPServer:
    """MCP Server with simple JWT authentication using local keys."""
    
    def __init__(self):
        self.app = FastAPI(title="Simple JWT MCP Server", version="0.1.0")
        self.private_key = None
        self.public_key = None
        self.public_key_jwk = None
        self.generate_keys()
        self.setup_middleware()
        self.setup_routes()
        
    def generate_keys(self):
        """Generate or load RSA key pair for JWT signing."""
        import os
        
        key_file = "mcp_private_key.pem"
        
        if os.path.exists(key_file):
            logger.info("Loading existing RSA key pair...")
            try:
                with open(key_file, "rb") as f:
                    self.private_key = serialization.load_pem_private_key(
                        f.read(),
                        password=None,
                    )
                logger.info("✅ RSA key pair loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load key file: {e}. Generating new keys...")
                self._generate_new_keys(key_file)
        else:
            logger.info("Generating new RSA key pair...")
            self._generate_new_keys(key_file)
        
        # Get public key
        self.public_key = self.private_key.public_key()
        
        # Convert to JWK format for clients
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
    
    def _generate_new_keys(self, key_file: str):
        """Generate and save new RSA keys."""
        # Generate private key
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Save private key to file
        try:
            with open(key_file, "wb") as f:
                f.write(self.private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            logger.info(f"✅ RSA key pair generated and saved to {key_file}")
        except Exception as e:
            logger.warning(f"Failed to save key file: {e}. Keys will be memory-only.")
        
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
        
        @self.app.get("/.well-known/oauth-protected-resource")
        async def protected_resource_metadata():
            """OAuth 2.0 Protected Resource Metadata (RFC 9728)."""
            return {
                "resource": MCP_SERVER_URL,
                "authorization_servers": [JWT_ISSUER],
                "scopes_supported": ["mcp:read", "mcp:tools", "mcp:prompts"],
                "bearer_methods_supported": ["header"],
                "resource_documentation": f"{MCP_SERVER_URL}/docs",
            }
        
        @self.app.get("/.well-known/oauth-authorization-server")
        async def authorization_server_metadata():
            """Simple authorization server metadata."""
            return {
                "issuer": JWT_ISSUER,
                "token_endpoint": f"{MCP_SERVER_URL}/auth/token",
                "jwks_uri": f"{MCP_SERVER_URL}/.well-known/jwks.json",
                "scopes_supported": ["mcp:read", "mcp:tools", "mcp:prompts"],
                "response_types_supported": ["token"],
                "grant_types_supported": ["password"],  # Simplified for demo
                "token_endpoint_auth_methods_supported": ["none"],
            }
        
        @self.app.get("/.well-known/jwks.json")
        async def jwks_endpoint():
            """JSON Web Key Set endpoint."""
            return {
                "keys": [self.public_key_jwk]
            }
        
        @self.app.post("/auth/token")
        async def generate_token(token_request: TokenRequest):
            """Generate a JWT token for testing."""
            logger.info(f"Generating token for user: {token_request.username}")
            
            # In a real system, you'd validate credentials here
            # For demo purposes, we'll accept any username
            
            now = datetime.utcnow()
            now_timestamp = int(now.timestamp())
            exp_timestamp = int((now + timedelta(hours=1)).timestamp())
            
            logger.info(f"Current time: {now} (timestamp: {now_timestamp})")
            logger.info(f"Token will expire: {now + timedelta(hours=1)} (timestamp: {exp_timestamp})")
            
            payload = {
                "iss": JWT_ISSUER,
                "aud": JWT_AUDIENCE,
                "sub": f"user_{token_request.username}",
                "iat": now_timestamp,
                "exp": exp_timestamp,
                "preferred_username": token_request.username,
                "scope": " ".join(token_request.scopes),
                "scopes": token_request.scopes,
                "roles": ["user"],  # Default role
            }
            
            # Add admin role for specific users
            if token_request.username.lower() in ["admin", "administrator"]:
                payload["roles"] = ["user", "admin"]
            
            # Sign the token
            token = jwt.encode(
                payload,
                self.private_key,
                algorithm="RS256",
                headers={"kid": "mcp-key-1"}
            )
            
            logger.info(f"✅ Token generated for {token_request.username}")
            logger.info(f"Token payload: {payload}")
            
            return {
                "access_token": token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": " ".join(token_request.scopes),
                "user": token_request.username,
                "debug": {
                    "issued_at": now.isoformat(),
                    "expires_at": (now + timedelta(hours=1)).isoformat(),
                    "current_timestamp": now_timestamp,
                    "payload": payload
                }
            }
        
        @self.app.get("/auth/demo-tokens")
        async def demo_tokens():
            """Generate demo tokens for testing."""
            tokens = []
            
            demo_users = [
                {"username": "alice", "scopes": ["mcp:read", "mcp:tools"]},
                {"username": "bob", "scopes": ["mcp:read", "mcp:prompts"]},
                {"username": "admin", "scopes": ["mcp:read", "mcp:tools", "mcp:prompts"]},
            ]
            
            for user in demo_users:
                token_req = TokenRequest(**user)
                token_response = await generate_token(token_req)
                tokens.append({
                    "user": user["username"],
                    "scopes": user["scopes"],
                    "token": token_response["access_token"]
                })
            
            return {"demo_tokens": tokens}
        
        @self.app.post("/auth/debug-token")
        async def debug_token(request: Request):
            """Debug token validation issues."""
            try:
                auth_header = request.headers.get("authorization", "")
                if not auth_header.startswith("Bearer "):
                    return {"error": "No Bearer token found"}
                
                token = auth_header[7:]  # Remove "Bearer "
                
                # Try to decode without verification first
                try:
                    unverified = jwt.decode(token, options={"verify_signature": False})
                    logger.info(f"Unverified token payload: {unverified}")
                except Exception as e:
                    return {"error": f"Token decode failed: {e}"}
                
                # Get current time for comparison
                now = datetime.utcnow()
                current_timestamp = int(now.timestamp())
                
                # Check timestamps
                iat = unverified.get("iat", 0)
                exp = unverified.get("exp", 0)
                
                debug_info = {
                    "current_time": now.isoformat(),
                    "current_timestamp": current_timestamp,
                    "token_iat": iat,
                    "token_exp": exp,
                    "token_iat_human": datetime.fromtimestamp(iat).isoformat() if iat else "N/A",
                    "token_exp_human": datetime.fromtimestamp(exp).isoformat() if exp else "N/A",
                    "is_future_token": iat > current_timestamp,
                    "is_expired": exp < current_timestamp,
                    "time_until_valid": iat - current_timestamp if iat > current_timestamp else 0,
                    "time_until_expiry": exp - current_timestamp if exp > current_timestamp else 0,
                }
                
                # Now try with verification
                try:
                    verified = jwt.decode(
                        token,
                        self.public_key,
                        algorithms=["RS256"],
                        audience=JWT_AUDIENCE,
                        issuer=JWT_ISSUER,
                        options={"verify_signature": True, "verify_exp": True, "verify_iat": False}
                    )
                    return {
                        "status": "valid",
                        "payload": verified,
                        "user": verified.get("preferred_username"),
                        "debug": debug_info
                    }
                except jwt.ExpiredSignatureError:
                    return {"error": "Token expired", "payload": unverified, "debug": debug_info}
                except jwt.ImmatureSignatureError:
                    return {"error": "Token not yet valid (future iat)", "payload": unverified, "debug": debug_info}
                except jwt.InvalidAudienceError:
                    return {"error": f"Invalid audience. Expected: {JWT_AUDIENCE}", "payload": unverified, "debug": debug_info}
                except jwt.InvalidIssuerError:
                    return {"error": f"Invalid issuer. Expected: {JWT_ISSUER}", "payload": unverified, "debug": debug_info}
                except Exception as e:
                    return {"error": f"Token validation failed: {e}", "payload": unverified, "debug": debug_info}
                    
            except Exception as e:
                return {"error": f"Debug failed: {e}"}
        
        @self.app.get("/auth/time-check")
        async def time_check():
            """Check server time for debugging."""
            now = datetime.utcnow()
            return {
                "server_time_utc": now.isoformat(),
                "server_timestamp": int(now.timestamp()),
                "server_timezone": "UTC"
            }
        
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
            logger.info(f"Scopes: {token_info.get('scopes', [])}")
            
            # Handle notifications (no response)
            if mcp_request.id is None:
                logger.info(f"Handling notification: {mcp_request.method}")
                return JSONResponse(status_code=202, content=None)
            
            # Check permissions for different operations
            scopes = token_info.get("scopes", [])
            roles = token_info.get("roles", [])
            
            # Handle requests based on method and authorization
            if mcp_request.method == "initialize":
                result = await self.handle_initialize(mcp_request.params or {}, token_info)
            elif mcp_request.method == "tools/list":
                if not self.check_permission(scopes, roles, "tools", "read"):
                    return self.forbidden_response("Insufficient permissions for tools access")
                result = await self.handle_list_tools()
            elif mcp_request.method == "tools/call":
                if not self.check_permission(scopes, roles, "tools", "execute"):
                    return self.forbidden_response("Insufficient permissions for tool execution")
                result = await self.handle_call_tool(mcp_request.params or {}, token_info)
            elif mcp_request.method == "prompts/list":
                if not self.check_permission(scopes, roles, "prompts", "read"):
                    return self.forbidden_response("Insufficient permissions for prompts access")
                result = await self.handle_list_prompts()
            elif mcp_request.method == "prompts/get":
                if not self.check_permission(scopes, roles, "prompts", "read"):
                    return self.forbidden_response("Insufficient permissions for prompts access")
                result = await self.handle_get_prompt(mcp_request.params or {}, token_info)
            elif mcp_request.method == "ping":
                result = {
                    "pong": True,
                    "timestamp": time.time(),
                    "user": username,
                    "authenticated": True
                }
            else:
                return JSONResponse(
                    status_code=400,
                    content={
                        "jsonrpc": "2.0",
                        "id": mcp_request.id,
                        "error": {"code": -32601, "message": f"Method not found: {mcp_request.method}"}
                    }
                )
            
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": mcp_request.id,
                "result": result
            })
        
        @self.app.get("/mcp")
        async def handle_mcp_get():
            """GET endpoint for MCP."""
            return {
                "server": "simple-jwt-mcp",
                "transport": "streamable-http",
                "auth": "jwt",
                "provider": "local"
            }
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint (no auth required)."""
            return {"status": "healthy", "timestamp": time.time()}
    
    def check_permission(self, scopes: List[str], roles: List[str], resource: str, action: str) -> bool:
        """Check if user has permission for a resource/action."""
        # Admin can do everything
        if "admin" in roles:
            return True
        
        # Check specific scope
        if f"mcp:{resource}" in scopes:
            return True
        
        # Check read scope for read actions
        if action == "read" and "mcp:read" in scopes:
            return True
        
        return False
    
    async def verify_token(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
    ) -> Dict[str, Any]:
        """Verify JWT token."""
        if not credentials:
            raise HTTPException(
                status_code=401,
                detail="Authorization header missing",
                headers=self.get_www_authenticate_header()
            )
        
        token = credentials.credentials
        
        try:
            # Verify and decode token with clock skew tolerance
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
            "WWW-Authenticate": f'Bearer realm="mcp-server", resource_metadata="{MCP_SERVER_URL}/.well-known/oauth-protected-resource"'
        }
    
    def forbidden_response(self, detail: str):
        """Return 403 Forbidden response."""
        return JSONResponse(
            status_code=403,
            content={"error": "Forbidden", "detail": detail}
        )
    
    async def handle_initialize(self, params: Dict[str, Any], token_info: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize request."""
        return {
            "protocolVersion": "2025-06-18",
            "capabilities": {
                "tools": {"listChanged": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": {
                "name": "simple-jwt-mcp",
                "version": "0.1.0",
                "description": "MCP Server with simple JWT authentication",
                "authenticatedUser": token_info.get("preferred_username", "unknown")
            }
        }
    
    async def handle_list_tools(self) -> Dict[str, Any]:
        """Handle tools/list request."""
        return {
            "tools": [
                {
                    "name": "echo",
                    "description": "Echo back a message",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "Message to echo"}
                        },
                        "required": ["message"]
                    }
                },
                {
                    "name": "whoami",
                    "description": "Get current user information",
                    "inputSchema": {
                        "type": "object",
                        "properties": {}
                    }
                },
                {
                    "name": "admin_tool",
                    "description": "Admin-only tool",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "description": "Admin action"}
                        },
                        "required": ["action"]
                    }
                }
            ]
        }
    
    async def handle_call_tool(self, params: Dict[str, Any], token_info: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        name = params.get("name")
        arguments = params.get("arguments", {})
        username = token_info.get("preferred_username", "unknown")
        roles = token_info.get("roles", [])
        
        if name == "echo":
            message = arguments.get("message", "Hello, World!")
            return {
                "content": [
                    {"type": "text", "text": f"🔒 Authenticated Echo from {username}: {message}"}
                ],
                "isError": False
            }
        elif name == "whoami":
            user_info = {
                "username": username,
                "subject": token_info.get("sub"),
                "roles": roles,
                "scopes": token_info.get("scopes", []),
                "expires": datetime.fromtimestamp(token_info.get("exp", 0)).isoformat()
            }
            return {
                "content": [
                    {"type": "text", "text": f"🔒 User Info:\n{json.dumps(user_info, indent=2)}"}
                ],
                "isError": False
            }
        elif name == "admin_tool":
            if "admin" not in roles:
                return {
                    "content": [
                        {"type": "text", "text": "❌ Access denied: Admin role required"}
                    ],
                    "isError": True
                }
            
            action = arguments.get("action", "status")
            return {
                "content": [
                    {"type": "text", "text": f"🔐 Admin action '{action}' executed by {username}"}
                ],
                "isError": False
            }
        else:
            return {
                "content": [
                    {"type": "text", "text": f"Unknown tool: {name}"}
                ],
                "isError": True
            }
    
    async def handle_list_prompts(self) -> Dict[str, Any]:
        """Handle prompts/list request."""
        return {
            "prompts": [
                {
                    "name": "authenticated_prompt",
                    "description": "An authenticated prompt",
                    "arguments": [
                        {
                            "name": "topic",
                            "description": "Topic to discuss",
                            "required": True
                        }
                    ]
                }
            ]
        }
    
    async def handle_get_prompt(self, params: Dict[str, Any], token_info: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get request."""
        name = params.get("name")
        arguments = params.get("arguments", {})
        username = token_info.get("preferred_username", "unknown")
        
        if name == "authenticated_prompt":
            topic = arguments.get("topic", "general")
            return {
                "messages": [
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "text",
                                "text": f"🔒 Hello {username}! This is an authenticated prompt about {topic}. You are authenticated via JWT."
                            }
                        ]
                    }
                ]
            }
        else:
            raise ValueError(f"Unknown prompt: {name}")
    
    def run(self, host: str = "127.0.0.1", port: int = 9000):
        """Run the server."""
        logger.info(f"Starting Simple JWT MCP Server on {host}:{port}")
        logger.info("🔑 JWT authentication enabled with local RSA keys")
        logger.info(f"📖 Get demo tokens at: http://{host}:{port}/auth/demo-tokens")
        logger.info(f"🔧 Generate custom token at: POST http://{host}:{port}/auth/token")
        uvicorn.run(self.app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    server = SimpleMCPServer()
    server.run()