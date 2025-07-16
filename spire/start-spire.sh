#!/bin/bash
set -e

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