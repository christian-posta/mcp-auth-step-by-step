#!/bin/bash

# Step 10: Keycloak Integration Test Script
# This script tests the MCP server with Keycloak integration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
KEYCLOAK_URL="http://localhost:8080"
KEYCLOAK_REALM="mcp-realm"
MCP_SERVER_URL="http://localhost:9000"
CLIENT_ID="mcp-test-client"
CLIENT_SECRET="mcp-secret-key-change-me"

# Global variables
MCP_SERVER_PID=""
INSPECT_MODE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --inspect)
            INSPECT_MODE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --inspect    Pause after each test scenario to examine results"
            echo "  -h, --help   Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Run all tests without pausing"
            echo "  $0 --inspect          # Run tests with pauses for inspection"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}=== Step 10: Keycloak Integration Test ===${NC}"
if [ "$INSPECT_MODE" = true ]; then
    echo -e "${YELLOW}Inspection mode enabled - will pause after each test scenario${NC}"
fi

# Helper functions
print_info() {
    echo -e "\033[1;34mℹ️ \033[0m $1" >&2
}

print_status() {
    echo -e "\033[1;32m✅\033[0m $1" >&2
}

print_error() {
    echo -e "\033[1;31m❌\033[0m $1" >&2
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

decode_jwt() {
    local token=$1
    print_info "Decoding JWT token..." >&2
    print_info "Token length: ${#token}" >&2
    print_info "Token starts with: ${token:0:20}..." >&2
    
    # Split the token into parts
    IFS='.' read -r header_b64 payload_b64 signature_b64 <<< "$token"
    
    print_info "Header base64: $header_b64" >&2
    print_info "Payload base64: $payload_b64" >&2
    
    # Add padding to base64 if needed (JWT uses URL-safe base64 without padding)
    header_b64_padded=$(printf '%s' "$header_b64" | sed 's/-/+/g; s/_/\//g')
    payload_b64_padded=$(printf '%s' "$payload_b64" | sed 's/-/+/g; s/_/\//g')
    
    # Add padding
    while [ $((${#header_b64_padded} % 4)) -ne 0 ]; do
        header_b64_padded="${header_b64_padded}="
    done
    while [ $((${#payload_b64_padded} % 4)) -ne 0 ]; do
        payload_b64_padded="${payload_b64_padded}="
    done
    
    print_info "Header base64 (padded): $header_b64_padded" >&2
    print_info "Payload base64 (padded): $payload_b64_padded" >&2
    
    # Decode header
    local header=$(echo "$header_b64_padded" | base64 -d 2>/dev/null | jq '.' 2>/dev/null)
    print_info "Header: $header" >&2
    
    # Decode payload
    local payload=$(echo "$payload_b64_padded" | base64 -d 2>/dev/null | jq '.' 2>/dev/null)
    print_info "Payload: $payload" >&2
    
    # Check key fields
    local issuer=$(echo "$payload" | jq -r '.iss // empty')
    local audience=$(echo "$payload" | jq -r '.aud // empty')
    local subject=$(echo "$payload" | jq -r '.sub // empty')
    local username=$(echo "$payload" | jq -r '.preferred_username // empty')
    local scope=$(echo "$payload" | jq -r '.scope // empty')
    local azp=$(echo "$payload" | jq -r '.azp // empty')
    print_info "Key fields:" >&2
    print_info "  Issuer: $issuer" >&2
    print_info "  Audience: $audience" >&2
    print_info "  Subject: $subject" >&2
    print_info "  Username: $username" >&2
    print_info "  Scope: $scope" >&2
    print_info "  AZP: $azp" >&2
}

# Helper function to extract 'scope' claim from JWT
extract_scope_claim() {
    local token=$1
    IFS='.' read -r _ payload_b64 _ <<< "$token"
    payload_b64_padded=$(printf '%s' "$payload_b64" | sed 's/-/+/g; s/_/\//g')
    while [ $((${#payload_b64_padded} % 4)) -ne 0 ]; do
        payload_b64_padded="${payload_b64_padded}="
    done
    local scope=$(echo "$payload_b64_padded" | base64 -d 2>/dev/null | jq -r '.scope // empty' 2>/dev/null)
    echo "$scope"
}

# Assertion function for scopes
assert_scopes() {
    local token="$1"
    local expected_scopes="$2"
    local user="$3"
    local actual_scopes=$(extract_scope_claim "$token")
    print_info "User: $user"
    print_info "Expected scopes: $expected_scopes"
    print_info "Actual scopes:   $actual_scopes"
    if [[ "$actual_scopes" != "$expected_scopes" ]]; then
        print_error "Scope assertion failed for $user: expected '$expected_scopes', got '$actual_scopes'"
        exit 1
    else
        print_status "Scope assertion passed for $user: $actual_scopes"
    fi
}

# Assertion function for mcp: scopes only
assert_mcp_scopes() {
    local token="$1"
    local expected_mcp_scopes="$2" # e.g. "mcp:read mcp:tools"
    local user="$3"
    local actual_scopes=$(extract_scope_claim "$token")
    local actual_mcp_scopes=$(for s in $actual_scopes; do [[ $s == mcp:* ]] && echo $s; done | sort | xargs)
    local expected_sorted=$(for s in $expected_mcp_scopes; do echo $s; done | sort | xargs)
    print_info "User: $user"
    print_info "Expected mcp: scopes: $expected_sorted"
    print_info "Actual mcp: scopes:   $actual_mcp_scopes"
    if [[ "$actual_mcp_scopes" != "$expected_sorted" ]]; then
        print_error "MCP scope assertion failed for $user: expected '$expected_sorted', got '$actual_mcp_scopes'"
        exit 1
    else
        print_status "MCP scope assertion passed for $user: $actual_mcp_scopes"
    fi
}

# Cleanup function to stop MCP server
cleanup() {
    if [ ! -z "$MCP_SERVER_PID" ]; then
        print_info "Stopping MCP server (PID: $MCP_SERVER_PID)..."
        kill $MCP_SERVER_PID 2>/dev/null || true
        wait $MCP_SERVER_PID 2>/dev/null || true
        print_status "MCP server stopped"
    fi
}

# Set up trap to cleanup on script exit
trap cleanup EXIT

# Check if Keycloak is running
check_keycloak() {
    print_info "Checking if Keycloak is running..."
    if curl -s "$KEYCLOAK_URL/realms/master" > /dev/null 2>&1; then
        print_status "Keycloak is running"
    else
        print_error "Keycloak is not running. Please start Keycloak first:"
        echo "  cd keycloak && docker-compose up -d"
        exit 1
    fi
}

# Setup Keycloak with MCP configuration
setup_keycloak() {
    print_info "Setting up Keycloak with MCP configuration..."
    
    if [ ! -f "keycloak/config.json" ]; then
        print_error "MCP Keycloak configuration file not found: keycloak/config.json"
        exit 1
    fi
    
    cd keycloak
    uv run python setup_keycloak.py --config config.json --url "$KEYCLOAK_URL" --summary
    cd ..
    
    print_status "Keycloak setup completed"
}

# Start MCP server
start_mcp_server() {
    print_info "Starting MCP server..."
    
    # Check if the step10.py file exists
    if [ ! -f "src/mcp_http/step10.py" ]; then
        print_error "MCP server file not found: src/mcp_http/step10.py"
        exit 1
    fi
    
    # Start the MCP server in the background
    uv run python src/mcp_http/step10.py &
    MCP_SERVER_PID=$!
    
    print_info "MCP server started with PID: $MCP_SERVER_PID"
    
    # Wait for server to start
    print_info "Waiting for MCP server to start..."
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$MCP_SERVER_URL/health" > /dev/null 2>&1; then
            print_status "MCP server is ready"
            return 0
        fi
        
        print_info "Waiting for MCP server... (attempt $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_error "MCP server failed to start within expected time"
    exit 1
}

# Get access token from Keycloak
get_token() {
    local username=$1
    local password=$2
    local scopes=$3
    
    print_info "Getting token for user: $username with scopes: $scopes" >&2
    
    local token_response=$(curl -s -X POST \
        "$KEYCLOAK_URL/realms/$KEYCLOAK_REALM/protocol/openid-connect/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "grant_type=password" \
        -d "client_id=$CLIENT_ID" \
        -d "username=$username" \
        -d "password=$password" \
        -d "scope=$scopes")
    
    # Debug: Check the token response
    print_info "Token response from Keycloak:" >&2
    echo "$token_response" | jq '.' >&2 2>/dev/null || echo "Raw response: $token_response" >&2
    
    if echo "$token_response" | grep -q "access_token"; then
        # Extract just the access_token, ensuring it's clean
        local access_token=$(echo "$token_response" | jq -r '.access_token // empty')
        
        # Debug: Check the extracted token
        print_info "Extracted token details:" >&2
        print_info "Token length: ${#access_token}" >&2
        print_info "Token starts with: ${access_token:0:20}..." >&2
        print_info "Token ends with: ...${access_token: -20}" >&2
        
        # Check for common issues
        if [[ "$access_token" == "null" ]] || [[ "$access_token" == "empty" ]]; then
            print_error "Token is null or empty" >&2
            return 1
        fi
        
        if [[ -z "$access_token" ]]; then
            print_error "Token is empty" >&2
            return 1
        fi
        
        # Verify it looks like a JWT token (should start with eyJ)
        if [[ ! "$access_token" =~ ^eyJ ]]; then
            print_error "Token doesn't look like a valid JWT (should start with 'eyJ')" >&2
            print_error "Token starts with: ${access_token:0:10}" >&2
            return 1
        fi
        
        print_status "Token obtained successfully" >&2
        
        # Output only the token to stdout, nothing else
        echo -n "$access_token"
    else
        print_error "Failed to get token:" >&2
        echo "$token_response" | jq '.' >&2 2>/dev/null || echo "Raw response: $token_response" >&2
        return 1
    fi
}

# Test MCP server health
test_mcp_health() {
    print_info "Testing MCP server health..."
    
    local health_response=$(curl -s "$MCP_SERVER_URL/health")
    
    if echo "$health_response" | grep -q "keycloak_integration.*true"; then
        print_status "MCP server health check passed"
        echo "$health_response" | jq '.'
    else
        print_error "MCP server health check failed:"
        echo "$health_response" | jq '.'
        exit 1
    fi
}

# Test MCP server without token (should fail)
test_unauthorized() {
    print_info "Testing MCP server without token (should fail)..."
    
    local response=$(curl -s -w "%{http_code}" \
        -X POST "$MCP_SERVER_URL/mcp" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc": "2.0", "id": 1, "method": "ping"}')
    
    local http_code="${response: -3}"
    local body="${response%???}"
    
    if [ "$http_code" = "401" ]; then
        print_status "Unauthorized request correctly rejected"
    else
        print_error "Expected 401, got $http_code"
        echo "$body" | jq '.'
        exit 1
    fi
}

# Test MCP server with token
test_authorized() {
    local token=$1
    local method=$2
    local params=$3
    
    print_info "Testing MCP server with token for method: $method"
    
    # Build the JSON request
    local json_request="{\"jsonrpc\": \"2.0\", \"id\": 1, \"method\": \"$method\""
    
    # Add params if provided
    if [ ! -z "$params" ]; then
        json_request="$json_request, \"params\": $params"
    fi
    
    json_request="$json_request}"
    
    # Debug: print the JSON being sent
    print_info "Sending JSON: $json_request"
    
    # Debug: Check token before sending
    print_info "Token being used:"
    print_info "Token length: ${#token}"
    print_info "Token starts with: ${token:0:20}..."
    print_info "Token ends with: ...${token: -20}"
    
    # Use a temporary file for the JSON to avoid shell escaping issues
    local temp_json=$(mktemp)
    echo "$json_request" > "$temp_json"
    
    # Debug: Show the curl command being executed
    print_info "Executing curl command:"
    print_info "curl -s -X POST $MCP_SERVER_URL/mcp -H 'Content-Type: application/json' -H 'Authorization: Bearer ${token:0:20}...' -d @$temp_json"
    
    local response=$(curl -s \
        -X POST "$MCP_SERVER_URL/mcp" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $token" \
        -d "@$temp_json")
    
    # Clean up temp file
    rm -f "$temp_json"
    
    # Debug: print raw response
    print_info "Raw response: $response"
    
    if echo "$response" | grep -q "result"; then
        print_status "Authorized request successful for $method"
        echo "$response" | jq '.result'
        
        # Check if scopes are included in response
        if echo "$response" | grep -q "userScopes"; then
            local response_scopes=$(echo "$response" | jq -r '.result.userScopes[]? // empty')
            print_info "User scopes in response: $response_scopes"
        fi
    else
        print_error "Authorized request failed for $method:"
        echo "$response" | jq '.' 2>/dev/null || echo "Raw response: $response"
        exit 1
    fi
}

# Test scope-based authorization
test_scope_authorization() {
    local token=$1
    local method=$2
    local should_succeed=$3
    local params=$4
    
    print_info "Testing scope authorization for $method (should $should_succeed)..."
    
    # Build the JSON request
    local json_request="{\"jsonrpc\": \"2.0\", \"id\": 1, \"method\": \"$method\""
    
    # Add params if provided
    if [ ! -z "$params" ]; then
        json_request="$json_request, \"params\": $params"
    fi
    
    json_request="$json_request}"
    
    # Use a temporary file for the JSON to avoid shell escaping issues
    local temp_json=$(mktemp)
    echo "$json_request" > "$temp_json"
    
    local response=$(curl -s \
        -X POST "$MCP_SERVER_URL/mcp" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $token" \
        -d "@$temp_json")
    
    # Clean up temp file
    rm -f "$temp_json"
    
    if [ "$should_succeed" = "succeed" ]; then
        if echo "$response" | grep -q "result"; then
            print_status "Scope authorization test passed for $method"
        else
            print_error "Scope authorization test failed for $method (expected success):"
            echo "$response" | jq '.' 2>/dev/null || echo "Raw response: $response"
            exit 1
        fi
    else
        if echo "$response" | grep -q "error.*Forbidden"; then
            print_status "Scope authorization test passed for $method (correctly denied)"
        else
            print_error "Scope authorization test failed for $method (expected failure):"
            echo "$response" | jq '.' 2>/dev/null || echo "Raw response: $response"
            exit 1
        fi
    fi
}

# Test azp claim verification
test_azp_verification() {
    local token=$1
    local expected_azp=$2
    
    print_info "Testing AZP claim verification (expected: $expected_azp)..."
    
    # Decode token to get azp claim
    IFS='.' read -r header_b64 payload_b64 signature_b64 <<< "$token"
    payload_b64_padded=$(printf '%s' "$payload_b64" | sed 's/-/+/g; s/_/\//g')
    while [ $((${#payload_b64_padded} % 4)) -ne 0 ]; do
        payload_b64_padded="${payload_b64_padded}="
    done
    local actual_azp=$(echo "$payload_b64_padded" | base64 -d 2>/dev/null | jq -r '.azp // empty' 2>/dev/null)
    
    if [ "$actual_azp" = "$expected_azp" ]; then
        print_status "AZP claim verification passed: $actual_azp"
    else
        print_error "AZP claim verification failed. Expected: $expected_azp, Got: $actual_azp"
        exit 1
    fi
}

# Pause function for inspection mode
pause_for_inspection() {
    local scenario_name="$1"
    
    if [ "$INSPECT_MODE" = true ]; then
        echo ""
        echo -e "${BLUE}=== Test scenario completed: $scenario_name ===${NC}"
        echo -e "${YELLOW}Press Enter to continue to the next test scenario, or type 'n' to exit:${NC}"
        read -r response
        if [[ "$response" =~ ^[Nn]$ ]]; then
            echo -e "${YELLOW}Exiting tests as requested...${NC}"
            exit 0
        fi
        echo ""
    fi
}

# Main test execution
main() {
    print_info "Starting Step 10 Keycloak integration test..."
    
    # Check prerequisites
    check_keycloak
    pause_for_inspection "Keycloak health check"
        
    # Start MCP server
    start_mcp_server
    pause_for_inspection "MCP server startup"
    
    # Test MCP server health
    test_mcp_health
    pause_for_inspection "MCP server health check"
    
    # Test unauthorized access
    test_unauthorized
    pause_for_inspection "Unauthorized access test"
    
    # Test with admin user (full access)
    print_info "=== Testing with admin user (full access) ==="
    
    # Get admin token with debug
    print_info "About to call get_token..." >&2
    admin_token=$(get_token "mcp-admin" "admin123" "openid profile email mcp:read mcp:tools mcp:prompts")
    token_exit_code=$?
    print_info "get_token exit code: $token_exit_code" >&2
    print_info "Captured token length: ${#admin_token}" >&2
    print_info "Captured token starts with: ${admin_token:0:50}..." >&2
    print_info "Captured token ends with: ...${admin_token: -50}" >&2
    
    if [ $token_exit_code -ne 0 ]; then
        print_error "Failed to get admin token"
        exit 1
    fi
    
    decode_jwt "$admin_token"
    assert_mcp_scopes "$admin_token" "mcp:read mcp:tools mcp:prompts" "mcp-admin"
    
    # Test azp verification for admin token
    test_azp_verification "$admin_token" "mcp-test-client"
    
    test_authorized "$admin_token" "ping"
    test_authorized "$admin_token" "tools/list"
    test_authorized "$admin_token" "tools/call" '{"name": "echo", "arguments": {"message": "Hello from admin", "repeat_count": 2}}'
    test_authorized "$admin_token" "prompts/list"
    test_authorized "$admin_token" "prompts/get" '{"name": "echo_prompt", "arguments": {"message": "Admin test"}}'
    
    pause_for_inspection "Admin user tests (full access)"
    
    # Test with regular user (limited access)
    print_info "=== Testing with regular user (limited access) ==="
    
    # Get user token
    user_token=$(get_token "mcp-user" "user123" "openid profile email mcp:read mcp:tools mcp:prompts")
    if [ $? -ne 0 ]; then
        print_error "Failed to get user token"
        exit 1
    fi
    
    decode_jwt "$user_token"
    assert_mcp_scopes "$user_token" "mcp:read mcp:tools" "mcp-user"
    
    # Test azp verification for user token
    test_azp_verification "$user_token" "mcp-test-client"
    
    test_authorized "$user_token" "ping"
    test_authorized "$user_token" "tools/list"
    test_authorized "$user_token" "tools/call" '{"name": "echo", "arguments": {"message": "Hello from user", "repeat_count": 1}}'
    test_scope_authorization "$user_token" "prompts/list" "fail"
    test_scope_authorization "$user_token" "prompts/get" "fail"
    
    pause_for_inspection "Regular user tests (limited access)"
    
    # Test with readonly user (minimal access)
    print_info "=== Testing with readonly user (minimal access) ==="
    
    # Get readonly token
    readonly_token=$(get_token "mcp-readonly" "readonly123" "openid profile email mcp:read mcp:tools mcp:prompts")
    if [ $? -ne 0 ]; then
        print_error "Failed to get readonly token"
        exit 1
    fi
    
    decode_jwt "$readonly_token"
    assert_mcp_scopes "$readonly_token" "mcp:read" "mcp-readonly"
    
    # Test azp verification for readonly token
    test_azp_verification "$readonly_token" "mcp-test-client"
    
    test_authorized "$readonly_token" "ping"
    test_scope_authorization "$readonly_token" "tools/list" "fail"
    test_scope_authorization "$readonly_token" "tools/call" "fail"
    test_scope_authorization "$readonly_token" "prompts/list" "fail"
    test_scope_authorization "$readonly_token" "prompts/get" "fail"
    
    pause_for_inspection "Readonly user tests (minimal access)"
    
    # Test OAuth metadata endpoints
    print_info "=== Testing OAuth metadata endpoints ==="
    
    # Test MCP server's protected resource metadata (RFC9728)
    local protected_resource=$(curl -s "$MCP_SERVER_URL/.well-known/oauth-protected-resource")
    if echo "$protected_resource" | grep -q "authorization_servers"; then
        print_status "OAuth protected resource metadata endpoint working"
        echo "$protected_resource" | jq '.'
    else
        print_error "OAuth protected resource metadata endpoint failed"
        echo "$protected_resource" | jq '.'
    fi
    
    # Test Keycloak's authorization server metadata (RFC8414)
    local auth_server_base=$(echo "$protected_resource" | jq -r '.authorization_servers[0] // empty')
    if [ ! -z "$auth_server_base" ]; then
        local oauth_metadata_url="${auth_server_base}/.well-known/oauth-authorization-server"
        print_info "Testing Keycloak OAuth 2.0 Authorization Server Metadata at: $oauth_metadata_url"
        local oauth_metadata=$(curl -s "$oauth_metadata_url")
        if echo "$oauth_metadata" | grep -q '"issuer"'; then
            print_status "Keycloak OAuth 2.0 Authorization Server metadata endpoint working"
            echo "$oauth_metadata" | jq '.'
        else
            print_error "Keycloak OAuth 2.0 Authorization Server metadata endpoint failed"
            echo "$oauth_metadata" | jq '.'
        fi
    else
        print_error "No authorization server URL found in protected resource metadata"
    fi
    
    pause_for_inspection "OAuth metadata endpoints tests"
    
    print_status "=== Step 10 Keycloak integration test completed successfully! ==="
    print_info "Keycloak URL: $KEYCLOAK_URL"
    print_info "Keycloak Realm: $KEYCLOAK_REALM"
    print_info "MCP Server URL: $MCP_SERVER_URL"
    print_info "Test users: mcp-admin, mcp-user, mcp-readonly"
}

# Run main function
main "$@" 