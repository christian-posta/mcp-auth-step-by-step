# Step 12: Per-Tool RBAC with Keycloak Integration
# This step demonstrates fine-grained, per-tool authorization using hierarchical scopes.
# Each tool has its own required scope, and mcp:tools grants access to ALL tools.

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Union, Dict, Any, List
from mcp.server import Server
import uvicorn
import os
import sys
import argparse
import logging
import jwt
import time
import platform
import httpx
import json
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from mcp.types import Tool, Prompt, PromptArgument, TextContent, PromptMessage, GetPromptResult
from pydantic import Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env', type=str, default='keycloak_direct.env', help='Path to env file')
    args, _ = parser.parse_known_args()
    env_file = args.env
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"[CONFIG] Loaded environment from {env_file}")
    else:
        print(f"[CONFIG] Env file {env_file} not found, using system environment.")
    print("[CONFIG] KEYCLOAK_URL:", os.environ.get('KEYCLOAK_URL'))
    print("[CONFIG] KEYCLOAK_REALM:", os.environ.get('KEYCLOAK_REALM'))
    print("[CONFIG] MCP_SERVER_URL:", os.environ.get('MCP_SERVER_URL'))
    print("[CONFIG] JWT_AUDIENCE:", os.environ.get('JWT_AUDIENCE'))
    print("[CONFIG] JWT_ISSUER:", os.environ.get('JWT_ISSUER'))

load_config()

KEYCLOAK_URL = os.environ.get('KEYCLOAK_URL', 'http://localhost:8080')
KEYCLOAK_REALM = os.environ.get('KEYCLOAK_REALM', 'mcp-realm')
JWT_ISSUER = os.environ.get('JWT_ISSUER', f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}")
JWT_AUDIENCE = os.environ.get('JWT_AUDIENCE', 'echo-mcp-server')
MCP_SERVER_URL = os.environ.get('MCP_SERVER_URL', 'http://localhost:9000')

security = HTTPBearer(auto_error=False)


# =============================================================================
# TOOL REGISTRY - Central definition of tools with their required scopes
# =============================================================================

class EchoRequest(BaseModel):
    message: str = Field(..., description="Message to echo")
    repeat_count: int = Field(1, ge=1, le=10, description="Number of times to repeat")

class CalculateRequest(BaseModel):
    operation: str = Field(..., description="Operation: add, subtract, multiply, divide")
    a: float = Field(..., description="First operand")
    b: float = Field(..., description="Second operand")

# Tool definitions with their required scopes
TOOL_DEFINITIONS = {
    "echo": {
        "required_scope": "mcp:tools:echo",
        "tool": Tool(
            name="echo",
            description="Echo a message back. Available to all authenticated users.",
            inputSchema=EchoRequest.model_json_schema(),
        ),
    },
    "get_time": {
        "required_scope": "mcp:tools:time",
        "tool": Tool(
            name="get_time",
            description="Get the current server time. Requires mcp:tools:time scope.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    },
    "calculate": {
        "required_scope": "mcp:tools:calc",
        "tool": Tool(
            name="calculate",
            description="Perform basic arithmetic operations. Requires mcp:tools:calc scope.",
            inputSchema=CalculateRequest.model_json_schema(),
        ),
    },
    "system_info": {
        "required_scope": "mcp:tools:admin",
        "tool": Tool(
            name="system_info",
            description="Get server system information. Admin only - requires mcp:tools:admin scope.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    },
}


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

def execute_echo(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the echo tool."""
    args = EchoRequest(**arguments)
    result = args.message * args.repeat_count
    return [TextContent(type="text", text=result)]

def execute_get_time(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the get_time tool."""
    current_time = datetime.now().isoformat()
    return [TextContent(type="text", text=f"Current server time: {current_time}")]

def execute_calculate(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the calculate tool."""
    args = CalculateRequest(**arguments)

    operations = {
        "add": lambda a, b: a + b,
        "subtract": lambda a, b: a - b,
        "multiply": lambda a, b: a * b,
        "divide": lambda a, b: a / b if b != 0 else "Error: Division by zero",
    }

    if args.operation not in operations:
        return [TextContent(type="text", text=f"Error: Unknown operation '{args.operation}'. Use: add, subtract, multiply, divide")]

    result = operations[args.operation](args.a, args.b)
    return [TextContent(type="text", text=f"{args.a} {args.operation} {args.b} = {result}")]

def execute_system_info(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the system_info tool (admin only)."""
    info = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "server_time": datetime.now().isoformat(),
        "keycloak_url": KEYCLOAK_URL,
        "keycloak_realm": KEYCLOAK_REALM,
    }
    return [TextContent(type="text", text=json.dumps(info, indent=2))]

# Map tool names to their execution functions
TOOL_EXECUTORS = {
    "echo": execute_echo,
    "get_time": execute_get_time,
    "calculate": execute_calculate,
    "system_info": execute_system_info,
}


# =============================================================================
# MCP REQUEST MODEL
# =============================================================================

class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: str
    params: Optional[Dict[str, Any]] = None


# =============================================================================
# MCP SERVER WITH PER-TOOL RBAC
# =============================================================================

class PerToolRBACServer:
    """MCP Server with per-tool RBAC using hierarchical scopes."""

    def __init__(self):
        self.app = FastAPI(title="MCP Server with Per-Tool RBAC", version="0.1.0")
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost",
                "http://127.0.0.1",
                "http://localhost:9000",
                "http://127.0.0.1:9000",
                "http://localhost:6274"
            ],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )
        self.server = Server("mcp-per-tool-rbac")
        self.jwks_cache = {}
        self.jwks_cache_time = None
        self.jwks_cache_duration = timedelta(minutes=5)
        self.setup_middleware()
        self.setup_routes()

    async def fetch_keycloak_jwks(self) -> Dict[str, Any]:
        """Fetch JWKS from Keycloak with caching."""
        now = datetime.now()

        if (self.jwks_cache_time and
            now - self.jwks_cache_time < self.jwks_cache_duration and
            self.jwks_cache):
            return self.jwks_cache

        jwks_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
        logger.info(f"Fetching JWKS from Keycloak: {jwks_url}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(jwks_url)
                response.raise_for_status()
                jwks_data = response.json()
                self.jwks_cache = jwks_data
                self.jwks_cache_time = now
                return jwks_data
        except Exception as e:
            logger.error(f"Failed to fetch JWKS from Keycloak: {e}")
            raise HTTPException(status_code=503, detail="Unable to fetch JWKS from Keycloak")

    def get_public_key_from_jwks(self, jwks_data: Dict[str, Any], kid: str) -> Optional[str]:
        """Extract public key from JWKS by key ID."""
        for key in jwks_data.get('keys', []):
            if key.get('kid') == kid:
                try:
                    from cryptography.hazmat.primitives.asymmetric import rsa
                    from cryptography.hazmat.primitives import serialization
                    import base64

                    n = int.from_bytes(base64.urlsafe_b64decode(key['n'] + '=='), 'big')
                    e = int.from_bytes(base64.urlsafe_b64decode(key['e'] + '=='), 'big')

                    public_numbers = rsa.RSAPublicNumbers(e, n)
                    public_key = public_numbers.public_key()

                    pem = public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
                    return pem.decode('utf-8')
                except Exception as e:
                    logger.error(f"Failed to convert JWK to PEM: {e}")
                    return None
        return None

    def setup_middleware(self):
        """Setup Origin validation middleware."""

        @self.app.middleware("http")
        async def origin_validation_middleware(request: Request, call_next):
            if request.url.path == "/health":
                return await call_next(request)

            origin = request.headers.get("origin")

            if not origin:
                return await call_next(request)

            if not origin.startswith("http://localhost") and not origin.startswith("http://127.0.0.1"):
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"Origin '{origin}' is not allowed."}
                )

            return await call_next(request)

    async def verify_token(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
    ) -> Dict[str, Any]:
        """Verify JWT token using Keycloak."""
        if not credentials:
            raise HTTPException(
                status_code=401,
                detail="Authorization header missing",
                headers=self.get_www_authenticate_header()
            )

        token = credentials.credentials

        try:
            header = jwt.get_unverified_header(token)
            kid = header.get('kid')
            if not kid:
                raise HTTPException(status_code=401, detail="Token missing key ID")

            jwks_data = await self.fetch_keycloak_jwks()
            public_key_pem = self.get_public_key_from_jwks(jwks_data, kid)
            if not public_key_pem:
                raise HTTPException(status_code=401, detail="Unable to verify token signature")

            payload = jwt.decode(
                token,
                public_key_pem,
                algorithms=["RS256"],
                audience=JWT_AUDIENCE,
                issuer=JWT_ISSUER,
                options={"verify_signature": True, "verify_exp": True, "verify_iat": False}
            )

            # Extract scopes from token
            scopes = []
            if 'scope' in payload:
                scopes = payload['scope'].split(' ')
            elif 'scopes' in payload:
                scopes = payload['scopes']
            payload['scopes'] = scopes

            username = payload.get('preferred_username', payload.get('sub', 'unknown'))
            logger.info(f"Token validated for user: {username}, scopes: {scopes}")

            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidAudienceError:
            raise HTTPException(status_code=401, detail="Invalid token audience")
        except jwt.InvalidIssuerError:
            raise HTTPException(status_code=401, detail="Invalid token issuer")
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            raise HTTPException(status_code=401, detail="Invalid token")

    def get_www_authenticate_header(self) -> Dict[str, str]:
        """Get WWW-Authenticate header for 401 responses."""
        return {
            "WWW-Authenticate": f'Bearer realm="mcp-server", resource_metadata="{MCP_SERVER_URL}/.well-known/oauth-protected-resource"'
        }

    # =========================================================================
    # PER-TOOL AUTHORIZATION
    # =========================================================================

    def check_tool_permission(self, scopes: List[str], tool_name: str) -> bool:
        """
        Check if user has permission to access a specific tool.

        Hierarchy:
        - mcp:tools grants access to ALL tools (hierarchical)
        - mcp:tools:<tool> grants access to specific tool only
        """
        # Hierarchical: mcp:tools grants access to all tools
        if "mcp:tools" in scopes:
            logger.info(f"Hierarchical access granted for tool '{tool_name}' via mcp:tools scope")
            return True

        # Check tool-specific scope
        tool_def = TOOL_DEFINITIONS.get(tool_name)
        if not tool_def:
            logger.warning(f"Unknown tool: {tool_name}")
            return False

        required_scope = tool_def["required_scope"]
        if required_scope in scopes:
            logger.info(f"Specific access granted for tool '{tool_name}' via {required_scope} scope")
            return True

        logger.warning(f"Access denied for tool '{tool_name}'. Required: {required_scope} or mcp:tools. User scopes: {scopes}")
        return False

    def get_accessible_tools(self, scopes: List[str]) -> List[Tool]:
        """
        Get list of tools accessible to the user based on their scopes.
        Only returns tools the user has permission to call.
        """
        accessible = []
        for tool_name, tool_def in TOOL_DEFINITIONS.items():
            if self.check_tool_permission(scopes, tool_name):
                accessible.append(tool_def["tool"])
        return accessible

    def forbidden_response(self, detail: str, tool_name: Optional[str] = None):
        """Return 403 Forbidden response with helpful information."""
        error_data = {"detail": detail}
        if tool_name and tool_name in TOOL_DEFINITIONS:
            error_data["required_scope"] = TOOL_DEFINITIONS[tool_name]["required_scope"]
            error_data["alternative_scope"] = "mcp:tools (grants access to all tools)"

        return JSONResponse(
            status_code=403,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32001,
                    "message": "Forbidden",
                    "data": error_data
                }
            }
        )

    # =========================================================================
    # ROUTES
    # =========================================================================

    def setup_routes(self):
        """Setup server routes."""

        @self.app.get("/.well-known/oauth-protected-resource")
        async def protected_resource_metadata():
            """OAuth 2.0 Protected Resource Metadata (RFC 9728)."""
            # List all supported scopes including per-tool scopes
            all_scopes = ["echo-mcp-server-audience", "mcp:read", "mcp:tools", "mcp:prompts"]
            for tool_def in TOOL_DEFINITIONS.values():
                all_scopes.append(tool_def["required_scope"])

            return {
                "resource": MCP_SERVER_URL,
                "authorization_servers": [f"{JWT_ISSUER}"],
                "scopes_supported": all_scopes,
                "bearer_methods_supported": ["header"],
                "resource_documentation": f"{MCP_SERVER_URL}/docs",
                "mcp_protocol_version": "2025-06-18",
                "resource_type": "mcp-server",
                "scope_hierarchy": {
                    "mcp:tools": "Grants access to ALL tools",
                    "mcp:tools:echo": "Grants access to echo tool only",
                    "mcp:tools:time": "Grants access to get_time tool only",
                    "mcp:tools:calc": "Grants access to calculate tool only",
                    "mcp:tools:admin": "Grants access to system_info tool only (admin)",
                }
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
                "feature": "per-tool-rbac",
                "keycloak_integration": True,
                "jwks_available": jwks_available,
                "available_tools": list(TOOL_DEFINITIONS.keys()),
                "scope_hierarchy": "mcp:tools grants access to all tools"
            }

        @self.app.get("/mcp")
        async def handle_mcp_get(request: Request):
            return JSONResponse(
                status_code=405,
                content={"detail": "Method Not Allowed - Use POST for MCP requests"}
            )

        @self.app.post("/mcp")
        async def handle_mcp_request(
            request: Request,
            token_info: Dict[str, Any] = Depends(self.verify_token)
        ):
            """Handle MCP requests with per-tool RBAC."""
            try:
                body_bytes = await request.body()
                body_json = json.loads(body_bytes.decode('utf-8'))
            except json.JSONDecodeError as e:
                return JSONResponse(
                    status_code=400,
                    content={"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}
                )

            try:
                mcp_request = MCPRequest(**body_json)
            except Exception as e:
                return JSONResponse(
                    status_code=400,
                    content={"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}}
                )

            username = token_info.get("preferred_username", token_info.get("sub", "unknown"))
            scopes = token_info.get("scopes", [])

            logger.info(f"MCP request from user '{username}': {mcp_request.method}")

            # Handle notifications
            if mcp_request.id is None:
                return JSONResponse(status_code=202, content=None)

            try:
                if mcp_request.method == "initialize":
                    result = {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {"tools": {"listChanged": False}, "prompts": {"listChanged": False}},
                        "serverInfo": {
                            "name": "mcp-per-tool-rbac",
                            "version": "0.1.0",
                            "feature": "per-tool-rbac",
                            "authenticatedUser": username,
                            "userScopes": scopes,
                        }
                    }

                elif mcp_request.method == "tools/list":
                    # Return ONLY tools the user has access to
                    accessible_tools = self.get_accessible_tools(scopes)
                    logger.info(f"User '{username}' has access to {len(accessible_tools)} tools: {[t.name for t in accessible_tools]}")
                    result = {
                        "tools": [tool.model_dump() for tool in accessible_tools]
                    }

                elif mcp_request.method == "tools/call":
                    tool_name = mcp_request.params.get("name") if mcp_request.params else None
                    if not tool_name:
                        return JSONResponse(
                            status_code=400,
                            content={"jsonrpc": "2.0", "id": mcp_request.id, "error": {"code": -32602, "message": "Missing tool name"}}
                        )

                    # Check per-tool permission
                    if not self.check_tool_permission(scopes, tool_name):
                        return self.forbidden_response(
                            f"Insufficient permissions for tool '{tool_name}'",
                            tool_name=tool_name
                        )

                    # Execute the tool
                    executor = TOOL_EXECUTORS.get(tool_name)
                    if not executor:
                        return JSONResponse(
                            status_code=400,
                            content={"jsonrpc": "2.0", "id": mcp_request.id, "error": {"code": -32602, "message": f"Unknown tool: {tool_name}"}}
                        )

                    arguments = mcp_request.params.get("arguments", {})
                    content = executor(arguments)
                    result = {
                        "content": [item.model_dump() for item in content],
                        "isError": False
                    }

                elif mcp_request.method == "prompts/list":
                    if "mcp:prompts" not in scopes:
                        return self.forbidden_response("Insufficient permissions for prompts access")
                    result = {"prompts": []}

                elif mcp_request.method == "ping":
                    result = {
                        "pong": True,
                        "timestamp": time.time(),
                        "user": username,
                        "feature": "per-tool-rbac",
                        "accessible_tools": [t.name for t in self.get_accessible_tools(scopes)],
                    }

                else:
                    return JSONResponse(
                        status_code=400,
                        content={"jsonrpc": "2.0", "id": mcp_request.id, "error": {"code": -32601, "message": "Method not found"}}
                    )

                return JSONResponse(content={"jsonrpc": "2.0", "id": mcp_request.id, "result": result})

            except Exception as e:
                logger.error(f"Error processing MCP method {mcp_request.method}: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"jsonrpc": "2.0", "id": mcp_request.id, "error": {"code": -32603, "message": str(e)}}
                )

    def run(self):
        uvicorn.run(self.app, host="0.0.0.0", port=9000)


def main():
    server = PerToolRBACServer()
    server.run()


if __name__ == "__main__":
    main()
