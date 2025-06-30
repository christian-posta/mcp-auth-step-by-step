# MCP Auth Step-by-Step

A complete Model Context Protocol (MCP) implementation demonstrating remote MCP server with HTTP transport, and another server with authorization and communication between a server and client over HTTP transport.

## Project Overview

This project consists of two main components:

1. **MCP Echo Server** - Two servers, that provides echo functionality. One without auth and one with JWT auth
2. **MCP Echo Client** - A client for communicating with the non-auth echo server; communication with the auth server should happen with the test file, or generate your own keys and call it

## Features

### Server Features
- **Echo Tool**: Echo back messages with optional repetition
- **HTTP Transport**: Communicate with the server over HTTP/JSON-RPC
- **MCP Compliance**: Follows the MCP specification for tools and prompts
- **JWT Authentication**: Secure authentication using JSON Web Tokens
- **Health Check**: Built-in health check endpoint
- **FastAPI**: Modern, fast web framework with automatic API documentation
- **Docker Support**: Containerized deployment ready

### Client Features
- **HTTP Transport**: Communicate with MCP servers over HTTP/JSON-RPC
- **Async Support**: Full async/await support for non-blocking operations
- **Type Safety**: Built with Pydantic for type safety and validation
- **Easy to Use**: Simple API for common MCP operations
- **Error Handling**: Comprehensive error handling and reporting

## Quick Start

### Prerequisites
- Python 3.10 or higher
- `uv` package manager (recommended) or `pip`

### Running the Server

#### Option 1: Using `uv` (Recommended)
```bash
cd echo
uv run python -m mcp_server_echo
```

To run the MCP server with JWT Authentication:
```bash
uv run python -m mcp_server_echo.jwt_server
```

You can generate your own tokens and call with [mcp-inspector](https://github.com/modelcontextprotocol/inspector):

```bash
uv run python generate_token.py
```
You can run the mcp-inspector and connect to the MCP server:

```bash
npx @modelcontextprotocol/inspector
```

Or run the full JWT test:

```bash
uv run python test_jwt_server.py
```


### Running the Client

The client is intended to be used with the non-auth MCP server. It shows HTTP Transport. To use test the JWT server, use mcp-inspector and generate your own token (see above)


#### Option 1: Using `uv` (Recommended)
```bash
cd echo-client
uv run python -m mcp_echo_client
```

## Usage

### Server Configuration

The server runs on `http://localhost:9000` by default. You can customize the host and port:

```bash
# Run with custom host and port
uv run python -m mcp_server_echo --host 127.0.0.1 --port 8080

# Run with environment variable
PORT=8000 uv run python -m mcp_server_echo
```

### Client Usage

#### Basic Usage
```python
import asyncio
from mcp_echo_client import MCPEchoClient

async def main():
    async with MCPEchoClient("http://localhost:9000") as client:
        # Initialize the connection
        await client.initialize()
        
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {tools}")
        
        # Call the echo tool
        result = await client.echo("Hello, World!", 3)
        print(f"Echo result: {result}")

asyncio.run(main())
```

#### Running the Demo
```bash
# Run the demo client (make sure server is running on port 9000)
uv run python -m mcp_echo_client

# Run against a different server
uv run python -m mcp_echo_client --server-url http://localhost:8000
```

### API Endpoints

- `POST /mcp` - Main MCP endpoint for JSON-RPC requests
- `GET /health` - Health check endpoint

### Available Tools

#### echo
Echo back a message with optional repetition.

**Parameters:**
- `message` (string, required): The message to echo back
- `repeat_count` (integer, optional): Number of times to repeat the message (1-10, default: 1)

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "tools/call",
  "params": {
    "name": "echo",
    "arguments": {
      "message": "Hello, World!",
      "repeat_count": 3
    }
  }
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Hello, World!Hello, World!Hello, World!"
      }
    ],
    "isError": false
  }
}
```

### Available Prompts

#### echo_prompt
A prompt that demonstrates echo functionality.

**Parameters:**
- `message` (string, required): The message to echo

**Example:**
```json
{
  "jsonrpc": "2.0",
  "id": "2",
  "method": "prompts/get",
  "params": {
    "name": "echo_prompt",
    "arguments": {
      "message": "Test message"
    }
  }
}
```

### Raw HTTP Test
```bash
# Initialize
curl -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"initialize"}'

# Call echo tool
curl -X POST http://localhost:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"2","method":"tools/call","params":{"name":"echo","arguments":{"message":"Hello","repeat_count":2}}}'
```


### Docker
```bash
# Build the server image
cd echo
docker build -t mcp-echo-server .

# Run the server
docker run -p 9000:9000 mcp-echo-server
```

## MCP Protocol Compliance

This implementation follows the Model Context Protocol specification:

- **Protocol Version**: 2025-06-18
- **Transport**: HTTP/JSON-RPC
- **Methods Supported**:
  - `initialize` - Initialize the connection
  - `tools/list` - List available tools
  - `tools/call` - Call a tool
  - `prompts/list` - List available prompts
  - `prompts/get` - Get a prompt
  - `ping` - Health check


## License

MIT
