#!/bin/bash

# Test script for Step 7: OAuth 2.0 Metadata
echo "🧪 Testing Step 7: OAuth 2.0 Metadata"
echo "====================================="

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

# Generate test token
echo "🔑 Generating test token..."
uv run python generate_token.py --username alice --scopes mcp:read,mcp:tools

# Extract token from generated file
ALICE_TOKEN=$(python -c "import json; print(json.load(open('token_alice.json'))['token'])")

if [ -z "$ALICE_TOKEN" ]; then
    echo "❌ Failed to extract token"
    exit 1
fi

echo "✅ Test token generated successfully"

# Start the server in background
echo "🚀 Starting Step 7 server..."
uv run step7 &
SERVER_PID=$!

# Wait for server to start
echo "⏳ Waiting for server to start..."
sleep 3

# Test health endpoint
echo "🔍 Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s http://localhost:9000/health)

if [ $? -eq 0 ]; then
    echo "✅ Health endpoint test passed!"
    echo "📄 Response: $HEALTH_RESPONSE"
    
    # Check if OAuth metadata is included
    if echo "$HEALTH_RESPONSE" | grep -q '"oauth_metadata"'; then
        echo "✅ Health response includes OAuth metadata!"
    else
        echo "❌ Health response missing OAuth metadata"
        exit 1
    fi
else
    echo "❌ Health endpoint test failed!"
    exit 1
fi

# Test OAuth Protected Resource metadata
echo "🔍 Testing OAuth Protected Resource metadata..."
PROTECTED_RESOURCE_RESPONSE=$(curl -s http://localhost:9000/.well-known/oauth-protected-resource)

if [ $? -eq 0 ]; then
    echo "✅ OAuth Protected Resource metadata test passed!"
    echo "📄 Response: $PROTECTED_RESOURCE_RESPONSE"
    
    # Check if response contains required fields
    if echo "$PROTECTED_RESOURCE_RESPONSE" | grep -q '"resource"' && \
       echo "$PROTECTED_RESOURCE_RESPONSE" | grep -q '"authorization_servers"' && \
       echo "$PROTECTED_RESOURCE_RESPONSE" | grep -q '"scopes_supported"' && \
       echo "$PROTECTED_RESOURCE_RESPONSE" | grep -q '"bearer_methods_supported"'; then
        echo "✅ Protected Resource metadata contains all required fields!"
    else
        echo "❌ Protected Resource metadata missing required fields"
        exit 1
    fi
    
    # Check if MCP-specific fields are present
    if echo "$PROTECTED_RESOURCE_RESPONSE" | grep -q '"mcp_protocol_version"' && \
       echo "$PROTECTED_RESOURCE_RESPONSE" | grep -q '"resource_type"'; then
        echo "✅ Protected Resource metadata includes MCP-specific fields!"
    else
        echo "❌ Protected Resource metadata missing MCP-specific fields"
        exit 1
    fi
else
    echo "❌ OAuth Protected Resource metadata test failed!"
    exit 1
fi

# Test OAuth Authorization Server metadata
echo "🔍 Testing OAuth Authorization Server metadata..."
AUTH_SERVER_RESPONSE=$(curl -s http://localhost:9000/.well-known/oauth-authorization-server)

if [ $? -eq 0 ]; then
    echo "✅ OAuth Authorization Server metadata test passed!"
    echo "📄 Response: $AUTH_SERVER_RESPONSE"
    
    # Check if response contains required fields
    if echo "$AUTH_SERVER_RESPONSE" | grep -q '"issuer"' && \
       echo "$AUTH_SERVER_RESPONSE" | grep -q '"jwks_uri"' && \
       echo "$AUTH_SERVER_RESPONSE" | grep -q '"scopes_supported"' && \
       echo "$AUTH_SERVER_RESPONSE" | grep -q '"response_types_supported"'; then
        echo "✅ Authorization Server metadata contains all required fields!"
    else
        echo "❌ Authorization Server metadata missing required fields"
        exit 1
    fi
    
    # Check if resource indicators are supported
    if echo "$AUTH_SERVER_RESPONSE" | grep -q '"resource_indicators_supported":true'; then
        echo "✅ Authorization Server supports resource indicators!"
    else
        echo "❌ Authorization Server missing resource indicators support"
        exit 1
    fi
else
    echo "❌ OAuth Authorization Server metadata test failed!"
    exit 1
fi

# Test JWKS endpoint
echo "🔍 Testing JWKS endpoint..."
JWKS_RESPONSE=$(curl -s http://localhost:9000/.well-known/jwks.json)

if [ $? -eq 0 ]; then
    echo "✅ JWKS endpoint test passed!"
    echo "📄 Response: $JWKS_RESPONSE"
    
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

# Test authenticated MCP initialize with OAuth metadata
echo "🔍 Testing authenticated MCP initialize with OAuth metadata..."
AUTH_INIT_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize"}')

if [ $? -eq 0 ]; then
    echo "✅ Authenticated initialize test passed!"
    echo "📄 Response: $AUTH_INIT_RESPONSE"
    
    # Check if response contains OAuth metadata
    if echo "$AUTH_INIT_RESPONSE" | grep -q '"oauth_metadata"' && \
       echo "$AUTH_INIT_RESPONSE" | grep -q '"protected_resource"' && \
       echo "$AUTH_INIT_RESPONSE" | grep -q '"authorization_server"'; then
        echo "✅ Initialize response includes OAuth metadata!"
    else
        echo "❌ Initialize response missing OAuth metadata"
        exit 1
    fi
else
    echo "❌ Authenticated initialize test failed!"
    exit 1
fi

# Test authenticated ping with OAuth metadata
echo "🔍 Testing authenticated ping with OAuth metadata..."
AUTH_PING_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "ping"}')

if [ $? -eq 0 ]; then
    echo "✅ Authenticated ping test passed!"
    echo "📄 Response: $AUTH_PING_RESPONSE"
    
    # Check if response contains OAuth metadata flag
    if echo "$AUTH_PING_RESPONSE" | grep -q '"oauth_metadata_available":true'; then
        echo "✅ Ping response indicates OAuth metadata availability!"
    else
        echo "❌ Ping response missing OAuth metadata flag"
        exit 1
    fi
else
    echo "❌ Authenticated ping test failed!"
    exit 1
fi

# Test authenticated tools/list (should still work)
echo "🔍 Testing authenticated tools/list..."
AUTH_TOOLS_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 3, "method": "tools/list"}')

if [ $? -eq 0 ]; then
    echo "✅ Authenticated tools/list test passed!"
    echo "📄 Response: $AUTH_TOOLS_RESPONSE"
    
    # Check if response contains tools
    if echo "$AUTH_TOOLS_RESPONSE" | grep -q '"name":"echo"'; then
        echo "✅ Echo tool is listed correctly!"
    else
        echo "❌ Echo tool not found in response!"
        exit 1
    fi
else
    echo "❌ Authenticated tools/list test failed!"
    exit 1
fi

# Test authenticated tools/call (should still work)
echo "🔍 Testing authenticated tools/call..."
AUTH_CALL_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "echo", "arguments": {"message": "Hello OAuth", "repeat_count": 2}}}')

if [ $? -eq 0 ]; then
    echo "✅ Authenticated tools/call test passed!"
    echo "📄 Response: $AUTH_CALL_RESPONSE"
    
    # Check if response contains the echoed message
    if echo "$AUTH_CALL_RESPONSE" | grep -q 'Hello OAuthHello OAuth'; then
        echo "✅ Echo tool works correctly!"
    else
        echo "❌ Echo tool response is incorrect!"
        exit 1
    fi
else
    echo "❌ Authenticated tools/call test failed!"
    exit 1
fi

# Test unauthenticated request (should still fail)
echo "🔍 Testing unauthenticated request..."
UNAUTH_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 5, "method": "initialize"}')

if [ $? -eq 0 ]; then
    echo "✅ Unauthenticated request test passed!"
    echo "📄 Response: $UNAUTH_RESPONSE"
    
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

echo ""
echo "🎉 Step 7 tests completed successfully!"
echo "✅ OAuth 2.0 Protected Resource metadata is working"
echo "✅ OAuth 2.0 Authorization Server metadata is working"
echo "✅ JWKS endpoint continues to work"
echo "✅ All existing MCP functionality still works"
echo "✅ OAuth metadata is included in MCP responses"
echo "✅ Resource indicators are supported"
echo "✅ Authentication enforcement continues to work"
echo "✅ Ready for next step: Scope-based authorization" 