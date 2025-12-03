# Step 14: Per-Tool RBAC with FastMCP + Filtered tools/list
# This step extends step13 with per-tool authorization (RBAC) and filtered
# tools/list response - users only see tools they have permission to use.
#
# Key features added in this step:
# - TOOL_SCOPES mapping for per-tool permission requirements
# - has_tool_permission() and require_tool_permission() helpers
# - RBACFastMCP subclass that filters tools/list based on user scopes
# - Hierarchical scope support: mcp:tools grants access to ALL tools
#
# This matches the functionality of step12 (FastAPI) but with FastMCP.

import os
import argparse
import json
import platform
from datetime import datetime
from typing import List
from pydantic import AnyHttpUrl
from dotenv import load_dotenv

from fastmcp import FastMCP
from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import get_access_token, AccessToken
from mcp.types import Tool as MCPTool


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
# TOOL SCOPE REQUIREMENTS
# =============================================================================

TOOL_SCOPES = {
    "echo": "mcp:tools:echo",
    "get_time": "mcp:tools:time",
    "calculate": "mcp:tools:calc",
    "system_info": "mcp:tools:admin",
}


# =============================================================================
# AUTHORIZATION HELPERS
# =============================================================================

def _check_tool_permission_with_scopes(scopes: list, tool_name: str) -> bool:
    """Check if scopes grant access to a tool (used by list_tools filter)."""
    # Hierarchical: mcp:tools grants access to all tools
    if "mcp:tools" in scopes:
        return True

    # Check tool-specific scope
    required_scope = TOOL_SCOPES.get(tool_name)
    if required_scope and required_scope in scopes:
        return True

    return False


def has_tool_permission(tool_name: str) -> bool:
    """
    Check if the current user has permission to use a specific tool.

    Hierarchy:
    - mcp:tools grants access to ALL tools
    - mcp:tools:<tool> grants access to specific tool only
    """
    token: AccessToken | None = get_access_token()

    if token is None:
        return False

    scopes = token.scopes or []
    return _check_tool_permission_with_scopes(scopes, tool_name)


def require_tool_permission(tool_name: str) -> None:
    """Raise an error if the user doesn't have permission for the tool."""
    if not has_tool_permission(tool_name):
        required = TOOL_SCOPES.get(tool_name, "unknown")
        raise ValueError(
            f"Insufficient permissions for tool '{tool_name}'. "
            f"Required scope: {required} or mcp:tools (hierarchical)"
        )


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
# CUSTOM FASTMCP WITH FILTERED TOOLS LIST
# =============================================================================

class RBACFastMCP(FastMCP):
    """
    FastMCP subclass that filters tools/list based on user permissions.

    This ensures users only see tools they have permission to use,
    preventing the AI from suggesting unavailable tools.
    """

    def _setup_handlers(self) -> None:
        """Set up core MCP protocol handlers with custom RBAC filtering."""
        # Register our filtered list_tools instead of the default
        self._mcp_server.list_tools()(self._filtered_list_tools)
        # Keep default handlers for everything else
        self._mcp_server.call_tool(validate_input=self.strict_input_validation)(
            self._call_tool_mcp
        )
        self._mcp_server.list_resources()(self._list_resources_mcp)
        self._mcp_server.read_resource()(self._read_resource_mcp)
        self._mcp_server.list_prompts()(self._list_prompts_mcp)
        self._mcp_server.get_prompt()(self._get_prompt_mcp)
        self._mcp_server.list_resource_templates()(self._list_resource_templates_mcp)

    async def _filtered_list_tools(self) -> List[MCPTool]:
        """List only tools the current user has permission to access."""
        # Get all tools from the tool manager (async method returns dict[key, Tool])
        all_tools = await self._tool_manager.get_tools()

        # Get current user's scopes
        token: AccessToken | None = get_access_token()
        scopes = token.scopes if token else []

        # Filter tools based on permissions
        accessible_tools = []
        for key, tool in all_tools.items():
            tool_name = tool.name
            # whoami is always accessible (no specific scope required)
            if tool_name == "whoami" or _check_tool_permission_with_scopes(scopes, tool_name):
                accessible_tools.append(
                    tool.to_mcp_tool(
                        name=key,
                        include_fastmcp_meta=self.include_fastmcp_meta,
                    )
                )

        return accessible_tools


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

# Create RBAC-enabled FastMCP server with authentication
mcp = RBACFastMCP(
    name="MCP Server with Per-Tool RBAC (FastMCP)",
    auth=auth,
)


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

@mcp.tool
async def echo(message: str, repeat_count: int = 1) -> str:
    """
    Echo a message back. Requires mcp:tools:echo scope.

    Args:
        message: The message to echo
        repeat_count: Number of times to repeat (1-10)

    Returns:
        The echoed message
    """
    require_tool_permission("echo")

    if repeat_count < 1:
        repeat_count = 1
    if repeat_count > 10:
        repeat_count = 10

    return message * repeat_count


@mcp.tool
async def get_time() -> str:
    """
    Get the current server time. Requires mcp:tools:time scope.

    Returns:
        Current server time in ISO format
    """
    require_tool_permission("get_time")

    current_time = datetime.now().isoformat()
    return f"Current server time: {current_time}"


@mcp.tool
async def calculate(operation: str, a: float, b: float) -> str:
    """
    Perform basic arithmetic operations. Requires mcp:tools:calc scope.

    Args:
        operation: One of: add, subtract, multiply, divide
        a: First operand
        b: Second operand

    Returns:
        Result of the calculation
    """
    require_tool_permission("calculate")

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
    Get server system information. Admin only - requires mcp:tools:admin scope.

    Returns:
        JSON string with system information
    """
    require_tool_permission("system_info")

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
    Get information about the authenticated user and their permissions.
    This tool is available to all authenticated users.

    Returns:
        JSON string with user information and accessible tools
    """
    user = get_user_info()

    # Determine which tools the user can access
    accessible_tools = []
    for tool_name in TOOL_SCOPES.keys():
        if has_tool_permission(tool_name):
            accessible_tools.append(tool_name)

    result = {
        "authenticated": user.get("authenticated", False),
        "client_id": user.get("client_id"),
        "scopes": user.get("scopes", []),
        "accessible_tools": accessible_tools,
        "scope_hierarchy": {
            "mcp:tools": "Grants access to ALL tools",
            "mcp:tools:echo": "echo tool only",
            "mcp:tools:time": "get_time tool only",
            "mcp:tools:calc": "calculate tool only",
            "mcp:tools:admin": "system_info tool only (admin)",
        }
    }
    return json.dumps(result, indent=2)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Run the FastMCP server."""
    print(f"[STARTUP] FastMCP Server with Per-Tool RBAC")
    print(f"[STARTUP] Keycloak URL: {KEYCLOAK_URL}")
    print(f"[STARTUP] Keycloak Realm: {KEYCLOAK_REALM}")
    print(f"[STARTUP] JWT Issuer: {JWT_ISSUER}")
    print(f"[STARTUP] JWT Audience: {JWT_AUDIENCE}")
    print(f"[STARTUP] MCP Server URL: {MCP_SERVER_URL}")
    print(f"[STARTUP] Tool scopes: {TOOL_SCOPES}")
    print(f"[STARTUP] tools/list filtered by user permissions")
    print()

    # Run with HTTP transport on port 9000
    mcp.run(transport="http", host="0.0.0.0", port=9000)


if __name__ == "__main__":
    main()
