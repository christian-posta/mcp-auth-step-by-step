
## Quick Start

Using `uv` (Recommended - No installation needed)

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


## Usage

### mcp inpsector
You can run the mcp-inspector and connect to the MCP server:

```bash
npx @modelcontextprotocol/inspector
```