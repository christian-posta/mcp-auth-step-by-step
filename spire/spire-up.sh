#!/bin/bash
set -e

# 0. Check for required certificates (SPIRE certificates only)
echo "Checking for required certificates..."
if [[ ! -f "dummy_upstream_ca.key" || ! -f "dummy_upstream_ca.crt" || ! -f "dummy_root_ca.crt" ]]; then
  echo "Missing required certificates. Generating them..."
  ./generate_dummy_certs.sh
else
  echo "All certificates found."
fi

# 1. Check if keycloak_keycloak-shared-network exists (should be created by Keycloak)
echo "Checking for keycloak_keycloak-shared-network..."
if ! docker network ls | grep -q keycloak_keycloak-shared-network; then
  echo "ERROR: keycloak_keycloak-shared-network not found!"
  echo "Please start Keycloak first to create the shared network."
  echo "Run: cd ../keycloak && docker compose up -d"
  exit 1
else
  echo "keycloak_keycloak-shared-network found."
fi

# 2. Start the server and OIDC discovery provider (everything except agent)
echo "Starting SPIRE server and OIDC discovery provider..."
docker compose up -d spire-server spire-oidc-discovery

# 3. Wait for the server to be healthy
until docker compose exec spire-server /opt/spire/bin/spire-server healthcheck; do
  echo "Waiting for SPIRE server to be healthy..."
  sleep 2
done

echo "SPIRE server is healthy."

# 4. Wait for the OIDC discovery provider to be ready
echo "Waiting for OIDC discovery provider to be ready..."
until curl -s http://localhost:18443/keys > /dev/null 2>&1; do
  echo "Waiting for OIDC discovery provider..."
  sleep 2
done

echo "OIDC discovery provider is ready."

# 5. Generate a join token
TOKEN=$(docker compose exec spire-server /opt/spire/bin/spire-server token generate -spiffeID spiffe://example.org/agent | grep 'Token:' | awk '{print $2}')
echo "Join token: $TOKEN"

# 6. Start the agent with the join token
# Remove any existing agent container
if docker compose ps | grep -q spire-agent; then
  echo "Stopping any existing spire-agent container..."
  docker compose rm -sf spire-agent
fi

echo "Starting spire-agent with join token..."
docker compose run -d --name spire-agent spire-agent -config "/etc/spire/agent/agent.conf" -joinToken "$TOKEN"

echo "SPIRE stack is up!"
echo ""
echo "Services running:"
echo "  - SPIRE Server: localhost:18081"
echo "  - OIDC Discovery Provider: localhost:18443"
echo "  - SPIRE Agent: (internal)"
echo ""
echo "Test OIDC endpoints:"
echo "  - Discovery document: curl http://localhost:18443/.well-known/openid-configuration"
echo "  - JWKS endpoint: curl http://localhost:18443/keys" 