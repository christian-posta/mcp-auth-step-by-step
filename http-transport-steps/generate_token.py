#!/usr/bin/env python3
"""
External JWT Token Generator for MCP Server

This script generates JWT tokens for testing the MCP server authentication.
It should be run separately from the MCP server.

Usage:
    python generate_token.py --username alice --scopes mcp:read,mcp:tools
    python generate_token.py --username admin --scopes mcp:read,mcp:tools,mcp:prompts
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import List

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# JWT Configuration
JWT_ISSUER = "mcp-simple-auth"
JWT_AUDIENCE = "mcp-server"

def generate_key_pair():
    """Generate RSA key pair for JWT signing."""
    print("🔑 Generating new RSA key pair...")
    
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Save private key
    private_key_file = "mcp_private_key.pem"
    with open(private_key_file, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    print(f"✅ Private key saved to {private_key_file}")
    
    # Save public key
    public_key_file = "mcp_public_key.pem"
    public_key = private_key.public_key()
    with open(public_key_file, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))
    print(f"✅ Public key saved to {public_key_file}")
    
    return private_key, public_key

def load_private_key():
    """Load existing private key or generate new one."""
    private_key_file = "mcp_private_key.pem"
    
    if os.path.exists(private_key_file):
        print(f"📖 Loading existing private key from {private_key_file}")
        try:
            with open(private_key_file, "rb") as f:
                private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                )
            print("✅ Private key loaded successfully")
            return private_key
        except Exception as e:
            print(f"❌ Failed to load private key: {e}")
            return None
    else:
        print("🔑 No private key found, generating new key pair...")
        private_key, _ = generate_key_pair()
        return private_key

def generate_jwt_token(username: str, scopes: List[str], private_key, expires_in_hours: int = 1):
    """Generate a JWT token."""
    now = datetime.utcnow()
    now_timestamp = int(now.timestamp())
    exp_timestamp = int((now + timedelta(hours=expires_in_hours)).timestamp())
    
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
    
    return token, payload

def main():
    parser = argparse.ArgumentParser(description="Generate JWT tokens for MCP server")
    parser.add_argument("--username", required=True, help="Username for the token")
    parser.add_argument("--scopes", default="mcp:read,mcp:tools", 
                       help="Comma-separated list of scopes (default: mcp:read,mcp:tools)")
    parser.add_argument("--expires", type=int, default=1, 
                       help="Token expiration in hours (default: 1)")
    parser.add_argument("--generate-keys", action="store_true", 
                       help="Generate new key pair")
    parser.add_argument("--demo", action="store_true", 
                       help="Generate demo tokens for common users")
    
    args = parser.parse_args()
    
    if args.generate_keys:
        generate_key_pair()
        return
    
    if args.demo:
        print("🎭 Generating demo tokens...")
        demo_users = [
            {"username": "alice", "scopes": ["mcp:read", "mcp:tools"]},
            {"username": "bob", "scopes": ["mcp:read", "mcp:prompts"]},
            {"username": "admin", "scopes": ["mcp:read", "mcp:tools", "mcp:prompts"]},
        ]
        
        private_key = load_private_key()
        if not private_key:
            print("❌ Failed to load or generate private key")
            sys.exit(1)
        
        tokens = []
        for user in demo_users:
            token, payload = generate_jwt_token(
                user["username"], 
                user["scopes"], 
                private_key, 
                args.expires
            )
            tokens.append({
                "user": user["username"],
                "scopes": user["scopes"],
                "token": token,
                "payload": payload
            })
        
        print("\n🎭 Demo Tokens Generated:")
        print("=" * 50)
        for token_info in tokens:
            print(f"\n👤 User: {token_info['user']}")
            print(f"🔑 Scopes: {', '.join(token_info['scopes'])}")
            print(f"🎫 Token: {token_info['token']}")
            print(f"⏰ Expires: {datetime.fromtimestamp(token_info['payload']['exp']).isoformat()}")
            print("-" * 30)
        
        # Save to file
        with open("demo_tokens.json", "w") as f:
            json.dump(tokens, f, indent=2, default=str)
        print(f"\n💾 Demo tokens saved to demo_tokens.json")
        return
    
    # Generate single token
    scopes = [s.strip() for s in args.scopes.split(",")]
    
    private_key = load_private_key()
    if not private_key:
        print("❌ Failed to load or generate private key")
        sys.exit(1)
    
    token, payload = generate_jwt_token(args.username, scopes, private_key, args.expires)
    
    print(f"\n🎫 JWT Token Generated:")
    print("=" * 30)
    print(f"👤 Username: {args.username}")
    print(f"🔑 Scopes: {', '.join(scopes)}")
    print(f"⏰ Expires: {datetime.fromtimestamp(payload['exp']).isoformat()}")
    print(f"🎫 Token: {token}")
    print("=" * 30)
    
    # Save to file
    token_file = f"token_{args.username}.json"
    with open(token_file, "w") as f:
        json.dump({
            "username": args.username,
            "scopes": scopes,
            "token": token,
            "payload": payload,
            "expires_at": datetime.fromtimestamp(payload['exp']).isoformat()
        }, f, indent=2, default=str)
    print(f"💾 Token saved to {token_file}")

if __name__ == "__main__":
    main() 