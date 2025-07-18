#!/bin/bash
set -e

echo "=== Restarting Keycloak with SPIRE SVID Client Authenticator ==="

# Stop existing containers
echo "Stopping existing Keycloak container..."
docker compose down

# Verify JAR file exists
if [ ! -f "spiffe-svid-client-authenticator-1.0.0.jar" ]; then
    echo "❌ Error: spiffe-svid-client-authenticator-1.0.0.jar not found in current directory"
    exit 1
fi

echo "✅ JAR file found: spiffe-svid-client-authenticator-1.0.0.jar"

# Start Keycloak with the authenticator
echo "Starting Keycloak with custom authenticator..."
docker compose up -d

# Wait for Keycloak to start
echo "Waiting for Keycloak to start..."
sleep 10

# Check if Keycloak is running
if ! docker compose ps | grep -q "Up"; then
    echo "❌ Keycloak failed to start"
    docker compose logs
    exit 1
fi

echo "✅ Keycloak is running"

# Verify the JAR is mounted correctly
echo "Verifying JAR file is mounted in container..."
if docker compose exec keycloak-idp ls -la /opt/keycloak/providers/spiffe-svid-client-authenticator-1.0.0.jar; then
    echo "✅ JAR file is mounted correctly"
else
    echo "❌ JAR file is not mounted correctly"
    exit 1
fi

# Check Keycloak logs for authenticator loading
echo "Checking Keycloak logs for authenticator loading..."
sleep 5
docker compose logs keycloak-idp | grep -i "spiffe\|authenticator" || echo "No SPIRE/authenticator messages in logs yet"

echo
echo "=== Keycloak is ready with custom authenticator ==="
echo "You can now:"
echo "1. Access Keycloak admin console at http://localhost:8080"
echo "2. Login with admin/admin"
echo "3. Go to Clients > [Your Client] > Settings > Client authentication"
echo "4. Look for 'spiffe-svid' in the Client authenticator dropdown"
echo
echo "To check logs: docker compose logs -f keycloak-idp" 