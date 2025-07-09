#!/bin/bash

# Variables
KEYCLOAK_URL="http://localhost:8080"
REALM="mcp-realm"
REG_ENDPOINT="$KEYCLOAK_URL/realms/$REALM/clients-registrations/openid-connect"

# Registration payload
read -r -d '' PAYLOAD <<EOF
{
  "client_name": "My Anonymous Client",
  "redirect_uris": ["http://localhost:8081/callback"],
  "grant_types": ["authorization_code"],
  "scope": "mcp:read mcp:tools mcp:prompts echo-mcp-server-audience",
  "token_endpoint_auth_method": "client_secret_basic"
}
EOF

# Register the client
echo "Registering client with Keycloak (anonymous)..."
RESPONSE=$(curl -s -X POST "$REG_ENDPOINT" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

echo "Response:"
echo "$RESPONSE" | jq

# Extract client_id and client_secret
CLIENT_ID=$(echo "$RESPONSE" | jq -r '.client_id')
CLIENT_SECRET=$(echo "$RESPONSE" | jq -r '.client_secret')

echo "Client ID: $CLIENT_ID"
echo "Client Secret: $CLIENT_SECRET"