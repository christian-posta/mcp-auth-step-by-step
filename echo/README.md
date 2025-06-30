# MCP Echo Server

A Model Context Protocol (MCP) server that provides echo functionality over HTTP transport.

## Features

- **Echo Tool**: Echo back messages with optional repetition
- **HTTP Transport**: Communicate with the server over HTTP/JSON-RPC
- **MCP Compliance**: Follows the MCP specification for tools and prompts
- **Health Check**: Built-in health check endpoint
- **FastAPI**: Modern, fast web framework with automatic API documentation
- **Docker Support**: Containerized deployment ready

## Quick Start

### Option 1: Using `uv` (Recommended - No installation needed)

```bash
cd src/echo
uv run python -m mcp_server_echo
```

To run the MCP server with Auth:

```bash
uv run python -m mcp_server_echo.jwt_server
```

You can run with your own tokens by generating them:

```bash
uv run python generate_token.py
```

Or run the full test:

```bash
uv run python test_jwt_server.py
```

This will automatically:
- Create a virtual environment
- Install dependencies from `pyproject.toml`
- Start the server on `http://localhost:9000`

### Option 2: Using `uvx` (Even simpler)

```bash
cd src/echo
uvx python -m mcp_server_echo
```

### Option 3: Manual installation

```bash
cd src/echo
pip install -e .
python -m mcp_server_echo
```

## Usage

### mcp inpsector
You can run the mcp-inspector and connect to the MCP server:

```bash
npx @modelcontextprotocol/inspector
```

### Running the Server

```bash
# Run with default settings (host: 0.0.0.0, port: 9000)
uv run python -m mcp_server_echo

# Run with custom host and port
uv run python -m mcp_server_echo --host 127.0.0.1 --port 8080

# Run with environment variable
PORT=8000 uv run python -m mcp_server_echo

# Run the file directly
uv run python src/mcp_server_echo/server.py --port 9000
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

## Testing

### Health Check
```bash
curl http://localhost:9000/health
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

### Using the Client
```bash
cd src/echo-client
uv run python -m mcp_echo_client
```

## Development

### Project Structure
```
src/echo/
├── src/mcp_server_echo/
│   ├── __init__.py
│   ├── __main__.py
│   └── server.py
├── pyproject.toml
├── README.md
├── Dockerfile
├── example.py
├── test_server.py
└── install_and_test.py
```

### Dependencies
- `mcp>=1.1.3` - MCP Python SDK
- `fastapi>=0.104.0` - Web framework
- `uvicorn>=0.24.0` - ASGI server
- `pydantic>=2.0.0` - Data validation

### Docker
```bash
# Build the server image
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