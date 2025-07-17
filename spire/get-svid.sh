#!/bin/bash
set -e

WORKLOAD_SPIFFE_ID="spiffe://example.org/workload"
PARENT_SPIFFE_ID="spiffe://example.org/agent"
AUDIENCE="example-audience"

prompt_continue() {
  read -r -p "Continue (Y/n)? " response
  response=${response:-Y}
  if [[ "$response" =~ ^[Nn]$ ]]; then
    echo "Aborting."
    exit 1
  fi
}

# 1. Check if workload entry exists
if docker compose exec spire-server /opt/spire/bin/spire-server entry show -spiffeID "$WORKLOAD_SPIFFE_ID" | grep -q "Entry ID"; then
  echo "Workload entry already exists."
else
  echo "Registering workload entry..."
  docker compose exec spire-server /opt/spire/bin/spire-server entry create \
    -parentID "$PARENT_SPIFFE_ID" \
    -spiffeID "$WORKLOAD_SPIFFE_ID" \
    -selector unix:uid:0
fi
prompt_continue

# 2. Fetch JWT SVID using spire-agent CLI
JWT_OUTPUT=$(docker compose exec spire-agent /opt/spire/bin/spire-agent api fetch jwt \
  --audience "$AUDIENCE" \
  --socketPath /opt/spire/sockets/workload_api.sock)

echo "$JWT_OUTPUT"
prompt_continue

# 3. Extract and decode JWT SVID
JWT=$(echo "$JWT_OUTPUT" | awk '/^token\(/ {getline; gsub(/^[[:space:]]+/, ""); gsub(/[[:space:]]+$/, ""); print $0}')

decode_jwt() {
  jwt="$1"
  header=$(echo "$jwt" | cut -d. -f1 | tr '_-' '/+' | awk '{ l=length($0)%4; if(l>0) { printf "%s", $0; for(i=1;i<=4-l;i++) printf "="; print "" } else print $0 }' | base64 -d 2>/dev/null | jq .)
  payload=$(echo "$jwt" | cut -d. -f2 | tr '_-' '/+' | awk '{ l=length($0)%4; if(l>0) { printf "%s", $0; for(i=1;i<=4-l;i++) printf "="; print "" } else print $0 }' | base64 -d 2>/dev/null | jq .)
  echo "Header:"
  echo "$header"
  echo "Claims:"
  echo "$payload"
}

echo "JWT: $JWT"
if [ -n "$JWT" ]; then
  echo
  echo "Decoded JWT SVID:"
  decode_jwt "$JWT"
  
  # Extract and display expiration time
  EXP=$(echo "$JWT" | cut -d. -f2 | tr '_-' '/+' | awk '{ l=length($0)%4; if(l>0) { printf "%s", $0; for(i=1;i<=4-l;i++) printf "="; print "" } else print $0 }' | base64 -d 2>/dev/null | jq -r '.exp')
  if [ -n "$EXP" ] && [ "$EXP" != "null" ]; then
    EXP_DATE=$(date -r "$EXP" 2>/dev/null || date -d "@$EXP" 2>/dev/null)
    echo
    echo "Expires: $EXP_DATE (Unix timestamp: $EXP)"
  fi
fi 