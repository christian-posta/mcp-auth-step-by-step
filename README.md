# MCP Auth Step by Step

This repository demonstrates building an MCP (Model Context Protocol) server with HTTP transport and JWT authentication, progressing through iterative steps.

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

### Step 9: Enhanced MCP Integration (Planned)
- **What it will add**: User context in responses and authenticated tools
- **Planned features**:
  - User context in MCP response headers/metadata
  - Authenticated tools with user-aware behavior
  - Enhanced MCP protocol integration
  - Personalized responses based on user identity

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
1. Install `uv`: https://docs.astral.sh/uv/getting-started/installation/
2. Navigate to the `http-transport-steps` directory

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

## Dependencies

- FastAPI
- PyJWT
- cryptography
- uvicorn

The project uses `uv` for dependency management with `pyproject.toml` configuration.
