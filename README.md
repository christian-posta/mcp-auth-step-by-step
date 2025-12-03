# MCP Auth Step by Step

This repository demonstrates building an MCP (Model Context Protocol) server with HTTP transport and JWT authentication, progressing through iterative steps.

> **For AI coding assistants:** See [AGENTS.md](AGENTS.md) for project guidance.

## Quick Start

```bash
# Prerequisites: Python 3.10+, uv, Docker, jq

# 1. Start Keycloak
cd keycloak && docker compose up -d && cd ..

# 2. Setup Keycloak realm
uv run python keycloak/setup_keycloak.py --config keycloak/config.json --url http://localhost:8080

# 3. Run MCP server (choose a step)
uv run step12  # Per-tool RBAC with FastAPI
# or
uv run step13  # FastMCP with basic OAuth
# or
uv run step14  # FastMCP with per-tool RBAC

# 4. Test
./test_step12.sh
# or
uv run python test_step13.py
uv run python test_step14.py
```

## Blog Series

This repo is a companion to the in-depth, step-by-step blog posts on "MCP Authorization". See the following:

* [Understanding MCP Authorization, Step by Step, Part One](https://blog.christianposta.com/understanding-mcp-authorization-step-by-step/)
* [Understanding MCP Authorization, Step by Step, Part Two](https://blog.christianposta.com/understanding-mcp-authorization-step-by-step-part-two/)
* [Understanding MCP Authorization, Step by Step, Part Three](https://blog.christianposta.com/understanding-mcp-authorization-step-by-step-part-three/)

Part 4 (late addition to the series):
[MCP Authorization With Dynamic Client Registration](https://blog.christianposta.com/understanding-mcp-authorization-with-dynamic-client-registration/)


## MCP Authorization Specification Requirements

The table below shows support for OAuth RFCs required by the MCP authorization specification across major identity providers.

### RFC Requirements Summary:
- **PKCE**: Proof Key for Code Exchange (OAuth 2.1 requirement)
- **RFC 8414**: OAuth 2.0 Authorization Server Metadata
- **RFC 7591**: OAuth 2.0 Dynamic Client Registration Protocol
- **RFC 8707**: Resource Indicators for OAuth 2.0

| Identity Provider | PKCE | RFC 8414 | RFC 7591 | RFC 8707 |
|-------------------|------|----------|----------|----------|
| **Okta** | Yes | Yes | Yes | N0 |
| **Auth0** | Yes | Yes | Kinda | No |
| **Keycloak** | Yes | Yes | Yes | No |
| **Ping Federate** | Yes | Yes | Yes | Yes |
| **ForgeRock** | Yes | Yes | Yes | Kinda |
| **Google OAuth** | Yes | No | No | No |
| **Microsoft Entra** | Yes | Yes | No | No |


## Overview

The project shows how to build a secure MCP server with:
- FastAPI-based HTTP transport
- JWT token authentication
- OAuth 2.0 metadata endpoints
- Scope-based authorization
- Role-based access control

## Step-by-Step Progression

### Step 1: Basic FastAPI Skeleton
- **File**: `http-transport-steps/src/mcp_http/step1.py`
- **What it adds**: Basic FastAPI application with health endpoint
- **Key features**: 
  - FastAPI server setup
  - Basic health check endpoint (`/health`)
  - Foundation for MCP HTTP transport

### Step 2: Basic MCP Request Handling
- **File**: `http-transport-steps/src/mcp_http/step2.py`
- **What it adds**: MCP protocol request/response handling
- **Key features**:
  - MCP request parsing and validation
  - Basic MCP response structure
  - `/mcp` endpoint for MCP protocol communication
  - JSON-RPC style request handling

### Step 3: MCP Tools and Prompts Definitions
- **File**: `http-transport-steps/src/mcp_http/step3.py`
- **What it adds**: MCP tools and prompts without dispatching
- **Key features**:
  - Tool definitions (`echo`, `get_time`)
  - Prompt definitions (`greeting`, `help`)
  - MCP protocol compliance for tools and prompts
  - No actual tool execution yet

### Step 4: MCP Tools Dispatching
- **File**: `http-transport-steps/src/mcp_http/step4.py`
- **What it adds**: Actual tool execution and prompt handling
- **Key features**:
  - Tool dispatching and execution
  - Prompt retrieval and handling
  - Working MCP server with functional tools
  - Error handling for invalid requests

### Step 5: Basic JWT Infrastructure
- **File**: `http-transport-steps/src/mcp_http/step5.py`
- **What it adds**: JWT public key loading and JWKS endpoint
- **Key features**:
  - Public key loading from file
  - JWKS (JSON Web Key Set) endpoint (`/.well-known/jwks.json`)
  - External token generation script (`generate_token.py`)
  - JWT infrastructure foundation

### Step 6: JWT Token Validation
- **File**: `http-transport-steps/src/mcp_http/step6.py`
- **What it adds**: JWT authentication middleware and enforcement
- **Key features**:
  - JWT token validation middleware
  - Authentication enforcement on `/mcp` endpoint
  - User context extraction from tokens
  - Proper error responses for invalid/missing tokens

### Step 7: OAuth 2.0 Metadata Endpoints
- **File**: `http-transport-steps/src/mcp_http/step7.py`
- **What it adds**: OAuth 2.0 metadata for protected resource and authorization server
- **Key features**:
  - `/.well-known/oauth-protected-resource` endpoint
  - `/.well-known/oauth-authorization-server` endpoint
  - Enhanced health endpoint with OAuth metadata
  - OAuth metadata in MCP responses

### Step 8: Scope-Based Authorization
- **File**: `http-transport-steps/src/mcp_http/step8.py`
- **What it adds**: Permission checking and role-based access control
- **Key features**:
  - `check_permission` method for scope validation
  - Role-based access control (admin, user, guest)
  - 403 Forbidden responses for insufficient permissions
  - Scope enforcement for MCP operations

### Step 9: Keycloak Integration
- **File**: `src/mcp_http/step9.py`
- **What it adds**: Keycloak as external identity provider
- **Key features**:
  - Integration with Keycloak for JWT validation
  - JWKS fetching from Keycloak
  - OAuth 2.0 metadata discovery

### Step 10: Full Keycloak Integration
- **File**: `src/mcp_http/step10.py`
- **What it adds**: Complete Keycloak integration with environment configuration
- **Key features**:
  - Environment-based configuration
  - Full OAuth 2.0 flow support
  - Scope-based authorization with Keycloak roles

### Step 11: Dynamic Client Registration
- **File**: `src/mcp_http/step11.py`
- **What it adds**: OAuth 2.0 Dynamic Client Registration (DCR)
- **Key features**:
  - RFC 7591 compliant DCR
  - Automatic client registration

### Step 12: Per-Tool RBAC (FastAPI)
- **File**: `src/mcp_http/step12.py`
- **What it adds**: Fine-grained, per-tool authorization using manual FastAPI implementation
- **Key features**:
  - 4 tools with individual scope requirements: `echo`, `get_time`, `calculate`, `system_info`
  - Hierarchical scope system: `mcp:tools` grants access to ALL tools
  - Tool-specific scopes: `mcp:tools:echo`, `mcp:tools:time`, `mcp:tools:calc`, `mcp:tools:admin`
  - Filtered `tools/list` response based on user permissions
  - Educational implementation showing "how it works under the hood"

### Step 13: FastMCP with Basic OAuth
- **File**: `src/mcp_http/step13.py`
- **What it adds**: Modern FastMCP framework with OAuth authentication
- **Key features**:
  - Built-in `JWTVerifier` for token validation
  - `RemoteAuthProvider` for OAuth integration
  - `get_access_token()` for accessing token claims
  - All tools available to any authenticated user (no per-tool RBAC)
  - ~200 lines of code

### Step 14: FastMCP with Per-Tool RBAC
- **File**: `src/mcp_http/step14.py`
- **What it adds**: Per-tool RBAC with filtered tools/list
- **Key features**:
  - `RBACFastMCP` subclass with custom `_filtered_list_tools`
  - Users only see tools they have permission to use
  - Hierarchical scope support: `mcp:tools` grants access to ALL tools
  - Per-tool scopes: `mcp:tools:echo`, `mcp:tools:time`, `mcp:tools:calc`, `mcp:tools:admin`

#### Step 12 vs Step 13 vs Step 14 Comparison

| Feature | Step 12 (FastAPI) | Step 13 (FastMCP Basic) | Step 14 (FastMCP RBAC) |
|---------|-------------------|-------------------------|------------------------|
| JWT Validation | Manual JWKS fetch | JWTVerifier built-in | JWTVerifier built-in |
| OAuth Integration | Custom endpoints | RemoteAuthProvider | RemoteAuthProvider |
| Tool Access | Per-tool scopes | All authenticated | Per-tool scopes |
| tools/list | Filtered | All tools | Filtered |
| Code Lines | ~400 lines | ~200 lines | ~350 lines |

#### Per-Tool Scope Matrix (Step 12/14)

| User | echo | get_time | calculate | system_info |
|------|------|----------|-----------|-------------|
| mcp-admin (mcp:tools) | ✓ | ✓ | ✓ | ✓ |
| mcp-user | ✓ | ✓ | ✓ | ✗ |
| mcp-guest | ✓ | ✗ | ✗ | ✗ |
| mcp-readonly | ✗ | ✗ | ✗ | ✗ |

## JWT Token Structure

The JWT tokens include:
- **User ID**: Unique identifier for the user
- **Scopes**: Permissions (e.g., `mcp:read`, `mcp:tools`, `mcp:prompts`)
- **Roles**: User roles (e.g., `admin`, `user`, `guest`)
- **Expiration**: Token validity period

## Testing

Each step includes a corresponding test script (`test_stepX.sh`) that validates:
- Basic functionality
- JWT authentication (steps 5+)
- Authorization (steps 6+)
- OAuth metadata (steps 7+)
- Access control (steps 8+)

## Usage

### Prerequisites

1. **Python 3.10+**
2. **uv** package manager: https://docs.astral.sh/uv/getting-started/installation/
3. **Docker** (for running Keycloak)
4. **jq** (for test scripts)

### Running Steps with uv


```bash
# Run any step using uv run
uv run step1
uv run step2
uv run step3
# ... etc
```

### Running Step 10 with Environment Configuration

Step 10 supports environment-based configuration for Keycloak and MCP server URLs. You can specify an env file (not .env) using the `--env` flag, or let it default to `keycloak_direct.env`.

Two example env files are provided:
- `keycloak_direct.env` (for direct Keycloak access at `localhost:8080`)
- `keycloak_proxy.env` (for proxy access at `localhost:9090`)

**Example usage:**

```bash
# Run step 10 with a specific env file (e.g., proxy)
uv run step10 --env keycloak_proxy.env
```

If the env file or environment variables are missing, the server will fall back to sensible defaults (localhost:8080, etc).

### Notes for running step11

* you will need to run step10 mcp server 
* you will have to allow anonymous client registration:
* add trusted hosts (check keycloak logs for the right IP)
* for trusted host policy, you don't need matching on URI
* allowable scopes for mcp:read, etc and aud mapper
* then run the step11 client

```bash
uv run step11
```

To run with mcp-inspector

* you'll need to run agentgateway with config.yaml
* uv run step10 --env keycloak_proxy.env
* run mcp-inspector UI (note, some of the auth stuff is broken, at the moment, use this: https://github.com/christian-posta/mcp-inspector/tree/ceposta-patches)
* then follow the step by step auth flow

mcp scopes issue:
https://github.com/modelcontextprotocol/inspector/issues/587

### Token Generation

For steps 5-8 that require JWT authentication, you can generate tokens using the `generate_token.py` script:

```bash
uv run python generate_token.py --username alice --scopes mcp:read,mcp:tools
uv run python generate_token.py --username bob --scopes mcp:read,mcp:prompts
uv run python generate_token.py --username admin --scopes mcp:read,mcp:tools,mcp:prompts
uv run python generate_token.py --username guest --scopes ""
```

### Keycloak Token Generation
To quickly get a token for testing step9/keycloak:

```bash# Get token for admin user (full access)
curl -X POST "http://localhost:8080/realms/mcp-realm/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=mcp-test-client" \
  -d "username=mcp-admin" \
  -d "password=admin123" \
  -d "scope=openid profile email mcp:read mcp:tools mcp:prompts" | jq -r '.access_token'

```

The script will output a JWT token that can be used in the `Authorization: Bearer <token>` header for authenticated requests.

### Running Step 12/13/14 (Per-Tool RBAC)

Steps 12 and 14 demonstrate per-tool authorization. Step 13 is basic FastMCP OAuth.

```bash
# Start Keycloak first
cd keycloak && docker compose up -d && cd ..

# Setup Keycloak realm with new scopes and users
cd keycloak && uv run python setup_keycloak.py --config config.json --url http://localhost:8080 && cd ..

# Run Step 12 (FastAPI with RBAC)
uv run step12

# Or run Step 13 (FastMCP basic OAuth - all tools for authenticated users)
uv run step13

# Or run Step 14 (FastMCP with RBAC and filtered tools/list)
uv run step14

# Test with test scripts
./test_step12.sh
uv run python test_step13.py
uv run python test_step14.py
```

Test users for per-tool RBAC:
- `mcp-admin` / `admin123` - has `mcp:tools` (all tools)
- `mcp-user` / `user123` - has `mcp:tools:echo`, `mcp:tools:time`, `mcp:tools:calc`
- `mcp-guest` / `guest123` - has only `mcp:tools:echo`
- `mcp-readonly` / `readonly123` - has only `mcp:read` (no tools)

## Dependencies

- FastAPI
- PyJWT
- cryptography
- uvicorn
- FastMCP (for step 13)

The project uses `uv` for dependency management with `pyproject.toml` configuration.
