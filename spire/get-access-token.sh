#!/bin/bash
set -e

# Configuration
WORKLOAD_SPIFFE_ID="spiffe://example.org/mcp-test-client"
PARENT_SPIFFE_ID="spiffe://example.org/agent"
AUDIENCE="http://localhost:8080/realms/mcp-realm"
KEYCLOAK_URL="http://localhost:8080"
KEYCLOAK_REALM="mcp-realm"
CLIENT_ID="spiffe://example.org/mcp-test-client"

prompt_continue() {
  read -r -p "Continue (Y/n)? " response
  response=${response:-Y}
  if [[ "$response" =~ ^[Nn]$ ]]; then
    echo "Aborting."
    exit 1
  fi
}

echo "=== SPIRE + Keycloak JWT Client Credentials Flow ==="
echo "Workload SPIFFE ID: $WORKLOAD_SPIFFE_ID"
echo "Audience: $AUDIENCE"
echo "Keycloak URL: $KEYCLOAK_URL"
echo "Keycloak Realm: $KEYCLOAK_REALM"
echo "Client ID: $CLIENT_ID"
echo

# 1. Check if workload entry exists and register if needed
echo "Step 1: Checking/Registering SPIRE workload entry..."
if docker compose exec spire-server /opt/spire/bin/spire-server entry show -spiffeID "$WORKLOAD_SPIFFE_ID" | grep -q "Entry ID"; then
  echo "✅ Workload entry already exists."
else
  echo "📝 Registering workload entry..."
  docker compose exec spire-server /opt/spire/bin/spire-server entry create \
    -parentID "$PARENT_SPIFFE_ID" \
    -spiffeID "$WORKLOAD_SPIFFE_ID" \
    -jwtSVIDTTL 60 \
    -selector unix:uid:0
  echo "✅ Workload entry created."
fi
prompt_continue

# 2. Fetch JWT SVID using spire-agent CLI with retry logic
echo
echo "Step 2: Fetching JWT SVID from SPIRE..."

# Retry configuration
MAX_ATTEMPTS=10
ATTEMPT=1
BACKOFF_DELAY=2

JWT_OUTPUT=""
while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
  echo "Attempt $ATTEMPT/$MAX_ATTEMPTS: Fetching JWT SVID..."
  
  JWT_OUTPUT=$(docker compose exec spire-agent /opt/spire/bin/spire-agent api fetch jwt \
    --audience "$AUDIENCE" \
    --spiffeID "$WORKLOAD_SPIFFE_ID" \
    --socketPath /opt/spire/sockets/workload_api.sock 2>&1)
  
  # Check if the command was successful and JWT was returned
  if [ $? -eq 0 ] && echo "$JWT_OUTPUT" | grep -q "token("; then
    echo "✅ Successfully fetched JWT SVID on attempt $ATTEMPT"
    break
  else
    echo "⚠️  Attempt $ATTEMPT failed. JWT SVID not yet available."
    echo "Output: $JWT_OUTPUT"
    
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
      echo "❌ Failed to fetch JWT SVID after $MAX_ATTEMPTS attempts"
      echo "This may indicate:"
      echo "  1. The workload entry hasn't synced to the agent yet"
      echo "  2. The SPIRE agent is not running or accessible"
      echo "  3. The workload selector doesn't match (unix:uid:0)"
      echo "  4. Network connectivity issues"
      exit 1
    fi
    
    echo "⏳ Waiting ${BACKOFF_DELAY} seconds before next attempt..."
    sleep $BACKOFF_DELAY
    
    # Exponential backoff (double the delay, max 30 seconds)
    BACKOFF_DELAY=$((BACKOFF_DELAY * 2))
    if [ $BACKOFF_DELAY -gt 30 ]; then
      BACKOFF_DELAY=30
    fi
    
    ATTEMPT=$((ATTEMPT + 1))
  fi
done

echo "SPIRE JWT Output:"
echo "$JWT_OUTPUT"
prompt_continue

# 3. Extract JWT token
echo
echo "Step 3: Extracting JWT token..."
JWT=$(echo "$JWT_OUTPUT" | awk '/^token\(/ {getline; gsub(/^[[:space:]]+/, ""); gsub(/[[:space:]]+$/, ""); print $0}')

if [ -z "$JWT" ]; then
  echo "❌ Failed to extract JWT token from SPIRE output"
  exit 1
fi

echo "✅ JWT token extracted (length: ${#JWT} characters)"
echo "JWT starts with: ${JWT:0:50}..."

# 4. Decode and display JWT for verification
decode_jwt() {
  jwt="$1"
  header=$(echo "$jwt" | cut -d. -f1 | tr '_-' '/+' | awk '{ l=length($0)%4; if(l>0) { printf "%s", $0; for(i=1;i<=4-l;i++) printf "="; print "" } else print $0 }' | base64 -d 2>/dev/null | jq .)
  payload=$(echo "$jwt" | cut -d. -f2 | tr '_-' '/+' | awk '{ l=length($0)%4; if(l>0) { printf "%s", $0; for(i=1;i<=4-l;i++) printf "="; print "" } else print $0 }' | base64 -d 2>/dev/null | jq .)
  echo "Header:"
  echo "$header"
  echo "Claims:"
  echo "$payload"
}

echo
echo "Decoded SPIRE JWT:"
decode_jwt "$JWT"
prompt_continue

# 5. Make Keycloak client credentials request with JWT assertion
echo
echo "Step 4: Requesting Keycloak access token using JWT client assertion..."
echo "Keycloak Token Endpoint: $KEYCLOAK_URL/realms/$KEYCLOAK_REALM/protocol/openid-connect/token"

# URL encode the JWT for the request
ENCODED_JWT=$(echo "$JWT" | sed 's/+/%2B/g' | sed 's/\//%2F/g' | sed 's/=/%3D/g')

KEYCLOAK_RESPONSE=$(curl -s -X POST \
  "$KEYCLOAK_URL/realms/$KEYCLOAK_REALM/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=$CLIENT_ID" \
  -d "grant_type=client_credentials" \
  -d "client_assertion_type=urn:ietf:params:oauth:client-assertion-type:spiffe-svid-jwt" \
  -d "client_assertion=$JWT" \
  -d "scope=mcp:read mcp:tools mcp:prompts")

echo "Keycloak Response Status: $?"
echo "Keycloak Response:"
echo "$KEYCLOAK_RESPONSE" | jq . 2>/dev/null || echo "$KEYCLOAK_RESPONSE"

# 6. Extract and display access token if successful
if echo "$KEYCLOAK_RESPONSE" | grep -q "access_token"; then
  echo
  echo "✅ SUCCESS: Keycloak access token obtained!"
  
  ACCESS_TOKEN=$(echo "$KEYCLOAK_RESPONSE" | jq -r '.access_token // empty')
  TOKEN_TYPE=$(echo "$KEYCLOAK_RESPONSE" | jq -r '.token_type // empty')
  EXPIRES_IN=$(echo "$KEYCLOAK_RESPONSE" | jq -r '.expires_in // empty')
  
  echo "Token Type: $TOKEN_TYPE"
  echo "Expires In: $EXPIRES_IN seconds"
  echo "Access Token: $ACCESS_TOKEN"
  
  # Decode the Keycloak access token
  echo
  echo "Decoded Keycloak Access Token:"
  decode_jwt "$ACCESS_TOKEN"
  
  # Save token to file for easy use
  echo "$ACCESS_TOKEN" > keycloak_access_token.txt
  echo
  echo "💾 Access token saved to: keycloak_access_token.txt"
  echo "You can use it with: export ACCESS_TOKEN=\$(cat keycloak_access_token.txt)"
  
else
  echo
  echo "❌ FAILED: Could not obtain Keycloak access token"
  echo "Check that:"
  echo "1. Keycloak is running at $KEYCLOAK_URL"
  echo "2. Realm '$KEYCLOAK_REALM' exists"
  echo "3. Client '$CLIENT_ID' exists and is configured for JWT client authentication"
  echo "4. The SPIRE JWT audience matches what Keycloak expects"
fi

echo
echo "=== Script completed ===" 