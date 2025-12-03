# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, Cursor, GitHub Copilot, etc.) when working with code in this repository.

## Prerequisites

- Python 3.10+
- `uv` package manager: https://docs.astral.sh/uv/getting-started/installation/
- Docker (for Keycloak)
- `jq` (for test scripts)

## Project Structure

```
├── src/mcp_http/       # MCP server implementations (step1.py - step14.py)
├── keycloak/           # Keycloak Docker + setup scripts
│   ├── docker-compose.yml
│   ├── config.json     # Realm, clients, scopes, users configuration
│   └── setup_keycloak.py
├── test_step*.sh       # Test scripts for each step
├── generate_token.py   # Local JWT token generator (steps 5-8)
├── *.env               # Environment files for Keycloak configuration
└── pyproject.toml      # Dependencies and entry points
```

## Ports

- **9000** - MCP Server (all steps)
- **8080** - Keycloak (direct access)
- **9090** - Keycloak via proxy (optional)

## Project Overview

This is a step-by-step tutorial demonstrating how to build an MCP (Model Context Protocol) server with HTTP transport and JWT authentication. Each step builds incrementally on the previous one, progressing from a basic FastAPI skeleton to a full OAuth 2.0/Keycloak-integrated MCP server.

Companion blog series: https://blog.christianposta.com/understanding-mcp-authorization-step-by-step/

## Commands

### Running Steps

```bash
# Run any step (1-11) using uv
uv run step1
uv run step2
# ...etc

# Run step10 with environment configuration
uv run step10 --env keycloak_direct.env  # direct access at localhost:8080
uv run step10 --env keycloak_proxy.env   # proxy access at localhost:9090
```

### Testing

```bash
# Run test script for any step
./test_step1.sh
./test_step2.sh
# ...etc
```

### Token Generation (steps 5-8)

```bash
uv run python generate_token.py --username alice --scopes mcp:read,mcp:tools
```

### Keycloak Setup

```bash
# Start Keycloak (in keycloak/ directory)
docker compose up -d

# Configure Keycloak realm
source .venv/bin/activate
cd keycloak
python setup_keycloak.py --config config.json --url http://localhost:8080
```

### Keycloak Token Generation (step 9+)

```bash
curl -X POST "http://localhost:8080/realms/mcp-realm/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=mcp-test-client" \
  -d "username=mcp-admin" \
  -d "password=admin123" \
  -d "scope=openid profile email mcp:read mcp:tools mcp:prompts" | jq -r '.access_token'
```

## Architecture

### Step Progression (src/mcp_http/stepN.py)

- **step1-4**: Basic FastAPI + MCP protocol (no auth)
- **step5-6**: JWT infrastructure and validation with local keys
- **step7-8**: OAuth 2.0 metadata endpoints + scope-based authorization
- **step9-10**: Keycloak integration with JWKS fetching
- **step11**: Dynamic Client Registration (DCR) client
- **step12**: Per-tool RBAC with FastAPI (educational, manual implementation)
- **step13**: FastMCP with basic OAuth (all tools available to authenticated users)
- **step14**: FastMCP with per-tool RBAC and filtered tools/list

### Key Components

- **Origin validation middleware**: Prevents DNS rebinding by restricting to localhost/127.0.0.1
- **JWKS caching**: 5-minute cache for Keycloak public keys
- **Scope-based authorization**: `mcp:read`, `mcp:tools`, `mcp:prompts`
- **Per-tool RBAC (step12/14)**: Hierarchical scopes - `mcp:tools` grants all, `mcp:tools:echo` grants specific tool

### MCP Endpoints

- `POST /mcp` - Main MCP protocol endpoint (protected)
- `GET /.well-known/oauth-protected-resource` - OAuth metadata (RFC 9728)
- `GET /.well-known/jwks.json` - Local JWKS (steps 5-8)
- `GET /health` - Health check

### Environment Configuration (step10+)

Uses `--env` flag with env files:
- `KEYCLOAK_URL`, `KEYCLOAK_REALM`
- `MCP_SERVER_URL`, `JWT_AUDIENCE`, `JWT_ISSUER`

## Dependencies

Managed via `pyproject.toml` with `uv`. Key dependencies: fastapi, uvicorn, mcp, PyJWT, cryptography, python-dotenv, httpx, fastmcp.

## Per-Tool RBAC (Step 12/14)

Test users for per-tool authorization:
- `mcp-admin` / `admin123` - `mcp:tools` (all tools)
- `mcp-user` / `user123` - `mcp:tools:echo`, `mcp:tools:time`, `mcp:tools:calc`
- `mcp-guest` / `guest123` - `mcp:tools:echo` only
- `mcp-readonly` / `readonly123` - `mcp:read` (no tools)

Tools: `echo`, `get_time`, `calculate`, `system_info` (admin only)

## Keycloak Admin Access

- URL: http://localhost:8080
- Username: `admin`
- Password: `admin`

## Adding a New Step

1. Copy the previous step file: `cp src/mcp_http/step14.py src/mcp_http/step15.py`
2. Add entry point to `pyproject.toml`: `step15 = "mcp_http.step15:main"`
3. Create test script: `cp test_step14.py test_step15.py` and update references
4. Update Keycloak config if new scopes/users needed: `keycloak/config.json`

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Connection refused` on port 8080 | Start Keycloak: `cd keycloak && docker compose up -d` |
| `Token has expired` | Generate new token with curl command |
| `Invalid token audience` | Check `JWT_AUDIENCE` matches Keycloak client ID (`echo-mcp-server`) |
| `JWKS fetch failed` | Verify Keycloak is running and realm exists |
| `403 Forbidden` on tool call | User missing required scope (check `mcp:tools:<name>`) |
| Keycloak setup fails | Ensure realm doesn't exist or use `--force` flag |
