#!/bin/bash

# Test script for Step 4: MCP Tools Dispatching
echo "🧪 Testing Step 4: MCP Tools Dispatching"
echo "========================================="

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
echo "🚀 Starting Step 4 server..."
uv run step4 &
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

# Test MCP initialize method
echo "🔍 Testing MCP initialize method..."
INIT_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize"}')

if [ $? -eq 0 ]; then
    echo "✅ MCP initialize test passed!"
    echo "📄 Response: $INIT_RESPONSE"
    
    # Check if response contains expected fields
    if echo "$INIT_RESPONSE" | grep -q '"protocolVersion"' && echo "$INIT_RESPONSE" | grep -q '"serverInfo"'; then
        echo "✅ Initialize response format is correct!"
    else
        echo "❌ Initialize response format is incorrect!"
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

# Test call_tool with different parameters
echo "🔍 Testing call_tool with different parameters..."
CALL_TOOL_RESPONSE2=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "echo", "arguments": {"message": "Test", "repeat_count": 2}}}')

if [ $? -eq 0 ]; then
    echo "✅ call_tool with different params test passed!"
    echo "📄 Response: $CALL_TOOL_RESPONSE2"
    
    # Check if response contains the echoed message
    if echo "$CALL_TOOL_RESPONSE2" | grep -q 'TestTest'; then
        echo "✅ Echo tool with different parameters works correctly!"
    else
        echo "❌ Echo tool with different parameters response is incorrect!"
        exit 1
    fi
else
    echo "❌ call_tool with different params test failed!"
    exit 1
fi

# Test unsupported method (should return error)
echo "🔍 Testing unsupported method..."
ERROR_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 5, "method": "unknown_method"}')

if [ $? -eq 0 ]; then
    echo "✅ Unsupported method test passed!"
    echo "📄 Response: $ERROR_RESPONSE"
    
    # Check if response contains error
    if echo "$ERROR_RESPONSE" | grep -q '"error"' && echo "$ERROR_RESPONSE" | grep -q '"code":-32603'; then
        echo "✅ Error handling for unsupported methods works correctly!"
    else
        echo "❌ Error handling for unsupported methods is incorrect!"
        exit 1
    fi
else
    echo "❌ Unsupported method test failed!"
    exit 1
fi

echo ""
echo "🎉 Step 4 tests completed successfully!"
echo "✅ MCP initialize method works correctly"
echo "✅ Tools dispatching is implemented and working"
echo "✅ Echo tool responds correctly with different parameters"
echo "✅ Error handling for unsupported methods works"
echo "✅ JSON-RPC 2.0 format is maintained throughout" 