#!/usr/bin/env python3
"""
Step 9: Keycloak Setup and Configuration

This script orchestrates the complete setup of Keycloak for MCP integration:
1. Manages Docker Compose for Keycloak
2. Runs Keycloak configuration setup
3. Verifies the setup was successful
"""

import subprocess
import sys
import time
import requests
import json
import os
from pathlib import Path

# Configuration
KEYCLOAK_URL = "http://localhost:8080"
KEYCLOAK_REALM = "mcp-realm"
KEYCLOAK_CONFIG_FILE = "keycloak/config.json"
KEYCLOAK_SETUP_SCRIPT = "keycloak/setup_keycloak.py"

def log(message, level="INFO"):
    """Log messages with color coding."""
    colors = {
        'INFO': '\033[1;34mℹ️\033[0m',
        'SUCCESS': '\033[1;32m✅\033[0m',
        'WARNING': '\033[1;33m⚠️\033[0m',
        'ERROR': '\033[1;31m❌\033[0m'
    }
    color = colors.get(level, colors['INFO'])
    print(f"{color} {message}")

def run_command(command, cwd=None, check=True):
    """Run a shell command and return the result."""
    log(f"Running: {command}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=check
        )
        if result.stdout:
            log(f"Output: {result.stdout.strip()}")
        if result.stderr:
            log(f"Stderr: {result.stderr.strip()}")
        return result
    except subprocess.CalledProcessError as e:
        log(f"Command failed with exit code {e.returncode}", "ERROR")
        log(f"Error: {e.stderr}", "ERROR")
        if check:
            raise
        return e

def check_keycloak_health():
    """Check if Keycloak is healthy and responding."""
    try:
        # Try to access the master realm - this is a reliable way to check if Keycloak is running
        response = requests.get(f"{KEYCLOAK_URL}/realms/master", timeout=10)
        if response.status_code == 200:
            log("Keycloak health check passed", "SUCCESS")
            return True
        else:
            log(f"Keycloak health check failed with status {response.status_code}", "ERROR")
            return False
    except requests.exceptions.RequestException as e:
        log(f"Keycloak health check failed: {e}", "ERROR")
        return False

def wait_for_keycloak(max_attempts=30):
    """Wait for Keycloak to become available."""
    log("Waiting for Keycloak to become available...")
    
    for attempt in range(max_attempts):
        if check_keycloak_health():
            return True
        
        log(f"Attempt {attempt + 1}/{max_attempts} - Keycloak not ready yet...")
        time.sleep(2)
    
    log("Keycloak failed to become available within expected time", "ERROR")
    return False

def manage_docker_compose():
    """Manage Docker Compose for Keycloak."""
    keycloak_dir = Path("keycloak")
    
    if not keycloak_dir.exists():
        log(f"Keycloak directory not found: {keycloak_dir}", "ERROR")
        return False
    
    # Check if containers are running and stop them
    log("Checking for existing Keycloak containers...")
    result = run_command("docker compose ps", cwd=keycloak_dir, check=False)
    
    if "Up" in result.stdout:
        log("Stopping existing Keycloak containers...")
        run_command("docker compose down", cwd=keycloak_dir)
        time.sleep(2)  # Give containers time to stop
    
    # Start fresh Keycloak
    log("Starting Keycloak with Docker Compose...")
    run_command("docker compose up -d", cwd=keycloak_dir)
    
    return True

def setup_keycloak():
    """Run Keycloak setup script."""
    if not os.path.exists(KEYCLOAK_CONFIG_FILE):
        log(f"Keycloak config file not found: {KEYCLOAK_CONFIG_FILE}", "ERROR")
        return False
    
    if not os.path.exists(KEYCLOAK_SETUP_SCRIPT):
        log(f"Keycloak setup script not found: {KEYCLOAK_SETUP_SCRIPT}", "ERROR")
        return False
    
    log("Running Keycloak setup script...")
    result = run_command(
        f"uv run python {KEYCLOAK_SETUP_SCRIPT} --config {KEYCLOAK_CONFIG_FILE} --url {KEYCLOAK_URL} --summary",
        check=False
    )
    
    if result.returncode == 0:
        log("Keycloak setup completed successfully", "SUCCESS")
        return True
    else:
        log("Keycloak setup failed", "ERROR")
        return False

def verify_setup():
    """Verify that Keycloak setup was successful."""
    log("Verifying Keycloak setup...")
    
    # Test realm exists
    try:
        response = requests.get(f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}")
        if response.status_code == 200:
            log(f"Realm '{KEYCLOAK_REALM}' exists", "SUCCESS")
        else:
            log(f"Realm '{KEYCLOAK_REALM}' not found", "ERROR")
            return False
    except requests.exceptions.RequestException as e:
        log(f"Failed to verify realm: {e}", "ERROR")
        return False
    
    # Test OAuth authorization server metadata
    try:
        response = requests.get(f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/.well-known/oauth-authorization-server")
        if response.status_code == 200:
            metadata = response.json()
            if "issuer" in metadata:
                log("OAuth authorization server metadata available", "SUCCESS")
            else:
                log("OAuth authorization server metadata missing issuer", "ERROR")
                return False
        else:
            log("OAuth authorization server metadata not available", "ERROR")
            return False
    except requests.exceptions.RequestException as e:
        log(f"Failed to verify OAuth metadata: {e}", "ERROR")
        return False
    
    log("Keycloak setup verification completed", "SUCCESS")
    return True

def main():
    """Main function."""
    log("=== Step 9: Keycloak Setup and Configuration ===")
    
    try:
        # Step 1: Manage Docker Compose
        if not manage_docker_compose():
            log("Failed to manage Docker Compose", "ERROR")
            sys.exit(1)
        
        # Step 2: Wait for Keycloak to be ready
        if not wait_for_keycloak():
            log("Keycloak failed to start", "ERROR")
            sys.exit(1)
        
        # Step 3: Setup Keycloak configuration
        if not setup_keycloak():
            log("Failed to setup Keycloak configuration", "ERROR")
            sys.exit(1)
        
        # Step 4: Verify setup
        if not verify_setup():
            log("Keycloak setup verification failed", "ERROR")
            sys.exit(1)
        
        log("=== Step 9 completed successfully! ===", "SUCCESS")
        log("Keycloak is ready for MCP integration")
        log(f"Keycloak URL: {KEYCLOAK_URL}")
        log(f"Realm: {KEYCLOAK_REALM}")
        log("Run test_step9.sh to verify token acquisition and JWT validation")
        
    except Exception as e:
        log(f"Unexpected error: {e}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main() 