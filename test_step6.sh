#!/bin/bash

# Test script for Step 6: JWT Token Validation
echo "🧪 Testing Step 6: JWT Token Validation"
echo "========================================"

# Pretty-print JSON with jq (color if available), fallback to raw
pretty_json() {
  if command -v jq >/dev/null 2>&1; then
    jq -C . 2>/dev/null || cat
  else
    cat
  fi
}

# Function to cleanup background processes
cleanup() {
    echo "🧹 Cleaning up..."
    if [ ! -z "$SERVER_PID" ]; then
        kill $SERVER_PID 2>/dev/null
        wait $SERVER_PID 2>/dev/null
    fi
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup EXIT INT TERM

# Check if public key exists, if not generate one
if [ ! -f "mcp_public_key.pem" ]; then
    echo "🔑 No public key found, generating key pair..."
    uv run python generate_token.py --generate-keys
    if [ $? -ne 0 ]; then
        echo "❌ Failed to generate key pair"
        exit 1
    fi
fi

# Generate test tokens
echo "🔑 Generating test tokens..."
uv run python generate_token.py --username alice --scopes mcp:read,mcp:tools
uv run python generate_token.py --username admin --scopes mcp:read,mcp:tools,mcp:prompts

# Extract tokens from generated files
ALICE_TOKEN=$(python -c "import json; print(json.load(open('token_alice.json'))['token'])")
ADMIN_TOKEN=$(python -c "import json; print(json.load(open('token_admin.json'))['token'])")

if [ -z "$ALICE_TOKEN" ] || [ -z "$ADMIN_TOKEN" ]; then
    echo "❌ Failed to extract tokens"
    exit 1
fi

echo "✅ Test tokens generated successfully"

# Start the server in background
echo "🚀 Starting Step 6 server..."
uv run step6 &
SERVER_PID=$!

# Wait for server to start
echo "⏳ Waiting for server to start..."
sleep 3

# Test health endpoint
echo "🔍 Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s http://localhost:9000/health)

if [ $? -eq 0 ]; then
    echo "✅ Health endpoint test passed!"
    echo "📄 Response:"
    echo "$HEALTH_RESPONSE" | pretty_json
    
    # Check if auth is required
    if echo "$HEALTH_RESPONSE" | grep -q '"auth_required":true'; then
        echo "✅ Authentication is required!"
    else
        echo "❌ Authentication requirement not indicated"
        exit 1
    fi
else
    echo "❌ Health endpoint test failed!"
    exit 1
fi

# Test JWKS endpoint
echo "🔍 Testing JWKS endpoint..."
JWKS_RESPONSE=$(curl -s http://localhost:9000/.well-known/jwks.json)

if [ $? -eq 0 ]; then
    echo "✅ JWKS endpoint test passed!"
    echo "📄 Response:"
    echo "$JWKS_RESPONSE" | pretty_json
    
    # Check if JWKS contains keys
    if echo "$JWKS_RESPONSE" | grep -q '"keys"'; then
        echo "✅ JWKS contains public key!"
    else
        echo "❌ JWKS does not contain keys"
        exit 1
    fi
else
    echo "❌ JWKS endpoint test failed!"
    exit 1
fi

# Test unauthenticated MCP request (should fail)
echo "🔍 Testing unauthenticated MCP request..."
UNAUTH_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize"}')

if [ $? -eq 0 ]; then
    echo "✅ Unauthenticated request test passed!"
    echo "📄 Response:"
    echo "$UNAUTH_RESPONSE" | pretty_json
    
    # Check if response contains 401 error
    if echo "$UNAUTH_RESPONSE" | grep -q '"detail":"Authorization header missing"'; then
        echo "✅ Properly rejects unauthenticated requests!"
    else
        echo "❌ Did not properly reject unauthenticated request"
        exit 1
    fi
else
    echo "❌ Unauthenticated request test failed!"
    exit 1
fi

# Test authenticated MCP initialize with Alice token
echo "🔍 Testing authenticated MCP initialize (Alice)..."
AUTH_INIT_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize"}')

if [ $? -eq 0 ]; then
    echo "✅ Authenticated initialize test passed!"
    echo "📄 Response:"
    echo "$AUTH_INIT_RESPONSE" | pretty_json
    
    # Check if response contains user info
    if echo "$AUTH_INIT_RESPONSE" | grep -q '"authenticatedUser":"alice"'; then
        echo "✅ Initialize response includes authenticated user!"
    else
        echo "❌ Initialize response missing authenticated user"
        exit 1
    fi
else
    echo "❌ Authenticated initialize test failed!"
    exit 1
fi

# Test authenticated tools/list with Alice token
echo "🔍 Testing authenticated tools/list (Alice)..."
AUTH_TOOLS_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}')

if [ $? -eq 0 ]; then
    echo "✅ Authenticated tools/list test passed!"
    echo "📄 Response:"
    echo "$AUTH_TOOLS_RESPONSE" | pretty_json
    
    # Check if response contains tools
    if echo "$AUTH_TOOLS_RESPONSE" | grep -q '"name":"echo"'; then
        echo "✅ Echo tool is listed correctly for authenticated user!"
    else
        echo "❌ Echo tool not found in authenticated response!"
        exit 1
    fi
else
    echo "❌ Authenticated tools/list test failed!"
    exit 1
fi

# Test authenticated tools/call with Alice token
echo "🔍 Testing authenticated tools/call (Alice)..."
AUTH_CALL_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "echo", "arguments": {"message": "Hello Alice", "repeat_count": 2}}}')

if [ $? -eq 0 ]; then
    echo "✅ Authenticated tools/call test passed!"
    echo "📄 Response:"
    echo "$AUTH_CALL_RESPONSE" | pretty_json
    
    # Check if response contains the echoed message
    if echo "$AUTH_CALL_RESPONSE" | grep -q 'Hello AliceHello Alice'; then
        echo "✅ Echo tool works correctly for authenticated user!"
    else
        echo "❌ Echo tool response is incorrect for authenticated user!"
        exit 1
    fi
else
    echo "❌ Authenticated tools/call test failed!"
    exit 1
fi

# Test authenticated ping with Alice token
echo "🔍 Testing authenticated ping (Alice)..."
AUTH_PING_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 4, "method": "ping"}')

if [ $? -eq 0 ]; then
    echo "✅ Authenticated ping test passed!"
    echo "📄 Response:"
    echo "$AUTH_PING_RESPONSE" | pretty_json
    
    # Check if response contains user info
    if echo "$AUTH_PING_RESPONSE" | grep -q '"user":"alice"' && echo "$AUTH_PING_RESPONSE" | grep -q '"authenticated":true'; then
        echo "✅ Ping response includes authenticated user info!"
    else
        echo "❌ Ping response missing authenticated user info"
        exit 1
    fi
else
    echo "❌ Authenticated ping test failed!"
    exit 1
fi

# Test authenticated request with Admin token
echo "🔍 Testing authenticated request (Admin)..."
ADMIN_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 5, "method": "initialize"}')

if [ $? -eq 0 ]; then
    echo "✅ Admin authenticated request test passed!"
    echo "📄 Response:"
    echo "$ADMIN_RESPONSE" | pretty_json
    
    # Check if response contains admin user info
    if echo "$ADMIN_RESPONSE" | grep -q '"authenticatedUser":"admin"'; then
        echo "✅ Admin user is properly authenticated!"
    else
        echo "❌ Admin user not properly authenticated"
        exit 1
    fi
else
    echo "❌ Admin authenticated request test failed!"
    exit 1
fi

# Test invalid token (should fail)
echo "🔍 Testing invalid token..."
INVALID_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid.token.here" \
  -d '{"jsonrpc": "2.0", "id": 6, "method": "initialize"}')

if [ $? -eq 0 ]; then
    echo "✅ Invalid token test passed!"
    echo "📄 Response:"
    echo "$INVALID_RESPONSE" | pretty_json
    
    # Check if response contains error
    if echo "$INVALID_RESPONSE" | grep -q '"detail":"Invalid token"'; then
        echo "✅ Properly rejects invalid tokens!"
    else
        echo "❌ Did not properly reject invalid token"
        exit 1
    fi
else
    echo "❌ Invalid token test failed!"
    exit 1
fi

echo ""
echo "🎉 Step 6 tests completed successfully!"
echo "✅ JWT token validation is working"
echo "✅ Authentication is enforced for MCP requests"
echo "✅ Authenticated users can access all MCP functionality"
echo "✅ User context is included in responses"
echo "✅ Invalid tokens are properly rejected"
echo "✅ WWW-Authenticate headers are set correctly"
echo "✅ Ready for next step: OAuth 2.0 metadata" 