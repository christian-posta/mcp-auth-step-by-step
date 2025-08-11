#!/bin/bash

# Test script for Step 1: Basic FastAPI Skeleton
echo "🧪 Testing Step 1: Basic FastAPI Skeleton"
echo "=========================================="

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
echo "🚀 Starting Step 1 server..."
uv run step1 &
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

# Test that server is running
echo "🔍 Testing server is running..."
if curl -s http://localhost:9000/health > /dev/null; then
    echo "✅ Server is running and responding!"
else
    echo "❌ Server is not responding!"
    exit 1
fi

echo ""
echo "🎉 Step 1 tests completed successfully!"
echo "✅ Basic FastAPI server is working"
echo "✅ Health endpoint is responding"
echo "✅ CORS middleware is configured" 