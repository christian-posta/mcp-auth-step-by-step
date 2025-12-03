# Step 13: FastMCP with OAuth/OIDC Authentication
# This step demonstrates how to use the modern FastMCP framework with Keycloak
# for OAuth/OIDC authentication. This is a rewrite of step10 using FastMCP.
#
# Key differences from Step 10 (FastAPI):
# - Uses FastMCP's built-in JWTVerifier instead of manual JWT validation
# - Uses RemoteAuthProvider for OAuth integration
# - Uses get_access_token() for accessing token claims in tools
# - Much less boilerplate code (~200 lines vs ~600 lines)
#
# This step focuses on basic authentication. Per-tool RBAC is added in step14.

import os
import argparse
import json
import platform
from datetime import datetime
from pydantic import AnyHttpUrl
from dotenv import load_dotenv

from fastmcp import FastMCP
from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import get_access_token, AccessToken


# =============================================================================
# CONFIGURATION
# =============================================================================

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

load_config()

KEYCLOAK_URL = os.environ.get('KEYCLOAK_URL', 'http://localhost:8080')
KEYCLOAK_REALM = os.environ.get('KEYCLOAK_REALM', 'mcp-realm')
JWT_ISSUER = os.environ.get('JWT_ISSUER', f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}")
JWT_AUDIENCE = os.environ.get('JWT_AUDIENCE', 'echo-mcp-server')
MCP_SERVER_URL = os.environ.get('MCP_SERVER_URL', 'http://localhost:9000')


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_user_info() -> dict:
    """Get information about the current authenticated user."""
    token: AccessToken | None = get_access_token()
    if token is None:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "client_id": token.client_id,
        "scopes": token.scopes,
        "claims": token.claims,
    }


# =============================================================================
# FASTMCP SERVER SETUP WITH KEYCLOAK AUTH
# =============================================================================

# Configure JWT verification with Keycloak
token_verifier = JWTVerifier(
    jwks_uri=f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs",
    issuer=JWT_ISSUER,
    audience=JWT_AUDIENCE,
)

# Create RemoteAuthProvider for OAuth integration
auth = RemoteAuthProvider(
    token_verifier=token_verifier,
    authorization_servers=[AnyHttpUrl(f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}")],
    base_url=MCP_SERVER_URL,
)

# Create FastMCP server with authentication
mcp = FastMCP(
    name="MCP Server with OAuth (FastMCP)",
    auth=auth,
)


# =============================================================================
# TOOL IMPLEMENTATIONS
# All tools are available to any authenticated user in this step.
# Per-tool RBAC is demonstrated in step14.
# =============================================================================

@mcp.tool
async def echo(message: str, repeat_count: int = 1) -> str:
    """
    Echo a message back.

    Args:
        message: The message to echo
        repeat_count: Number of times to repeat (1-10)

    Returns:
        The echoed message
    """
    if repeat_count < 1:
        repeat_count = 1
    if repeat_count > 10:
        repeat_count = 10

    return message * repeat_count


@mcp.tool
async def get_time() -> str:
    """
    Get the current server time.

    Returns:
        Current server time in ISO format
    """
    current_time = datetime.now().isoformat()
    return f"Current server time: {current_time}"


@mcp.tool
async def calculate(operation: str, a: float, b: float) -> str:
    """
    Perform basic arithmetic operations.

    Args:
        operation: One of: add, subtract, multiply, divide
        a: First operand
        b: Second operand

    Returns:
        Result of the calculation
    """
    operations = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y if y != 0 else "Error: Division by zero",
    }

    if operation not in operations:
        return f"Error: Unknown operation '{operation}'. Use: add, subtract, multiply, divide"

    result = operations[operation](a, b)
    return f"{a} {operation} {b} = {result}"


@mcp.tool
async def system_info() -> str:
    """
    Get server system information.

    Returns:
        JSON string with system information
    """
    user = get_user_info()

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
        "requested_by": user.get("client_id", "unknown"),
        "user_scopes": user.get("scopes", []),
    }
    return json.dumps(info, indent=2)


@mcp.tool
async def whoami() -> str:
    """
    Get information about the authenticated user.

    Returns:
        JSON string with user information
    """
    user = get_user_info()

    result = {
        "authenticated": user.get("authenticated", False),
        "client_id": user.get("client_id"),
        "scopes": user.get("scopes", []),
    }
    return json.dumps(result, indent=2)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Run the FastMCP server."""
    print(f"[STARTUP] FastMCP Server with OAuth Authentication")
    print(f"[STARTUP] Keycloak URL: {KEYCLOAK_URL}")
    print(f"[STARTUP] Keycloak Realm: {KEYCLOAK_REALM}")
    print(f"[STARTUP] JWT Issuer: {JWT_ISSUER}")
    print(f"[STARTUP] JWT Audience: {JWT_AUDIENCE}")
    print(f"[STARTUP] MCP Server URL: {MCP_SERVER_URL}")
    print(f"[STARTUP] All tools available to authenticated users")
    print()

    # Run with HTTP transport on port 9000
    mcp.run(transport="http", host="0.0.0.0", port=9000)


if __name__ == "__main__":
    main()
