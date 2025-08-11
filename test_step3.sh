#!/bin/bash

# Test script for Step 3: MCP Tools and Prompts
echo "🧪 Testing Step 3: MCP Tools and Prompts"
echo "========================================="

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

# Start the server in background
echo "🚀 Starting Step 3 server..."
uv run step3 &
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
    echo "📄 Response:"
    echo "$PING_RESPONSE" | pretty_json
else
    echo "❌ MCP ping test failed!"
    exit 1
fi

# Test list_tools method
echo "🔍 Testing list_tools method..."
TOOLS_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}')

if [ $? -eq 0 ]; then
    echo "✅ list_tools test passed!"
    echo "📄 Response:"
    echo "$TOOLS_RESPONSE" | pretty_json
    
    # Check if response contains error (expected since dispatching not implemented)
    if echo "$TOOLS_RESPONSE" | grep -q '"error"' && echo "$TOOLS_RESPONSE" | grep -q '"code":-32601'; then
        echo "✅ Correctly returns 'Method not found' (dispatching not implemented yet)"
    else
        echo "❌ Unexpected response format!"
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
    echo "📄 Response:"
    echo "$CALL_TOOL_RESPONSE" | pretty_json
    
    # Check if response contains error (expected since dispatching not implemented)
    if echo "$CALL_TOOL_RESPONSE" | grep -q '"error"' && echo "$CALL_TOOL_RESPONSE" | grep -q '"code":-32601'; then
        echo "✅ Correctly returns 'Method not found' (dispatching not implemented yet)"
    else
        echo "❌ Unexpected response format!"
        exit 1
    fi
else
    echo "❌ call_tool test failed!"
    exit 1
fi

# Test list_prompts method
echo "🔍 Testing list_prompts method..."
PROMPTS_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 4, "method": "prompts/list"}')

if [ $? -eq 0 ]; then
    echo "✅ list_prompts test passed!"
    echo "📄 Response:"
    echo "$PROMPTS_RESPONSE" | pretty_json
    
    # Check if response contains error (expected since dispatching not implemented)
    if echo "$PROMPTS_RESPONSE" | grep -q '"error"' && echo "$PROMPTS_RESPONSE" | grep -q '"code":-32601'; then
        echo "✅ Correctly returns 'Method not found' (dispatching not implemented yet)"
    else
        echo "❌ Unexpected response format!"
        exit 1
    fi
else
    echo "❌ list_prompts test failed!"
    exit 1
fi

# Test get_prompt method
echo "🔍 Testing get_prompt method..."
GET_PROMPT_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 5, "method": "prompts/get", "params": {"name": "echo_prompt", "arguments": {"message": "Test Message"}}}')

if [ $? -eq 0 ]; then
    echo "✅ get_prompt test passed!"
    echo "📄 Response:"
    echo "$GET_PROMPT_RESPONSE" | pretty_json
    
    # Check if response contains error (expected since dispatching not implemented)
    if echo "$GET_PROMPT_RESPONSE" | grep -q '"error"' && echo "$GET_PROMPT_RESPONSE" | grep -q '"code":-32601'; then
        echo "✅ Correctly returns 'Method not found' (dispatching not implemented yet)"
    else
        echo "❌ Unexpected response format!"
        exit 1
    fi
else
    echo "❌ get_prompt test failed!"
    exit 1
fi

echo ""
echo "🎉 Step 3 tests completed successfully!"
echo "✅ MCP tools and prompts are defined (but not dispatched yet)"
echo "✅ Server correctly returns 'Method not found' for unimplemented methods"
echo "✅ JSON-RPC 2.0 error format is maintained"
echo "✅ Ready for next step: implementing method dispatching" 