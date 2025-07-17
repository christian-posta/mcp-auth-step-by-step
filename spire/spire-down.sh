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
if docker volume ls | grep -q spire_spire-server-socket; then
  echo "Removing spire-server-socket volume..."
  docker volume rm spire_spire-server-socket
fi

# 3. Note about network (owned by Keycloak)
echo ""
echo "Note: keycloak_keycloak-shared-network is owned by Keycloak and will not be removed."
echo "To remove the network, stop Keycloak first: cd ../keycloak && docker compose down"

echo ""
echo "SPIRE stack shutdown complete!"
echo ""
echo "Remaining resources:"
echo "  - Certificates: $(ls -1 *.pem *.crt *.key 2>/dev/null | wc -l | tr -d ' ') files"
echo "  - keycloak_keycloak-shared-network: $(docker network ls | grep -c keycloak_keycloak-shared-network || echo "0") instances"
echo ""
echo "To completely clean up, you can also:"
echo "  - Remove certificates: rm *.pem *.crt *.key"
echo "  - Remove network (after stopping Keycloak): cd ../keycloak && docker compose down" 