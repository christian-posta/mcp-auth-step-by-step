#!/bin/bash

# Step 12: Per-Tool RBAC Test Script
# This script tests the MCP server with per-tool authorization
# Demonstrates hierarchical scopes: mcp:tools grants access to all tools

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
KEYCLOAK_URL="http://localhost:8080"
KEYCLOAK_REALM="mcp-realm"
MCP_SERVER_URL="http://localhost:9000"
CLIENT_ID="mcp-test-client"

# Global variables
MCP_SERVER_PID=""

echo -e "${BLUE}=== Step 12: Per-Tool RBAC Test ===${NC}"
echo -e "${YELLOW}Testing hierarchical scope-based authorization for individual tools${NC}"
echo ""

# Helper functions
print_info() {
    echo -e "\033[1;34m[INFO]\033[0m $1"
}

print_status() {
    echo -e "\033[1;32m[PASS]\033[0m $1"
}

print_error() {
    echo -e "\033[1;31m[FAIL]\033[0m $1"
}

print_section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Cleanup function
cleanup() {
    if [ ! -z "$MCP_SERVER_PID" ]; then
        print_info "Stopping MCP server (PID: $MCP_SERVER_PID)..."
        kill $MCP_SERVER_PID 2>/dev/null || true
        wait $MCP_SERVER_PID 2>/dev/null || true
    fi
}

trap cleanup EXIT

# Check if Keycloak is running
check_keycloak() {
    print_info "Checking if Keycloak is running..."
    if curl -s "$KEYCLOAK_URL/realms/master" > /dev/null 2>&1; then
        print_status "Keycloak is running"
    else
        print_error "Keycloak is not running. Please start Keycloak first:"
        echo "  cd keycloak && docker compose up -d"
        exit 1
    fi
}

# Setup Keycloak
setup_keycloak() {
    print_info "Setting up Keycloak with per-tool RBAC configuration..."

    if [ ! -f "keycloak/config.json" ]; then
        print_error "Keycloak configuration file not found: keycloak/config.json"
        exit 1
    fi

    cd keycloak
    uv run python setup_keycloak.py --config config.json --url "$KEYCLOAK_URL" --summary
    cd ..

    print_status "Keycloak setup completed"
}

# Start MCP server
start_mcp_server() {
    print_info "Starting Step 12 MCP server with per-tool RBAC..."

    if [ ! -f "src/mcp_http/step12.py" ]; then
        print_error "MCP server file not found: src/mcp_http/step12.py"
        exit 1
    fi

    uv run python src/mcp_http/step12.py &
    MCP_SERVER_PID=$!

    print_info "MCP server started with PID: $MCP_SERVER_PID"

    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s "$MCP_SERVER_URL/health" > /dev/null 2>&1; then
            print_status "MCP server is ready"
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done

    print_error "MCP server failed to start"
    exit 1
}

# Get access token from Keycloak
get_token() {
    local username=$1
    local password=$2
    local scopes=$3

    local token_response=$(curl -s -X POST \
        "$KEYCLOAK_URL/realms/$KEYCLOAK_REALM/protocol/openid-connect/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "grant_type=password" \
        -d "client_id=$CLIENT_ID" \
        -d "username=$username" \
        -d "password=$password" \
        -d "scope=$scopes")

    if echo "$token_response" | grep -q "access_token"; then
        echo "$token_response" | jq -r '.access_token'
    else
        print_error "Failed to get token for $username"
        echo "$token_response" | jq '.' >&2
        return 1
    fi
}

# Test tools/list - returns only accessible tools
test_tools_list() {
    local token=$1
    local user=$2
    local expected_tools=$3

    print_info "Testing tools/list for $user (expecting: $expected_tools)..."

    local response=$(curl -s -X POST "$MCP_SERVER_URL/mcp" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $token" \
        -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}')

    local actual_tools=$(echo "$response" | jq -r '[.result.tools[].name] | sort | join(", ")')

    if [ "$actual_tools" = "$expected_tools" ]; then
        print_status "tools/list for $user: $actual_tools"
    else
        print_error "tools/list for $user: expected '$expected_tools', got '$actual_tools'"
        echo "$response" | jq '.'
        exit 1
    fi
}

# Test tools/call - should succeed or fail based on permissions
test_tool_call() {
    local token=$1
    local tool_name=$2
    local arguments=$3
    local should_succeed=$4
    local user=$5

    print_info "Testing tools/call '$tool_name' for $user (should $should_succeed)..."

    local temp_json=$(mktemp)
    echo "{\"jsonrpc\": \"2.0\", \"id\": 1, \"method\": \"tools/call\", \"params\": {\"name\": \"$tool_name\", \"arguments\": $arguments}}" > "$temp_json"

    local response=$(curl -s -X POST "$MCP_SERVER_URL/mcp" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $token" \
        -d "@$temp_json")

    rm -f "$temp_json"

    if [ "$should_succeed" = "succeed" ]; then
        if echo "$response" | grep -q '"result"'; then
            local result=$(echo "$response" | jq -r '.result.content[0].text // .result')
            print_status "tools/call '$tool_name' succeeded: ${result:0:50}..."
        else
            print_error "tools/call '$tool_name' should have succeeded"
            echo "$response" | jq '.'
            exit 1
        fi
    else
        if echo "$response" | grep -q '"error".*Forbidden'; then
            print_status "tools/call '$tool_name' correctly denied (403 Forbidden)"
        else
            print_error "tools/call '$tool_name' should have been denied"
            echo "$response" | jq '.'
            exit 1
        fi
    fi
}

# Main test execution
main() {
    print_section "Prerequisites Check"
    check_keycloak
    setup_keycloak
    start_mcp_server

    # Test health endpoint
    print_section "Health Check"
    local health=$(curl -s "$MCP_SERVER_URL/health")
    echo "$health" | jq '.'

    # =========================================================================
    # TEST: mcp-admin (has mcp:tools - hierarchical access to ALL tools)
    # =========================================================================
    print_section "Admin User Tests (mcp:tools = ALL tools)"

    admin_token=$(get_token "mcp-admin" "admin123" "openid profile email mcp:read mcp:tools mcp:prompts")

    # Admin should see ALL 4 tools
    test_tools_list "$admin_token" "mcp-admin" "calculate, echo, get_time, system_info"

    # Admin should be able to call ALL tools
    test_tool_call "$admin_token" "echo" '{"message": "Hello", "repeat_count": 2}' "succeed" "mcp-admin"
    test_tool_call "$admin_token" "get_time" '{}' "succeed" "mcp-admin"
    test_tool_call "$admin_token" "calculate" '{"operation": "add", "a": 5, "b": 3}' "succeed" "mcp-admin"
    test_tool_call "$admin_token" "system_info" '{}' "succeed" "mcp-admin"

    # =========================================================================
    # TEST: mcp-user (has mcp:tools:echo, mcp:tools:time, mcp:tools:calc)
    # =========================================================================
    print_section "Regular User Tests (specific tool scopes)"

    user_token=$(get_token "mcp-user" "user123" "openid profile email mcp:read mcp:tools:echo mcp:tools:time mcp:tools:calc")

    # User should see only 3 tools (not system_info)
    test_tools_list "$user_token" "mcp-user" "calculate, echo, get_time"

    # User should be able to call their allowed tools
    test_tool_call "$user_token" "echo" '{"message": "User test", "repeat_count": 1}' "succeed" "mcp-user"
    test_tool_call "$user_token" "get_time" '{}' "succeed" "mcp-user"
    test_tool_call "$user_token" "calculate" '{"operation": "multiply", "a": 4, "b": 7}' "succeed" "mcp-user"

    # User should NOT be able to call system_info (admin only)
    test_tool_call "$user_token" "system_info" '{}' "fail" "mcp-user"

    # =========================================================================
    # TEST: mcp-guest (has only mcp:tools:echo)
    # =========================================================================
    print_section "Guest User Tests (only echo scope)"

    guest_token=$(get_token "mcp-guest" "guest123" "openid profile email mcp:read mcp:tools:echo")

    # Guest should see only 1 tool
    test_tools_list "$guest_token" "mcp-guest" "echo"

    # Guest should be able to call only echo
    test_tool_call "$guest_token" "echo" '{"message": "Guest test", "repeat_count": 3}' "succeed" "mcp-guest"

    # Guest should NOT be able to call other tools
    test_tool_call "$guest_token" "get_time" '{}' "fail" "mcp-guest"
    test_tool_call "$guest_token" "calculate" '{"operation": "add", "a": 1, "b": 1}' "fail" "mcp-guest"
    test_tool_call "$guest_token" "system_info" '{}' "fail" "mcp-guest"

    # =========================================================================
    # TEST: mcp-readonly (has only mcp:read - NO tool access)
    # =========================================================================
    print_section "Readonly User Tests (no tool scopes)"

    readonly_token=$(get_token "mcp-readonly" "readonly123" "openid profile email mcp:read")

    # Readonly should see 0 tools
    test_tools_list "$readonly_token" "mcp-readonly" ""

    # Readonly should NOT be able to call any tools
    test_tool_call "$readonly_token" "echo" '{"message": "test"}' "fail" "mcp-readonly"
    test_tool_call "$readonly_token" "get_time" '{}' "fail" "mcp-readonly"
    test_tool_call "$readonly_token" "calculate" '{"operation": "add", "a": 1, "b": 1}' "fail" "mcp-readonly"
    test_tool_call "$readonly_token" "system_info" '{}' "fail" "mcp-readonly"

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print_section "Test Summary"

    echo ""
    echo -e "${GREEN}All per-tool RBAC tests passed!${NC}"
    echo ""
    echo "Scope hierarchy demonstrated:"
    echo "  - mcp:tools        -> ALL tools (admin)"
    echo "  - mcp:tools:echo   -> echo only"
    echo "  - mcp:tools:time   -> get_time only"
    echo "  - mcp:tools:calc   -> calculate only"
    echo "  - mcp:tools:admin  -> system_info only"
    echo ""
    echo "User access matrix:"
    echo "  | User        | echo | get_time | calculate | system_info |"
    echo "  |-------------|------|----------|-----------|-------------|"
    echo "  | mcp-admin   |  OK  |    OK    |    OK     |     OK      |"
    echo "  | mcp-user    |  OK  |    OK    |    OK     |     X       |"
    echo "  | mcp-guest   |  OK  |    X     |    X      |     X       |"
    echo "  | mcp-readonly|  X   |    X     |    X      |     X       |"
    echo ""
}

main "$@"
