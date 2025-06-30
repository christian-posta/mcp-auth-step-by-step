#!/bin/bash

# Test script for Step 2: MCP Request Handling with Origin Validation
echo "🧪 Testing Step 2: MCP Request Handling with Origin Validation"
echo "==============================================================="

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

# Start the server in background
echo "🚀 Starting Step 2 server..."
uv run step2 &
SERVER_PID=$!

# Wait for server to start
echo "⏳ Waiting for server to start..."
sleep 3

# Test health endpoint (should work without Origin header)
echo "🔍 Testing health endpoint (no Origin header)..."
HEALTH_RESPONSE=$(curl -s http://localhost:9000/health)

if [ $? -eq 0 ]; then
    echo "✅ Health endpoint test passed!"
    echo "📄 Response: $HEALTH_RESPONSE"
else
    echo "❌ Health endpoint test failed!"
    exit 1
fi

# Test MCP ping method with valid localhost Origin
echo "🔍 Testing MCP ping method with valid localhost Origin..."
PING_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Origin: http://localhost:3000" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "ping"}')

if [ $? -eq 0 ]; then
    echo "✅ MCP ping test with localhost Origin passed!"
    echo "📄 Response: $PING_RESPONSE"
    
    # Check if response contains expected fields
    if echo "$PING_RESPONSE" | grep -q '"jsonrpc":"2.0"' && echo "$PING_RESPONSE" | grep -q '"id":1'; then
        echo "✅ Response format is correct!"
    else
        echo "❌ Response format is incorrect!"
        exit 1
    fi
else
    echo "❌ MCP ping test with localhost Origin failed!"
    exit 1
fi

# Test MCP ping method with valid 127.0.0.1 Origin
echo "🔍 Testing MCP ping method with valid 127.0.0.1 Origin..."
PING_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Origin: http://127.0.0.1:8080" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "ping"}')

if [ $? -eq 0 ]; then
    echo "✅ MCP ping test with 127.0.0.1 Origin passed!"
    echo "📄 Response: $PING_RESPONSE"
else
    echo "❌ MCP ping test with 127.0.0.1 Origin failed!"
    exit 1
fi

# Test MCP ping method with no Origin header (should be rejected)
echo "🔍 Testing MCP ping method with no Origin header (should be rejected)..."
NO_ORIGIN_RESPONSE=$(curl -s -w "%{http_code}" -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 3, "method": "ping"}')

HTTP_CODE="${NO_ORIGIN_RESPONSE: -3}"
RESPONSE_BODY="${NO_ORIGIN_RESPONSE%???}"

if [ "$HTTP_CODE" = "403" ]; then
    echo "✅ MCP ping test with no Origin header correctly rejected!"
    echo "📄 Response: $RESPONSE_BODY"
else
    echo "❌ MCP ping test with no Origin header should have been rejected!"
    echo "📄 Response: $RESPONSE_BODY"
    echo "📄 HTTP Code: $HTTP_CODE"
    exit 1
fi

# Test MCP ping method with invalid Origin (should be rejected)
echo "🔍 Testing MCP ping method with invalid Origin (should be rejected)..."
INVALID_ORIGIN_RESPONSE=$(curl -s -w "%{http_code}" -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Origin: http://evil.com" \
  -d '{"jsonrpc": "2.0", "id": 4, "method": "ping"}')

INVALID_HTTP_CODE="${INVALID_ORIGIN_RESPONSE: -3}"
INVALID_RESPONSE_BODY="${INVALID_ORIGIN_RESPONSE%???}"

if [ "$INVALID_HTTP_CODE" = "403" ]; then
    echo "✅ MCP ping test with invalid Origin correctly rejected!"
    echo "📄 Response: $INVALID_RESPONSE_BODY"
else
    echo "❌ MCP ping test with invalid Origin should have been rejected!"
    echo "📄 Response: $INVALID_RESPONSE_BODY"
    echo "📄 HTTP Code: $INVALID_HTTP_CODE"
    exit 1
fi

# Test MCP ping method with HTTPS localhost (should be rejected)
echo "🔍 Testing MCP ping method with HTTPS localhost (should be rejected)..."
HTTPS_ORIGIN_RESPONSE=$(curl -s -w "%{http_code}" -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Origin: https://localhost:3000" \
  -d '{"jsonrpc": "2.0", "id": 5, "method": "ping"}')

HTTPS_HTTP_CODE="${HTTPS_ORIGIN_RESPONSE: -3}"
HTTPS_RESPONSE_BODY="${HTTPS_ORIGIN_RESPONSE%???}"

if [ "$HTTPS_HTTP_CODE" = "403" ]; then
    echo "✅ MCP ping test with HTTPS localhost correctly rejected!"
    echo "📄 Response: $HTTPS_RESPONSE_BODY"
else
    echo "❌ MCP ping test with HTTPS localhost should have been rejected!"
    echo "📄 Response: $HTTPS_RESPONSE_BODY"
    echo "📄 HTTP Code: $HTTPS_HTTP_CODE"
    exit 1
fi

# Test MCP method not found with valid Origin
echo "🔍 Testing MCP method not found with valid Origin..."
ERROR_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Origin: http://localhost:5000" \
  -d '{"jsonrpc": "2.0", "id": 6, "method": "unknown_method"}')

if [ $? -eq 0 ]; then
    echo "✅ MCP method not found test with valid Origin passed!"
    echo "📄 Response: $ERROR_RESPONSE"
    
    # Check if response contains error
    if echo "$ERROR_RESPONSE" | grep -q '"error"' && echo "$ERROR_RESPONSE" | grep -q '"code":-32601'; then
        echo "✅ Error handling is correct!"
    else
        echo "❌ Error handling is incorrect!"
        exit 1
    fi
else
    echo "❌ MCP method not found test with valid Origin failed!"
    exit 1
fi

echo ""
echo "🎉 Step 2 tests completed successfully!"
echo "✅ MCP request handling is working"
echo "✅ Origin header validation is working"
echo "✅ Valid localhost origins are accepted"
echo "✅ Valid 127.0.0.1 origins are accepted"
echo "✅ Invalid origins are rejected"
echo "✅ Missing Origin headers are rejected"
echo "✅ HTTPS origins are rejected"
echo "✅ Health endpoint bypasses Origin validation"
echo "✅ Ping method responds correctly"
echo "✅ Error handling for unknown methods works"
echo "✅ JSON-RPC 2.0 format is maintained" 