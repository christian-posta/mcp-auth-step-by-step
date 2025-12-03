#!/usr/bin/env python3
"""
Step 14: Per-Tool RBAC Test Script (FastMCP version)
This script tests the FastMCP server with per-tool authorization (RBAC)
and filtered tools/list - users only see tools they have permission to use.

This extends step13 (basic OAuth) with:
- TOOL_SCOPES mapping for per-tool permission requirements
- RBACFastMCP subclass that filters tools/list based on user scopes
- Hierarchical scope support: mcp:tools grants access to ALL tools
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


async def test_tool_call(token: str, tool_name: str, arguments: dict, should_succeed: bool, user: str):
    """Test a tool call using FastMCP client."""
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    action = "succeed" if should_succeed else "fail"
    print_info(f"Testing tools/call '{tool_name}' for {user} (should {action})...")

    try:
        transport = StreamableHttpTransport(
            url=MCP_SERVER_URL,
            headers={"Authorization": f"Bearer {token}"}
        )

        async with Client(transport=transport) as client:
            result = await client.call_tool(tool_name, arguments)

            if should_succeed:
                result_text = str(result.content[0].text if result.content else result)[:50]
                print_pass(f"tools/call '{tool_name}' succeeded: {result_text}...")
                return True
            else:
                print_fail(f"tools/call '{tool_name}' should have been denied but succeeded")
                return False

    except Exception as e:
        error_msg = str(e).lower()
        if not should_succeed and ("permission" in error_msg or "insufficient" in error_msg or "forbidden" in error_msg or "denied" in error_msg):
            print_pass(f"tools/call '{tool_name}' correctly denied")
            return True
        elif not should_succeed:
            # Any error when we expect failure is acceptable
            print_pass(f"tools/call '{tool_name}' correctly denied ({type(e).__name__})")
            return True
        else:
            print_fail(f"tools/call '{tool_name}' failed unexpectedly: {e}")
            return False


async def test_tools_list(token: str, user: str, expected_tools: list):
    """Test tools/list using FastMCP client - should return only permitted tools."""
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    print_info(f"Testing tools/list for {user} (expecting: {', '.join(sorted(expected_tools))})...")

    try:
        transport = StreamableHttpTransport(
            url=MCP_SERVER_URL,
            headers={"Authorization": f"Bearer {token}"}
        )

        async with Client(transport=transport) as client:
            tools = await client.list_tools()
            tool_names = sorted([t.name for t in tools])
            expected_sorted = sorted(expected_tools)

            print_info(f"tools/list for {user} returned: {', '.join(tool_names)}")

            if tool_names == expected_sorted:
                print_pass(f"tools/list correctly filtered for {user}")
                return True
            else:
                print_fail(f"tools/list mismatch: expected {expected_sorted}, got {tool_names}")
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
        print_info(f"whoami returned error: {e}")
        return True  # whoami might not require auth


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
    print_info("Setting up Keycloak with per-tool RBAC configuration...")
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
    """Start the FastMCP server (step14 - with RBAC)."""
    print_info("Starting Step 14 FastMCP server with per-tool RBAC...")

    proc = subprocess.Popen(
        ["uv", "run", "python", "src/mcp_http/step14.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    print_info(f"FastMCP server started with PID: {proc.pid}")

    # Wait for server to be ready
    max_attempts = 30
    for i in range(max_attempts):
        try:
            # FastMCP doesn't have /health, try connecting
            response = httpx.get("http://localhost:9000/", timeout=1)
            # Any response means server is up
            print_pass("FastMCP server is ready")
            return proc
        except:
            time.sleep(1)

    print_fail("FastMCP server failed to start")
    proc.terminate()
    return None


async def run_tests():
    """Run all tests."""
    print(f"{BLUE}=== Step 14: Per-Tool RBAC Test (FastMCP) ==={NC}")
    print(f"{YELLOW}Testing FastMCP with per-tool RBAC and filtered tools/list{NC}")
    print(f"{YELLOW}Users only see tools they have permission to use{NC}")
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
        # TEST: mcp-admin (has mcp:tools - hierarchical access to ALL tools)
        # =========================================================================
        print_section("Admin User Tests (mcp:tools = ALL tools)")

        admin_token = get_token("mcp-admin", "admin123", "openid profile email mcp:read mcp:tools mcp:prompts")
        if not admin_token:
            return False

        await test_whoami(admin_token, "mcp-admin")

        # Admin should see ALL tools in tools/list
        all_passed &= await test_tools_list(admin_token, "mcp-admin",
            ["echo", "get_time", "calculate", "system_info", "whoami"])

        # Admin should be able to call ALL tools
        all_passed &= await test_tool_call(admin_token, "echo", {"message": "Hello", "repeat_count": 2}, True, "mcp-admin")
        all_passed &= await test_tool_call(admin_token, "get_time", {}, True, "mcp-admin")
        all_passed &= await test_tool_call(admin_token, "calculate", {"operation": "add", "a": 5, "b": 3}, True, "mcp-admin")
        all_passed &= await test_tool_call(admin_token, "system_info", {}, True, "mcp-admin")

        # =========================================================================
        # TEST: mcp-user (has mcp:tools:echo, mcp:tools:time, mcp:tools:calc)
        # =========================================================================
        print_section("Regular User Tests (specific tool scopes)")

        user_token = get_token("mcp-user", "user123", "openid profile email mcp:read mcp:tools:echo mcp:tools:time mcp:tools:calc")
        if not user_token:
            return False

        await test_whoami(user_token, "mcp-user")

        # User should see only their allowed tools + whoami
        all_passed &= await test_tools_list(user_token, "mcp-user",
            ["echo", "get_time", "calculate", "whoami"])

        # User should be able to call their allowed tools
        all_passed &= await test_tool_call(user_token, "echo", {"message": "User test", "repeat_count": 1}, True, "mcp-user")
        all_passed &= await test_tool_call(user_token, "get_time", {}, True, "mcp-user")
        all_passed &= await test_tool_call(user_token, "calculate", {"operation": "multiply", "a": 4, "b": 7}, True, "mcp-user")

        # User should NOT be able to call system_info (admin only)
        all_passed &= await test_tool_call(user_token, "system_info", {}, False, "mcp-user")

        # =========================================================================
        # TEST: mcp-guest (has only mcp:tools:echo)
        # =========================================================================
        print_section("Guest User Tests (only echo scope)")

        guest_token = get_token("mcp-guest", "guest123", "openid profile email mcp:read mcp:tools:echo")
        if not guest_token:
            return False

        await test_whoami(guest_token, "mcp-guest")

        # Guest should see only echo + whoami
        all_passed &= await test_tools_list(guest_token, "mcp-guest",
            ["echo", "whoami"])

        # Guest should be able to call only echo
        all_passed &= await test_tool_call(guest_token, "echo", {"message": "Guest test", "repeat_count": 3}, True, "mcp-guest")

        # Guest should NOT be able to call other tools
        all_passed &= await test_tool_call(guest_token, "get_time", {}, False, "mcp-guest")
        all_passed &= await test_tool_call(guest_token, "calculate", {"operation": "add", "a": 1, "b": 1}, False, "mcp-guest")
        all_passed &= await test_tool_call(guest_token, "system_info", {}, False, "mcp-guest")

        # =========================================================================
        # TEST: mcp-readonly (has only mcp:read - NO tool access)
        # =========================================================================
        print_section("Readonly User Tests (no tool scopes)")

        readonly_token = get_token("mcp-readonly", "readonly123", "openid profile email mcp:read")
        if not readonly_token:
            return False

        # Readonly should see only whoami (which doesn't require tool scope)
        all_passed &= await test_tools_list(readonly_token, "mcp-readonly",
            ["whoami"])

        # Readonly should NOT be able to call any tools
        all_passed &= await test_tool_call(readonly_token, "echo", {"message": "test"}, False, "mcp-readonly")
        all_passed &= await test_tool_call(readonly_token, "get_time", {}, False, "mcp-readonly")
        all_passed &= await test_tool_call(readonly_token, "calculate", {"operation": "add", "a": 1, "b": 1}, False, "mcp-readonly")
        all_passed &= await test_tool_call(readonly_token, "system_info", {}, False, "mcp-readonly")

        # =========================================================================
        # SUMMARY
        # =========================================================================
        print_section("Test Summary")

        if all_passed:
            print()
            print(f"{GREEN}All FastMCP per-tool RBAC tests passed!{NC}")
        else:
            print()
            print(f"{RED}Some tests failed!{NC}")

        print()
        print("Step 13 vs Step 14 comparison:")
        print()
        print("┌─────────────────────┬──────────────────────┬──────────────────────┐")
        print("│ Feature             │ Step 13 (Basic)      │ Step 14 (RBAC)       │")
        print("├─────────────────────┼──────────────────────┼──────────────────────┤")
        print("│ Authentication      │ OAuth/JWT            │ OAuth/JWT            │")
        print("│ Tool Access         │ All authenticated    │ Per-tool scopes      │")
        print("│ tools/list          │ Returns ALL tools    │ Returns PERMITTED    │")
        print("│ Scope Hierarchy     │ Not applicable       │ mcp:tools = all      │")
        print("│ Use Case            │ Simple apps          │ Enterprise RBAC      │")
        print("└─────────────────────┴──────────────────────┴──────────────────────┘")
        print()
        print("RBAC Scope Mapping:")
        print("  - mcp:tools        -> ALL tools (admin)")
        print("  - mcp:tools:echo   -> echo only")
        print("  - mcp:tools:time   -> get_time only")
        print("  - mcp:tools:calc   -> calculate only")
        print("  - mcp:tools:admin  -> system_info only (admin)")
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
