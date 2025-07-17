#!/bin/bash
set -e

# Paths
KEY="dummy_upstream_ca.key"
CRT="dummy_upstream_ca.crt"
ROOTCRT="dummy_root_ca.crt"

# New OIDC HTTPS certificate paths
OIDC_KEY="oidc-https-key.pem"
OIDC_CSR="oidc-https.csr"
OIDC_CRT="oidc-https-cert.pem"

# Check if files already exist
if [[ -f "$KEY" || -f "$CRT" || -f "$ROOTCRT" || -f "$OIDC_KEY" || -f "$OIDC_CRT" ]]; then
  echo "One or more cert/key files already exist:"
  [[ -f "$KEY" ]] && echo "  $KEY"
  [[ -f "$CRT" ]] && echo "  $CRT"
  [[ -f "$ROOTCRT" ]] && echo "  $ROOTCRT"
  [[ -f "$OIDC_KEY" ]] && echo "  $OIDC_KEY"
  [[ -f "$OIDC_CRT" ]] && echo "  $OIDC_CRT"
  read -p "Overwrite existing files? [y/N]: " yn
  case $yn in
    [Yy]*) echo "Overwriting..." ;;
    *) echo "Aborting."; exit 1 ;;
  esac
fi

echo "Generating SPIRE CA certificates..."
# Generate dummy_upstream_ca.key and dummy_upstream_ca.crt
openssl req -x509 -newkey rsa:2048 -days 365 -nodes \
  -keyout "$KEY" \
  -out "$CRT" \
  -subj "/CN=Dummy Upstream CA"

# Copy dummy_upstream_ca.crt as dummy_root_ca.crt for the agent
cp "$CRT" "$ROOTCRT"

echo "Generating OIDC HTTPS certificates..."
# Generate OIDC HTTPS certificate request
openssl req -newkey rsa:2048 -keyout "$OIDC_KEY" -out "$OIDC_CSR" -nodes \
  -subj "/CN=spire-server" \
  -addext "subjectAltName=DNS:spire-server,DNS:spire-oidc-discovery,DNS:localhost,IP:127.0.0.1"

# Sign OIDC HTTPS certificate with SPIRE CA
openssl x509 -req -in "$OIDC_CSR" -CA "$CRT" -CAkey "$KEY" \
  -CAcreateserial -out "$OIDC_CRT" -days 365

# Clean up CSR file
rm "$OIDC_CSR"

echo "All certificates generated:"
echo "  $KEY (SPIRE CA private key)"
echo "  $CRT (SPIRE CA certificate)"
echo "  $ROOTCRT (SPIRE root CA for agent)"
echo "  $OIDC_KEY (OIDC HTTPS private key)"
echo "  $OIDC_CRT (OIDC HTTPS certificate)"
echo ""
echo "Certificate hierarchy:"
echo "  SPIRE CA ($CRT) signs:"
echo "    ├── JWT-SVIDs (existing SPIRE functionality)"
echo "    └── OIDC HTTPS certificate ($OIDC_CRT)" 