#!/bin/bash
set -e

echo "Shutting down SPIRE stack..."

# 1. Stop and remove SPIRE containers
echo "Stopping and removing SPIRE containers..."

# Handle spire-agent (may be started with docker compose run)
if docker ps -a | grep -q spire-agent; then
  echo "Stopping spire-agent..."
  docker stop spire-agent 2>/dev/null || true
  docker rm spire-agent 2>/dev/null || true
fi

# Handle compose-managed containers
if docker compose ps | grep -q spire-agent; then
  echo "Stopping compose-managed spire-agent..."
  docker compose rm -sf spire-agent
fi

if docker compose ps | grep -q spire-oidc-discovery; then
  echo "Stopping spire-oidc-discovery..."
  docker compose rm -sf spire-oidc-discovery
fi

if docker compose ps | grep -q spire-server; then
  echo "Stopping spire-server..."
  docker compose rm -sf spire-server
fi

# 2. Remove SPIRE volumes
echo "Removing SPIRE volumes..."
if docker volume ls | grep -q spire-server-socket; then
  echo "Removing spire-server-socket volume..."
  docker volume rm spire-server-socket
fi

# 3. Check if spire-network is still in use by other containers
echo "Checking spire-network usage..."
NETWORK_USERS=$(docker network inspect spire-network 2>/dev/null | jq -r '.[0].Containers | keys | length' 2>/dev/null || echo "0")

if [[ "$NETWORK_USERS" -gt 0 ]]; then
  echo "spire-network is still being used by $NETWORK_USERS container(s)."
  echo "Checking which containers are using the network..."
  
  # List containers using the network
  docker network inspect spire-network 2>/dev/null | jq -r '.[0].Containers | to_entries[] | "  - \(.value.Name) (\(.key))"' 2>/dev/null || echo "  Unable to list containers"
  
  echo "Keeping spire-network as it's still in use."
else
  echo "spire-network is not being used by any containers."
  echo "Removing spire-network..."
  docker network rm spire-network 2>/dev/null || echo "Network already removed or doesn't exist."
fi

echo ""
echo "SPIRE stack shutdown complete!"
echo ""
echo "Remaining resources:"
echo "  - Certificates: $(ls -1 *.pem *.crt *.key 2>/dev/null | wc -l | tr -d ' ') files"
echo "  - spire-network: $(docker network ls | grep -c spire-network || echo "0") instances"
echo ""
echo "To completely clean up, you can also:"
echo "  - Remove certificates: rm *.pem *.crt *.key"
echo "  - Remove network (if not in use): docker network rm spire-network" 