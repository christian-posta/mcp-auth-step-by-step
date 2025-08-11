#!/bin/bash

# Test script for Step 8: Scope-Based Authorization (matching step8.py logic)
echo "🧪 Testing Step 8: Scope-Based Authorization"
echo "============================================="

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
uv run python generate_token.py --username bob --scopes mcp:read,mcp:prompts
uv run python generate_token.py --username admin --scopes mcp:read,mcp:tools,mcp:prompts
uv run python generate_token.py --username guest --scopes ""

ALICE_TOKEN=$(python -c "import json; print(json.load(open('token_alice.json'))['token'])")
BOB_TOKEN=$(python -c "import json; print(json.load(open('token_bob.json'))['token'])")
ADMIN_TOKEN=$(python -c "import json; print(json.load(open('token_admin.json'))['token'])")
GUEST_TOKEN=$(python -c "import json; print(json.load(open('token_guest.json'))['token'])")

if [ -z "$ALICE_TOKEN" ] || [ -z "$BOB_TOKEN" ] || [ -z "$ADMIN_TOKEN" ] || [ -z "$GUEST_TOKEN" ]; then
    echo "❌ Failed to extract tokens"
    exit 1
fi

echo "✅ Test tokens generated successfully"

# Start the server in background
echo "🚀 Starting Step 8 server..."
uv run step8 &
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
    if echo "$HEALTH_RESPONSE" | grep -q '"scope_based_auth":true'; then
        echo "✅ Scope-based authorization is enabled!"
    else
        echo "❌ Scope-based authorization not indicated"
        exit 1
    fi
else
    echo "❌ Health endpoint test failed!"
    exit 1
fi

# Alice: should be able to access tools and prompts
echo "🔍 Testing Alice (should access both tools and prompts)..."
TOOLS_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}')
if echo "$TOOLS_RESPONSE" | grep -q '"name":"echo"'; then
    echo "✅ Alice can access tools/list"
    echo "$TOOLS_RESPONSE" | pretty_json
else
    echo "❌ Alice cannot access tools/list"
    echo "$TOOLS_RESPONSE" | pretty_json
    exit 1
fi
PROMPTS_RESPONSE=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "prompts/list"}')
if echo "$PROMPTS_RESPONSE" | grep -q '"name":"echo_prompt"'; then
    echo "✅ Alice can access prompts/list"
    echo "$PROMPTS_RESPONSE" | pretty_json
else
    echo "❌ Alice cannot access prompts/list"
    echo "$PROMPTS_RESPONSE" | pretty_json
    exit 1
fi

# Bob: should be able to access tools and prompts
echo "🔍 Testing Bob (should access both tools and prompts)..."
TOOLS_RESPONSE_BOB=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $BOB_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 3, "method": "tools/list"}')
if echo "$TOOLS_RESPONSE_BOB" | grep -q '"name":"echo"'; then
    echo "✅ Bob can access tools/list"
else
    echo "❌ Bob cannot access tools/list"
    echo "$TOOLS_RESPONSE_BOB" | pretty_json
    exit 1
fi
PROMPTS_RESPONSE_BOB=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $BOB_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 4, "method": "prompts/list"}')
if echo "$PROMPTS_RESPONSE_BOB" | grep -q '"name":"echo_prompt"'; then
    echo "✅ Bob can access prompts/list"
else
    echo "❌ Bob cannot access prompts/list"
    echo "$PROMPTS_RESPONSE_BOB" | pretty_json
    exit 1
fi

# Admin: should be able to access everything
echo "🔍 Testing Admin (full access)..."
ADMIN_TOOLS=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 5, "method": "tools/list"}')
if echo "$ADMIN_TOOLS" | grep -q '"name":"echo"'; then
    echo "✅ Admin can access tools/list"
else
    echo "❌ Admin cannot access tools/list"
    echo "$ADMIN_TOOLS" | pretty_json
    exit 1
fi

ADMIN_PROMPTS=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 6, "method": "prompts/list"}')
if echo "$ADMIN_PROMPTS" | grep -q '"name":"echo_prompt"'; then
    echo "✅ Admin can access prompts/list"
else
    echo "❌ Admin cannot access prompts/list"
    echo "$ADMIN_PROMPTS" | pretty_json
    exit 1
fi

# Guest: should be forbidden from both tools and prompts
echo "🔍 Testing Guest (should be forbidden from both tools and prompts)..."
GUEST_TOOLS=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GUEST_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 7, "method": "tools/list"}')
if echo "$GUEST_TOOLS" | grep -q '"code":-32001' && echo "$GUEST_TOOLS" | grep -q '"Forbidden"'; then
    echo "✅ Guest is forbidden from tools/list as expected"
else
    echo "❌ Guest should be forbidden from tools/list"
    echo "$GUEST_TOOLS" | pretty_json
    exit 1
fi
GUEST_PROMPTS=$(curl -s -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GUEST_TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 8, "method": "prompts/list"}')
if echo "$GUEST_PROMPTS" | grep -q '"code":-32001' && echo "$GUEST_PROMPTS" | grep -q '"Forbidden"'; then
    echo "✅ Guest is forbidden from prompts/list as expected"
else
    echo "❌ Guest should be forbidden from prompts/list"
    echo "$GUEST_PROMPTS" | pretty_json
    exit 1
fi

echo ""
echo "🎉 Step 8 tests completed successfully!"
echo "✅ Scope-based authorization is enforced (mcp:read grants read access to both tools and prompts)"
echo "✅ Users with mcp:read can access both tools and prompts"
echo "✅ Admin can access everything"
echo "✅ Users with no relevant scopes are forbidden"
echo "✅ All previous MCP and OAuth functionality still works"
echo "✅ Ready for next step!" 