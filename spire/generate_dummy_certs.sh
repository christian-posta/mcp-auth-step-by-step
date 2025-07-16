#!/bin/bash
set -e

# Paths
KEY="dummy_upstream_ca.key"
CRT="dummy_upstream_ca.crt"
ROOTCRT="dummy_root_ca.crt"

# Check if files already exist
if [[ -f "$KEY" || -f "$CRT" || -f "$ROOTCRT" ]]; then
  echo "One or more dummy cert/key files already exist:"
  [[ -f "$KEY" ]] && echo "  $KEY"
  [[ -f "$CRT" ]] && echo "  $CRT"
  [[ -f "$ROOTCRT" ]] && echo "  $ROOTCRT"
  read -p "Overwrite existing files? [y/N]: " yn
  case $yn in
    [Yy]*) echo "Overwriting..." ;;
    *) echo "Aborting."; exit 1 ;;
  esac
fi

# Generate dummy_upstream_ca.key and dummy_upstream_ca.crt
openssl req -x509 -newkey rsa:2048 -days 365 -nodes \
  -keyout "$KEY" \
  -out "$CRT" \
  -subj "/CN=Dummy Upstream CA"

# Copy dummy_upstream_ca.crt as dummy_root_ca.crt for the agent
cp "$CRT" "$ROOTCRT"

echo "Dummy certs and key generated:"
echo "  $KEY"
echo "  $CRT"
echo "  $ROOTCRT" 