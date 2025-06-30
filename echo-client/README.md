# MCP Echo Client

A Model Context Protocol (MCP) client for communicating with the echo server over HTTP.

## Features

- **HTTP Transport**: Communicate with MCP servers over HTTP/JSON-RPC
- **Async Support**: Full async/await support for non-blocking operations
- **Type Safety**: Built with Pydantic for type safety and validation
- **Easy to Use**: Simple API for common MCP operations
- **Error Handling**: Comprehensive error handling and reporting

## Quick Start

### Option 1: Using `uv` (Recommended - No installation needed)

```bash
cd src/echo-client
uv run python -m mcp_echo_client
```

This will automatically:
- Create a virtual environment
- Install dependencies from `pyproject.toml`
- Run the demo client against the echo server

### Option 2: Using `uvx` (Even simpler)

```bash
cd src/echo-client
uvx python -m mcp_echo_client
```

### Option 3: Manual installation

```bash
cd src/echo-client
pip install -e .
python -m mcp_echo_client
```

## Usage

### Basic Usage

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

### Running the Demo

```bash
# Run the demo client (make sure server is running on port 9000)
uv run python -m mcp_echo_client

# Or run the demo function directly
uv run python -c "import asyncio; from mcp_echo_client import demo; asyncio.run(demo())"

# Run against a different server
uv run python -m mcp_echo_client --server-url http://localhost:8000
```

### API Reference

#### MCPEchoClient

The main client class for communicating with MCP servers.

**Constructor:**
```python
MCPEchoClient(server_url: str = "http://localhost:9000")
```

**Methods:**

- `initialize()` - Initialize the MCP connection
- `list_tools()` - List available tools
- `call_tool(name, arguments)` - Call a tool by name with arguments
- `list_prompts()` - List available prompts
- `get_prompt(name, arguments)` - Get a prompt by name with optional arguments
- `ping()` - Send a ping to the server
- `echo(message, repeat_count)` - Convenience method to call the echo tool
- `health_check()` - Check server health

### Example Requests

#### Initialize Connection
```python
result = await client.initialize()
# Returns server capabilities and info
```

#### List Tools
```python
tools = await client.list_tools()
# Returns list of available tools
```

#### Call Echo Tool
```python
result = await client.echo("Hello, World!", 3)
# Returns: "Hello, World!Hello, World!Hello, World!"
```

#### Get Prompt
```python
prompt = await client.get_prompt("echo_prompt", {"message": "Test"})
# Returns prompt with templated content
```

## Testing

### Prerequisites
Make sure the echo server is running:
```bash
cd src/echo
uv run python -m mcp_server_echo
```

### Run Client Tests
```bash
cd src/echo-client
uv run python -m mcp_echo_client
```

### Manual Testing
```python
import asyncio
from mcp_echo_client import MCPEchoClient

async def test_client():
    async with MCPEchoClient() as client:
        # Health check
        health = await client.health_check()
        print(f"Server health: {health}")
        
        # Initialize
        init = await client.initialize()
        print(f"Server info: {init.get('serverInfo', {})}")
        
        # Echo test
        result = await client.echo("Test message", 2)
        print(f"Echo result: {result}")

asyncio.run(test_client())
```

## Development

### Project Structure
```
src/echo-client/
├── src/mcp_echo_client/
│   ├── __init__.py
│   ├── __main__.py
│   └── client.py
├── pyproject.toml
└── README.md
```

### Dependencies
- `httpx>=0.25.0` - HTTP client
- `pydantic>=2.0.0` - Data validation

### Running in Development
```bash
cd src/echo-client
uv venv
source .venv/bin/activate
uv pip install -e .
python -m mcp_echo_client
```

## Error Handling

The client includes comprehensive error handling:

```python
async with MCPEchoClient() as client:
    try:
        result = await client.echo("Hello", 3)
        print(f"Success: {result}")
    except Exception as e:
        print(f"Error: {e}")
        # Handle connection errors, MCP errors, etc.
```

## License

MIT 