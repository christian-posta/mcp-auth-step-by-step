#!/bin/bash

# Test script for Step 2: MCP Request Handling
echo "🧪 Testing Step 2: MCP Request Handling"
echo "========================================"

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

# Test health endpoint
echo "🔍 Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s http://localhost:9000/health)

if [ $? -eq 0 ]; then
    echo "✅ Health endpoint test passed!"
    echo "📄 Response: $HEALTH_RESPONSE"
else
    echo "❌ Health endpoint test failed!"
    exit 1
fi

# Test MCP ping method
echo "🔍 Testing MCP ping method..."
PING_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "ping"}')

if [ $? -eq 0 ]; then
    echo "✅ MCP ping test passed!"
    echo "📄 Response: $PING_RESPONSE"
    
    # Check if response contains expected fields
    if echo "$PING_RESPONSE" | grep -q '"jsonrpc":"2.0"' && echo "$PING_RESPONSE" | grep -q '"id":1'; then
        echo "✅ Response format is correct!"
    else
        echo "❌ Response format is incorrect!"
        exit 1
    fi
else
    echo "❌ MCP ping test failed!"
    exit 1
fi

# Test MCP method not found
echo "🔍 Testing MCP method not found..."
ERROR_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "unknown_method"}')

if [ $? -eq 0 ]; then
    echo "✅ MCP method not found test passed!"
    echo "📄 Response: $ERROR_RESPONSE"
    
    # Check if response contains error
    if echo "$ERROR_RESPONSE" | grep -q '"error"' && echo "$ERROR_RESPONSE" | grep -q '"code":-32601'; then
        echo "✅ Error handling is correct!"
    else
        echo "❌ Error handling is incorrect!"
        exit 1
    fi
else
    echo "❌ MCP method not found test failed!"
    exit 1
fi

echo ""
echo "🎉 Step 2 tests completed successfully!"
echo "✅ MCP request handling is working"
echo "✅ Ping method responds correctly"
echo "✅ Error handling for unknown methods works"
echo "✅ JSON-RPC 2.0 format is maintained" 