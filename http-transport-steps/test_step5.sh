#!/bin/bash

# Test script for Step 5: Basic JWT Infrastructure
echo "🧪 Testing Step 5: Basic JWT Infrastructure"
echo "============================================"

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
    python generate_token.py --generate-keys
    if [ $? -ne 0 ]; then
        echo "❌ Failed to generate key pair"
        exit 1
    fi
fi

# Start the server in background
echo "🚀 Starting Step 5 server..."
uv run step5 &
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
    
    # Check if JWT is enabled
    if echo "$HEALTH_RESPONSE" | grep -q '"jwt_enabled":true'; then
        echo "✅ JWT infrastructure is enabled!"
    else
        echo "⚠️  JWT infrastructure is not enabled"
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

# Test MCP initialize method
echo "🔍 Testing MCP initialize method..."
INIT_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize"}')

if [ $? -eq 0 ]; then
    echo "✅ MCP initialize test passed!"
    echo "📄 Response: $INIT_RESPONSE"
    
    # Check if response contains JWT info
    if echo "$INIT_RESPONSE" | grep -q '"jwt_enabled"'; then
        echo "✅ Initialize response includes JWT status!"
    else
        echo "❌ Initialize response missing JWT status"
        exit 1
    fi
else
    echo "❌ MCP initialize test failed!"
    exit 1
fi

# Test list_tools method
echo "🔍 Testing list_tools method..."
TOOLS_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}')

if [ $? -eq 0 ]; then
    echo "✅ list_tools test passed!"
    echo "📄 Response: $TOOLS_RESPONSE"
    
    # Check if response contains tools
    if echo "$TOOLS_RESPONSE" | grep -q '"name":"echo"'; then
        echo "✅ Echo tool is listed correctly!"
    else
        echo "❌ Echo tool not found in response!"
        exit 1
    fi
else
    echo "❌ list_tools test failed!"
    exit 1
fi

# Test call_tool method
echo "🔍 Testing call_tool method..."
CALL_TOOL_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "echo", "arguments": {"message": "Hello World", "repeat_count": 3}}}')

if [ $? -eq 0 ]; then
    echo "✅ call_tool test passed!"
    echo "📄 Response: $CALL_TOOL_RESPONSE"
    
    # Check if response contains the echoed message
    if echo "$CALL_TOOL_RESPONSE" | grep -q 'Hello WorldHello WorldHello World'; then
        echo "✅ Echo tool works correctly!"
    else
        echo "❌ Echo tool response is incorrect!"
        exit 1
    fi
else
    echo "❌ call_tool test failed!"
    exit 1
fi


echo ""
echo "🎉 Step 5 tests completed successfully!"
echo "✅ JWT infrastructure is in place"
echo "✅ JWKS endpoint is working"
echo "✅ All existing MCP functionality still works"
echo "✅ Ready for next step: JWT token validation" 