#!/bin/bash
set -e

# 0. Check for required dummy certificates
echo "Checking for required dummy certificates..."
if [[ ! -f "dummy_upstream_ca.key" || ! -f "dummy_upstream_ca.crt" || ! -f "dummy_root_ca.crt" ]]; then
  echo "Missing required dummy certificates. Generating them..."
  ./generate_dummy_certs.sh
else
  echo "Dummy certificates found."
fi

# 1. Start the server
if ! docker compose ps | grep -q spire-server; then
  echo "Starting spire-server..."
  docker compose up -d spire-server
else
  echo "spire-server already running."
fi

# 2. Wait for the server to be healthy
until docker compose exec spire-server /opt/spire/bin/spire-server healthcheck; do
  echo "Waiting for SPIRE server to be healthy..."
  sleep 2
done

echo "SPIRE server is healthy."

# 3. Generate a join token
TOKEN=$(docker compose exec spire-server /opt/spire/bin/spire-server token generate -spiffeID spiffe://example.org/agent | grep 'Token:' | awk '{print $2}')
echo "Join token: $TOKEN"

# 4. Start the agent with the join token
# Remove any existing agent container
if docker compose ps | grep -q spire-agent; then
  echo "Stopping any existing spire-agent container..."
  docker compose rm -sf spire-agent
fi

echo "Starting spire-agent with join token..."
docker compose run -d --name spire-agent spire-agent -config "/etc/spire/agent/agent.conf" -joinToken "$TOKEN"




echo "SPIRE stack is up!" 