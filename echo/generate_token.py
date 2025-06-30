#!/usr/bin/env python3
"""
Standalone JWT token generator for MCP testing.
This script generates tokens using the same logic as the JWT server.
"""

import json
import sys
from datetime import datetime, timedelta
from typing import List, Optional

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import BaseModel

# Constants (same as jwt_server.py)
JWT_ISSUER = "mcp-simple-auth"
JWT_AUDIENCE = "mcp-server"

class TokenRequest(BaseModel):
    username: str
    scopes: Optional[List[str]] = ["mcp:read", "mcp:tools", "mcp:prompts"]

def generate_keys():
    """Load existing RSA key pair for JWT signing."""
    import os
    
    key_file = "mcp_private_key.pem"
    
    if os.path.exists(key_file):
        print(f"🔑 Loading existing RSA key pair from {key_file}...")
        try:
            with open(key_file, "rb") as f:
                private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                )
            print("✅ RSA key pair loaded successfully")
        except Exception as e:
            print(f"❌ Failed to load key file: {e}")
            print("Please ensure the JWT server has been run at least once to generate the key file.")
            sys.exit(1)
    else:
        print(f"❌ Key file {key_file} not found!")
        print("Please run the JWT server first to generate the key file:")
        print("  python src/mcp_server_echo/jwt_server.py")
        sys.exit(1)
    
    # Get public key
    public_key = private_key.public_key()
    
    return private_key, public_key

def generate_token(username: str, scopes: List[str] = None, private_key=None):
    """Generate a JWT token for the specified user."""
    if scopes is None:
        scopes = ["mcp:read", "mcp:tools", "mcp:prompts"]
    
    if private_key is None:
        private_key, _ = generate_keys()
    
    now = datetime.utcnow()
    now_timestamp = int(now.timestamp())
    exp_timestamp = int((now + timedelta(hours=1)).timestamp())
    
    print(f"🕐 Current time: {now} (timestamp: {now_timestamp})")
    print(f"⏰ Token will expire: {now + timedelta(hours=1)} (timestamp: {exp_timestamp})")
    
    payload = {
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "sub": f"user_{username}",
        "iat": now_timestamp,
        "exp": exp_timestamp,
        "preferred_username": username,
        "scope": " ".join(scopes),
        "scopes": scopes,
        "roles": ["user"],  # Default role
    }
    
    # Add admin role for specific users
    if username.lower() in ["admin", "administrator"]:
        payload["roles"] = ["user", "admin"]
    
    # Sign the token
    token = jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": "mcp-key-1"}
    )
    
    print(f"✅ Token generated for {username}")
    print(f"📋 Token payload: {json.dumps(payload, indent=2)}")
    
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": " ".join(scopes),
        "user": username,
        "debug": {
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
            "current_timestamp": now_timestamp,
            "payload": payload
        }
    }

def generate_demo_tokens():
    """Generate demo tokens for all test users."""
    print("🎫 Generating demo tokens...")
    
    # Load existing key
    private_key, _ = generate_keys()
    
    demo_users = [
        {"username": "alice", "scopes": ["mcp:read", "mcp:tools"]},
        {"username": "bob", "scopes": ["mcp:read", "mcp:prompts"]},
        {"username": "admin", "scopes": ["mcp:read", "mcp:tools", "mcp:prompts"]},
    ]
    
    tokens = []
    for user in demo_users:
        token_data = generate_token(user["username"], user["scopes"], private_key)
        tokens.append({
            "user": user["username"],
            "scopes": user["scopes"],
            "token": token_data["access_token"]
        })
        print("-" * 50)
    
    return tokens

def main():
    """Main function."""
    print("🔑 JWT Token Generator for MCP Testing")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        # Generate token for specific user
        username = sys.argv[1]
        scopes = sys.argv[2:] if len(sys.argv) > 2 else None
        
        if scopes is None:
            scopes = ["mcp:read", "mcp:tools", "mcp:prompts"]
        
        print(f"👤 Generating token for user: {username}")
        print(f"🔐 Scopes: {', '.join(scopes)}")
        print()
        
        # Load existing key
        private_key, _ = generate_keys()
        token_data = generate_token(username, scopes, private_key)
        
        print("\n" + "=" * 50)
        print("🎯 GENERATED TOKEN:")
        print("=" * 50)
        print(f"Authorization: Bearer {token_data['access_token']}")
        print()
        print("📋 Token Details:")
        print(f"User: {token_data['user']}")
        print(f"Scopes: {token_data['scope']}")
        print(f"Expires in: {token_data['expires_in']} seconds")
        print(f"Token type: {token_data['token_type']}")
        
    else:
        # Generate demo tokens
        tokens = generate_demo_tokens()
        
        print("\n" + "=" * 50)
        print("🎯 DEMO TOKENS:")
        print("=" * 50)
        
        for i, token_info in enumerate(tokens, 1):
            print(f"\n{i}. User: {token_info['user']}")
            print(f"   Scopes: {', '.join(token_info['scopes'])}")
            print(f"   Authorization: Bearer {token_info['token']}")
        
        print("\n" + "=" * 50)
        print("💡 Usage Examples:")
        print("=" * 50)
        print("# Test with curl:")
        print("curl -H 'Authorization: Bearer <TOKEN>' http://localhost:9000/mcp")
        print()
        print("# Test with Python requests:")
        print("import requests")
        print("headers = {'Authorization': 'Bearer <TOKEN>'}")
        print("response = requests.post('http://localhost:9000/mcp', headers=headers, json={...})")

if __name__ == "__main__":
    main() 