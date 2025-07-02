#!/bin/bash

# Step 9: Keycloak Setup Verification and Token Testing
# This script verifies Keycloak setup and tests token acquisition

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
CLIENT_ID="mcp-test-client"
CLIENT_SECRET="mcp-secret-key-change-me"

# Global variables
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

echo -e "${BLUE}=== Step 9: Keycloak Setup Verification and Token Testing ===${NC}"
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
    print_info "Key fields:" >&2
    print_info "  Issuer: $issuer" >&2
    print_info "  Audience: $audience" >&2
    print_info "  Subject: $subject" >&2
    print_info "  Username: $username" >&2
    print_info "  Scope: $scope" >&2
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

# Check if Keycloak is running
check_keycloak() {
    print_info "Checking if Keycloak is running..."
    if curl -s "$KEYCLOAK_URL/realms/master" > /dev/null 2>&1; then
        print_status "Keycloak is running"
    else
        print_error "Keycloak is not running. Please run step9.py first:"
        echo "  uv run python src/mcp_http/step9.py"
        exit 1
    fi
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

# Test realm configuration
test_realm_config() {
    print_info "Testing realm configuration..."
    
    local realm_info=$(curl -s "$KEYCLOAK_URL/realms/$KEYCLOAK_REALM")
    
    if echo "$realm_info" | grep -q "mcp-realm"; then
        print_status "Realm configuration verified"
        echo "$realm_info" | jq '.'
    else
        print_error "Realm configuration verification failed"
        echo "$realm_info" | jq '.'
        exit 1
    fi
}

# Test OAuth authorization server metadata
test_oauth_metadata() {
    print_info "Testing OAuth authorization server metadata..."
    
    local auth_server_metadata=$(curl -s "$KEYCLOAK_URL/realms/$KEYCLOAK_REALM/.well-known/oauth-authorization-server")
    
    if echo "$auth_server_metadata" | grep -q "issuer"; then
        print_status "OAuth authorization server metadata verified"
        echo "$auth_server_metadata" | jq '.'
    else
        print_error "OAuth authorization server metadata verification failed"
        echo "$auth_server_metadata" | jq '.'
        exit 1
    fi
}

# Test JWKS endpoint
test_jwks() {
    print_info "Testing JWKS endpoint..."
    
    local jwks=$(curl -s "$KEYCLOAK_URL/realms/$KEYCLOAK_REALM/protocol/openid-connect/certs")
    
    if echo "$jwks" | grep -q "keys"; then
        print_status "JWKS endpoint verified"
        echo "$jwks" | jq '.'
    else
        print_error "JWKS endpoint verification failed"
        echo "$jwks" | jq '.'
        exit 1
    fi
}

# Test token acquisition and validation
test_token_acquisition() {
    local username=$1
    local password=$2
    local scopes=$3
    local expected_audience=$4
    
    print_info "=== Testing token acquisition for user: $username ==="
    
    # Get token
    local token=$(get_token "$username" "$password" "$scopes")
    if [ $? -ne 0 ]; then
        print_error "Failed to get token for $username"
        exit 1
    fi
    
    # Decode and validate token
    decode_jwt "$token"
    
    # Verify audience using the same approach as decode_jwt
    IFS='.' read -r header_b64 payload_b64 signature_b64 <<< "$token"
    payload_b64_padded=$(printf '%s' "$payload_b64" | sed 's/-/+/g; s/_/\//g')
    while [ $((${#payload_b64_padded} % 4)) -ne 0 ]; do
        payload_b64_padded="${payload_b64_padded}="
    done
    local actual_audience=$(echo "$payload_b64_padded" | base64 -d 2>/dev/null | jq -r '.aud // empty' 2>/dev/null)
    
    if [ "$actual_audience" = "$expected_audience" ]; then
        print_status "Token audience verification passed: $actual_audience"
    else
        print_error "Token audience verification failed. Expected: $expected_audience, Got: $actual_audience"
        exit 1
    fi
    
    # Verify scopes using the same approach
    local actual_scopes=$(echo "$payload_b64_padded" | base64 -d 2>/dev/null | jq -r '.scope // empty' 2>/dev/null)
    print_info "Token scopes: $actual_scopes"
    
    print_status "Token acquisition and validation passed for $username"
}

# Main test execution
main() {
    print_info "Starting Step 9 Keycloak verification and token testing..."
    
    # Check prerequisites
    check_keycloak
    pause_for_inspection "Keycloak health check"
    
    # Test realm configuration
    test_realm_config
    pause_for_inspection "Realm configuration test"
    
    # Test OAuth metadata
    test_oauth_metadata
    pause_for_inspection "OAuth metadata test"
    
    # Test JWKS endpoint
    test_jwks
    pause_for_inspection "JWKS endpoint test"
    
    # Test token acquisition for admin user
    test_token_acquisition "mcp-admin" "admin123" "openid profile email mcp:read mcp:tools mcp:prompts" "echo-mcp-server"
    pause_for_inspection "Admin user token test"
    
    # Test token acquisition for regular user
    test_token_acquisition "mcp-user" "user123" "openid profile email mcp:read mcp:tools" "echo-mcp-server"
    pause_for_inspection "Regular user token test"
    
    # Test token acquisition for readonly user
    test_token_acquisition "mcp-readonly" "readonly123" "openid profile email mcp:read" "echo-mcp-server"
    pause_for_inspection "Readonly user token test"
    
    print_status "=== Step 9 Keycloak verification and token testing completed successfully! ==="
    print_info "Keycloak URL: $KEYCLOAK_URL"
    print_info "Keycloak Realm: $KEYCLOAK_REALM"
    print_info "Client ID: $CLIENT_ID"
    print_info "Test users: mcp-admin, mcp-user, mcp-readonly"
    print_info "All tokens have correct audience: echo-mcp-server"
    print_info "Ready for Step 10: MCP Server with Keycloak Integration"
}

# Run main function
main "$@" 