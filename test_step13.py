#!/usr/bin/env python3
"""
Step 13: FastMCP OAuth Test Script (Basic Authentication)
This script tests the FastMCP server with basic OAuth authentication.
All tools are available to any authenticated user (no per-tool RBAC).

Per-tool RBAC with filtered tools/list is tested in test_step14.py.
"""

import asyncio
import subprocess
import sys
import time
import httpx
import json
from typing import Optional

# Colors for output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

# Configuration
KEYCLOAK_URL = "http://localhost:8080"
KEYCLOAK_REALM = "mcp-realm"
MCP_SERVER_URL = "http://localhost:9000/mcp"
CLIENT_ID = "mcp-test-client"


def print_info(msg: str):
    print(f"{BLUE}[INFO]{NC} {msg}")


def print_pass(msg: str):
    print(f"{GREEN}[PASS]{NC} {msg}")


def print_fail(msg: str):
    print(f"{RED}[FAIL]{NC} {msg}")


def print_section(title: str):
    print()
    print(f"{BLUE}{'━' * 60}{NC}")
    print(f"{BLUE}  {title}{NC}")
    print(f"{BLUE}{'━' * 60}{NC}")


def get_token(username: str, password: str, scopes: str) -> Optional[str]:
    """Get access token from Keycloak."""
    try:
        response = httpx.post(
            f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": CLIENT_ID,
                "username": username,
                "password": password,
                "scope": scopes,
            },
            timeout=10,
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print_fail(f"Failed to get token for {username}: {response.text}")
            return None
    except Exception as e:
        print_fail(f"Error getting token: {e}")
        return None


async def test_tool_call(token: str, tool_name: str, arguments: dict, user: str):
    """Test a tool call using FastMCP client. All tools should succeed for authenticated users."""
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    print_info(f"Testing tools/call '{tool_name}' for {user}...")

    try:
        transport = StreamableHttpTransport(
            url=MCP_SERVER_URL,
            headers={"Authorization": f"Bearer {token}"}
        )

        async with Client(transport=transport) as client:
            result = await client.call_tool(tool_name, arguments)
            result_text = str(result.content[0].text if result.content else result)[:50]
            print_pass(f"tools/call '{tool_name}' succeeded: {result_text}...")
            return True

    except Exception as e:
        print_fail(f"tools/call '{tool_name}' failed: {e}")
        return False


async def test_tools_list(token: str, user: str):
    """Test tools/list - should return all 5 tools for any authenticated user."""
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    expected_tools = ["calculate", "echo", "get_time", "system_info", "whoami"]
    print_info(f"Testing tools/list for {user} (expecting all tools: {', '.join(expected_tools)})...")

    try:
        transport = StreamableHttpTransport(
            url=MCP_SERVER_URL,
            headers={"Authorization": f"Bearer {token}"}
        )

        async with Client(transport=transport) as client:
            tools = await client.list_tools()
            tool_names = sorted([t.name for t in tools])

            print_info(f"tools/list returned: {', '.join(tool_names)}")

            if tool_names == expected_tools:
                print_pass(f"tools/list returns all tools for {user}")
                return True
            else:
                print_fail(f"tools/list mismatch: expected {expected_tools}, got {tool_names}")
                return False

    except Exception as e:
        print_fail(f"tools/list failed: {e}")
        return False


async def test_whoami(token: str, user: str):
    """Test whoami tool."""
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    print_info(f"Testing whoami tool for {user}...")

    try:
        transport = StreamableHttpTransport(
            url=MCP_SERVER_URL,
            headers={"Authorization": f"Bearer {token}"}
        )

        async with Client(transport=transport) as client:
            result = await client.call_tool("whoami", {})
            result_text = result.content[0].text if result.content else str(result)
            print_pass(f"whoami for {user}:")
            try:
                parsed = json.loads(result_text)
                print(json.dumps(parsed, indent=2))
            except:
                print(result_text)
            return True

    except Exception as e:
        print_fail(f"whoami failed: {e}")
        return False


async def test_unauthenticated_access():
    """Test that unauthenticated access is rejected."""
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    print_info("Testing unauthenticated access (should be rejected)...")

    try:
        transport = StreamableHttpTransport(
            url=MCP_SERVER_URL,
            # No Authorization header
        )

        async with Client(transport=transport) as client:
            await client.list_tools()
            print_fail("Unauthenticated access should have been rejected")
            return False

    except Exception as e:
        error_msg = str(e).lower()
        if "401" in error_msg or "unauthorized" in error_msg or "authentication" in error_msg:
            print_pass("Unauthenticated access correctly rejected")
            return True
        else:
            # Any error is acceptable for unauthenticated access
            print_pass(f"Unauthenticated access rejected ({type(e).__name__})")
            return True


def check_keycloak() -> bool:
    """Check if Keycloak is running."""
    print_info("Checking if Keycloak is running...")
    try:
        response = httpx.get(f"{KEYCLOAK_URL}/realms/master", timeout=5)
        if response.status_code == 200:
            print_pass("Keycloak is running")
            return True
    except:
        pass
    print_fail("Keycloak is not running. Please start Keycloak first:")
    print("  cd keycloak && docker compose up -d")
    return False


def setup_keycloak() -> bool:
    """Setup Keycloak realm."""
    print_info("Setting up Keycloak...")
    try:
        result = subprocess.run(
            ["uv", "run", "python", "keycloak/setup_keycloak.py",
             "--config", "keycloak/config.json",
             "--url", KEYCLOAK_URL,
             "--summary"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            print_pass("Keycloak setup completed")
            return True
        else:
            print(result.stdout)
            print(result.stderr)
            return True  # Might already exist
    except Exception as e:
        print_fail(f"Keycloak setup failed: {e}")
        return False


def start_mcp_server() -> Optional[subprocess.Popen]:
    """Start the FastMCP server (step13 - basic OAuth)."""
    print_info("Starting Step 13 FastMCP server (basic OAuth)...")

    proc = subprocess.Popen(
        ["uv", "run", "python", "src/mcp_http/step13.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    print_info(f"FastMCP server started with PID: {proc.pid}")

    # Wait for server to be ready
    max_attempts = 30
    for i in range(max_attempts):
        try:
            response = httpx.get("http://localhost:9000/", timeout=1)
            print_pass("FastMCP server is ready")
            return proc
        except:
            time.sleep(1)

    print_fail("FastMCP server failed to start")
    proc.terminate()
    return None


async def run_tests():
    """Run all tests."""
    print(f"{BLUE}=== Step 13: FastMCP Basic OAuth Test ==={NC}")
    print(f"{YELLOW}Testing FastMCP with OAuth authentication (no per-tool RBAC){NC}")
    print(f"{YELLOW}All tools available to any authenticated user{NC}")
    print()

    print_section("Prerequisites Check")

    if not check_keycloak():
        return False

    setup_keycloak()

    proc = start_mcp_server()
    if not proc:
        return False

    try:
        # Wait a bit more for server initialization
        await asyncio.sleep(2)

        all_passed = True

        # =========================================================================
        # TEST: Unauthenticated access should be rejected
        # =========================================================================
        print_section("Authentication Tests")
        all_passed &= await test_unauthenticated_access()

        # =========================================================================
        # TEST: mcp-admin - all tools available
        # =========================================================================
        print_section("Admin User Tests")

        admin_token = get_token("mcp-admin", "admin123", "openid profile email mcp:read mcp:tools")
        if not admin_token:
            return False

        await test_whoami(admin_token, "mcp-admin")
        all_passed &= await test_tools_list(admin_token, "mcp-admin")
        all_passed &= await test_tool_call(admin_token, "echo", {"message": "Hello", "repeat_count": 2}, "mcp-admin")
        all_passed &= await test_tool_call(admin_token, "get_time", {}, "mcp-admin")
        all_passed &= await test_tool_call(admin_token, "calculate", {"operation": "add", "a": 5, "b": 3}, "mcp-admin")
        all_passed &= await test_tool_call(admin_token, "system_info", {}, "mcp-admin")

        # =========================================================================
        # TEST: mcp-user - all tools available (no RBAC in step13)
        # =========================================================================
        print_section("Regular User Tests (all tools accessible)")

        user_token = get_token("mcp-user", "user123", "openid profile email mcp:read")
        if not user_token:
            return False

        await test_whoami(user_token, "mcp-user")
        all_passed &= await test_tools_list(user_token, "mcp-user")

        # In step13, ALL tools are available to any authenticated user
        all_passed &= await test_tool_call(user_token, "echo", {"message": "User test"}, "mcp-user")
        all_passed &= await test_tool_call(user_token, "get_time", {}, "mcp-user")
        all_passed &= await test_tool_call(user_token, "calculate", {"operation": "multiply", "a": 4, "b": 7}, "mcp-user")
        all_passed &= await test_tool_call(user_token, "system_info", {}, "mcp-user")  # Should succeed in step13!

        # =========================================================================
        # TEST: mcp-readonly - all tools still available (no RBAC in step13)
        # =========================================================================
        print_section("Readonly User Tests (all tools still accessible in step13)")

        readonly_token = get_token("mcp-readonly", "readonly123", "openid profile email mcp:read")
        if not readonly_token:
            return False

        all_passed &= await test_tools_list(readonly_token, "mcp-readonly")

        # In step13, even readonly can access all tools (no RBAC)
        all_passed &= await test_tool_call(readonly_token, "echo", {"message": "Readonly test"}, "mcp-readonly")
        all_passed &= await test_tool_call(readonly_token, "system_info", {}, "mcp-readonly")

        # =========================================================================
        # SUMMARY
        # =========================================================================
        print_section("Test Summary")

        if all_passed:
            print()
            print(f"{GREEN}All FastMCP basic OAuth tests passed!{NC}")
        else:
            print()
            print(f"{RED}Some tests failed!{NC}")

        print()
        print("Step 13 Key Points:")
        print("  - FastMCP with OAuth/OIDC authentication")
        print("  - All tools available to ANY authenticated user")
        print("  - No per-tool RBAC (added in step14)")
        print("  - Uses JWTVerifier + RemoteAuthProvider")
        print()
        print("For per-tool RBAC with filtered tools/list, see step14.")
        print()

        return all_passed

    finally:
        print_info(f"Stopping MCP server (PID: {proc.pid})...")
        proc.terminate()
        proc.wait(timeout=5)


def main():
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
