#!/usr/bin/env python3
"""
Boot Keycloak: Complete Keycloak Setup and Configuration

This script combines Docker management and Keycloak configuration into a single
streamlined process. It will:
1. Start Keycloak using Docker Compose
2. Wait for Keycloak to be ready
3. Configure Keycloak using the provided config file
4. Verify the setup was successful

Usage:
    python boot_keycloak.py [--config CONFIG_FILE] [--url KEYCLOAK_URL] [--summary] [--verbose]
"""

import subprocess
import sys
import time
import requests
import json
import os
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, List

# Configuration
DEFAULT_KEYCLOAK_URL = "http://localhost:8080"
DEFAULT_CONFIG_FILE = "config.json"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"

class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[1;37m'
    NC = '\033[0m'  # No Color

def log(message: str, level: str = "INFO", verbose: bool = False):
    """Log messages with color coding."""
    colors = {
        'INFO': f'{Colors.BLUE}ℹ️{Colors.NC}',
        'SUCCESS': f'{Colors.GREEN}✅{Colors.NC}',
        'WARNING': f'{Colors.YELLOW}⚠️{Colors.NC}',
        'ERROR': f'{Colors.RED}❌{Colors.NC}',
        'VERBOSE': f'{Colors.CYAN}🔍{Colors.NC}'
    }
    
    if level == "VERBOSE" and not verbose:
        return
    
    color = colors.get(level, colors['INFO'])
    print(f"{color} {message}")

def run_command(command: str, cwd: Optional[Path] = None, check: bool = True, verbose: bool = False) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    log(f"Running: {command}", verbose=verbose)
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=check
        )
        if result.stdout and verbose:
            log(f"Output: {result.stdout.strip()}", "VERBOSE")
        if result.stderr and verbose:
            log(f"Stderr: {result.stderr.strip()}", "VERBOSE")
        return result
    except subprocess.CalledProcessError as e:
        log(f"Command failed with exit code {e.returncode}", "ERROR")
        if e.stderr:
            log(f"Error: {e.stderr}", "ERROR")
        if check:
            raise
        return e

def check_keycloak_health(keycloak_url: str) -> bool:
    """Check if Keycloak is healthy and responding."""
    try:
        # Try to access the master realm - this is a reliable way to check if Keycloak is running
        response = requests.get(f"{keycloak_url}/realms/master", timeout=10)
        if response.status_code == 200:
            log("Keycloak health check passed", "SUCCESS")
            return True
        else:
            log(f"Keycloak health check failed with status {response.status_code}", "ERROR")
            return False
    except requests.exceptions.RequestException as e:
        log(f"Keycloak health check failed: {e}", "ERROR")
        return False

def wait_for_keycloak(keycloak_url: str, max_attempts: int = 30) -> bool:
    """Wait for Keycloak to become available."""
    log("Waiting for Keycloak to become available...")
    
    for attempt in range(max_attempts):
        if check_keycloak_health(keycloak_url):
            return True
        
        log(f"Attempt {attempt + 1}/{max_attempts} - Keycloak not ready yet...")
        time.sleep(2)
    
    log("Keycloak failed to become available within expected time", "ERROR")
    return False

def manage_docker_compose(verbose: bool = False) -> bool:
    """Manage Docker Compose for Keycloak."""
    keycloak_dir = Path(".")
    
    # Check if containers are running and stop them
    log("Checking for existing Keycloak containers...")
    result = run_command("docker compose ps", cwd=keycloak_dir, check=False, verbose=verbose)
    
    if "Up" in result.stdout:
        log("Stopping existing Keycloak containers...")
        run_command("docker compose down", cwd=keycloak_dir, verbose=verbose)
        time.sleep(2)  # Give containers time to stop
    
    # Start fresh Keycloak
    log("Starting Keycloak with Docker Compose...")
    result = run_command("docker compose up -d", cwd=keycloak_dir, verbose=verbose)
    
    if result.returncode != 0:
        log("Failed to start Keycloak containers", "ERROR")
        return False
    
    return True

class KeycloakSetup:
    """Handles Keycloak configuration and setup."""
    
    def __init__(self, keycloak_url: str, admin_username: str = "admin", admin_password: str = "admin"):
        self.keycloak_url = keycloak_url.rstrip('/')
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.admin_token = None
        self.admin_base_url = None
        
    def log(self, level: str, message: str):
        """Log messages with appropriate color coding."""
        log(message, level)
    
    def get_admin_token(self) -> bool:
        """Get admin access token from Keycloak."""
        try:
            token_url = f"{self.keycloak_url}/realms/master/protocol/openid-connect/token"
            data = {
                'username': self.admin_username,
                'password': self.admin_password,
                'grant_type': 'password',
                'client_id': 'admin-cli'
            }
            
            response = requests.post(token_url, data=data, timeout=10)
            if response.status_code == 200:
                token_data = response.json()
                self.admin_token = token_data['access_token']
                self.log('SUCCESS', f"Admin token obtained successfully")
                return True
            else:
                self.log('ERROR', f"Failed to get admin token: {response.status_code}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Error getting admin token: {e}")
            return False
    
    def detect_admin_base_url(self) -> bool:
        """Detect the correct admin base URL for Keycloak version."""
        try:
            # Try Keycloak 17+ admin API
            admin_url = f"{self.keycloak_url}/admin"
            response = requests.get(admin_url, timeout=5)
            if response.status_code == 200:
                self.admin_base_url = f"{self.keycloak_url}/admin"
                self.log('SUCCESS', f"Using admin API: {self.admin_base_url}")
                return True
            
            # Try legacy admin API
            admin_url = f"{self.keycloak_url}/auth/admin"
            response = requests.get(admin_url, timeout=5)
            if response.status_code == 200:
                self.admin_base_url = f"{self.keycloak_url}/auth/admin"
                self.log('SUCCESS', f"Using legacy admin API: {self.admin_base_url}")
                return True
                
            self.log('ERROR', "Could not detect admin API endpoint")
            return False
            
        except Exception as e:
            self.log('ERROR', f"Error detecting admin API: {e}")
            return False
    
    def create_realm(self, realm_config: Dict[str, Any]) -> bool:
        """Create a new realm in Keycloak."""
        try:
            realm_name = realm_config['realm']
            self.log('INFO', f"Creating realm: {realm_name}")
            
            url = f"{self.admin_base_url}/realms"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, headers=headers, json=realm_config, timeout=10)
            if response.status_code in [201, 409]:  # 409 means realm already exists
                self.log('SUCCESS', f"Realm '{realm_name}' created/exists")
                return True
            else:
                self.log('ERROR', f"Failed to create realm: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Error creating realm: {e}")
            return False
    
    def update_realm_attributes(self, realm_name: str, realm_config: Dict[str, Any]) -> bool:
        """Update realm attributes."""
        try:
            self.log('INFO', f"Updating realm attributes for: {realm_name}")
            
            url = f"{self.admin_base_url}/realms/{realm_name}"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.put(url, headers=headers, json=realm_config, timeout=10)
            if response.status_code == 204:
                self.log('SUCCESS', f"Realm '{realm_name}' attributes updated")
                return True
            else:
                self.log('ERROR', f"Failed to update realm attributes: {response.status_code}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Error updating realm attributes: {e}")
            return False
    
    def create_client_scope(self, realm_name: str, scope_config: Dict[str, Any]) -> bool:
        """Create a client scope in Keycloak."""
        try:
            scope_name = scope_config['name']
            self.log('INFO', f"Creating client scope: {scope_name}")
            
            url = f"{self.admin_base_url}/realms/{realm_name}/client-scopes"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, headers=headers, json=scope_config, timeout=10)
            if response.status_code in [201, 409]:  # 409 means scope already exists
                self.log('SUCCESS', f"Client scope '{scope_name}' created/exists")
                return True
            else:
                self.log('ERROR', f"Failed to create client scope: {response.status_code}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Error creating client scope: {e}")
            return False
    
    def get_client_scope_id(self, realm_name: str, scope_name: str) -> Optional[str]:
        """Get the ID of a client scope by name."""
        try:
            url = f"{self.admin_base_url}/realms/{realm_name}/client-scopes"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                scopes = response.json()
                for scope in scopes:
                    if scope['name'] == scope_name:
                        return scope['id']
            
            return None
            
        except Exception as e:
            self.log('ERROR', f"Error getting client scope ID: {e}")
            return None
    
    def add_scope_mapper(self, realm_name: str, scope_id: str, mapper_config: Dict[str, Any]) -> bool:
        """Add a mapper to a client scope."""
        try:
            mapper_name = mapper_config['name']
            self.log('INFO', f"Adding mapper '{mapper_name}' to scope")
            
            url = f"{self.admin_base_url}/realms/{realm_name}/client-scopes/{scope_id}/protocol-mappers/models"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, headers=headers, json=mapper_config, timeout=10)
            if response.status_code in [201, 409]:  # 409 means mapper already exists
                self.log('SUCCESS', f"Mapper '{mapper_name}' added to scope")
                return True
            else:
                self.log('ERROR', f"Failed to add mapper: {response.status_code}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Error adding mapper: {e}")
            return False
    
    def create_client(self, realm_name: str, client_config: Dict[str, Any]) -> bool:
        """Create a client in Keycloak."""
        try:
            client_id = client_config['clientId']
            self.log('INFO', f"Creating client: {client_id}")
            
            url = f"{self.admin_base_url}/realms/{realm_name}/clients"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, headers=headers, json=client_config, timeout=10)
            if response.status_code in [201, 409]:  # 409 means client already exists
                self.log('SUCCESS', f"Client '{client_id}' created/exists")
                return True
            else:
                self.log('ERROR', f"Failed to create client: {response.status_code}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Error creating client: {e}")
            return False
    
    def update_client_token_exchange(self, realm_name: str, client_uuid: str, client_config: Dict[str, Any]) -> bool:
        """Update client token exchange settings."""
        try:
            self.log('INFO', f"Updating client token exchange settings")
            
            url = f"{self.admin_base_url}/realms/{realm_name}/clients/{client_uuid}"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.put(url, headers=headers, json=client_config, timeout=10)
            if response.status_code == 204:
                self.log('SUCCESS', "Client token exchange settings updated")
                return True
            else:
                self.log('ERROR', f"Failed to update client: {response.status_code}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Error updating client: {e}")
            return False
    
    def get_client_uuid(self, realm_name: str, client_id: str) -> Optional[str]:
        """Get the UUID of a client by client ID."""
        try:
            url = f"{self.admin_base_url}/realms/{realm_name}/clients?clientId={client_id}"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                clients = response.json()
                if clients:
                    return clients[0]['id']
            
            return None
            
        except Exception as e:
            self.log('ERROR', f"Error getting client UUID: {e}")
            return None
    
    def create_client_role(self, realm_name: str, client_id: str, role_config: Dict[str, Any]) -> bool:
        """Create a role for a client."""
        try:
            role_name = role_config['name']
            self.log('INFO', f"Creating client role: {role_name}")
            
            url = f"{self.admin_base_url}/realms/{realm_name}/clients/{client_id}/roles"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, headers=headers, json=role_config, timeout=10)
            if response.status_code in [201, 409]:  # 409 means role already exists
                self.log('SUCCESS', f"Client role '{role_name}' created/exists")
                return True
            else:
                self.log('ERROR', f"Failed to create client role: {response.status_code}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Error creating client role: {e}")
            return False
    
    def assign_client_scope(self, realm_name: str, client_id: str, scope_name: str, assignment_type: str = 'default') -> bool:
        """Assign a client scope to a client."""
        try:
            self.log('INFO', f"Assigning scope '{scope_name}' to client (type: {assignment_type})")
            
            # Get scope ID
            scope_id = self.get_client_scope_id(realm_name, scope_name)
            if not scope_id:
                self.log('ERROR', f"Scope '{scope_name}' not found")
                return False
            
            # Get client UUID
            client_uuid = self.get_client_uuid(realm_name, client_id)
            if not client_uuid:
                self.log('ERROR', f"Client '{client_id}' not found")
                return False
            
            # Assign scope
            url = f"{self.admin_base_url}/realms/{realm_name}/clients/{client_uuid}/client-scopes/{scope_id}"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.put(url, headers=headers, timeout=10)
            if response.status_code in [200, 204, 409]:  # 409 means already assigned
                self.log('SUCCESS', f"Scope '{scope_name}' assigned to client")
                return True
            else:
                self.log('ERROR', f"Failed to assign scope: {response.status_code}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Error assigning scope: {e}")
            return False
    
    def create_user(self, realm_name: str, user_config: Dict[str, Any]) -> bool:
        """Create a user in Keycloak."""
        try:
            username = user_config['username']
            self.log('INFO', f"Creating user: {username}")
            
            url = f"{self.admin_base_url}/realms/{realm_name}/users"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, headers=headers, json=user_config, timeout=10)
            if response.status_code in [201, 409]:  # 409 means user already exists
                self.log('SUCCESS', f"User '{username}' created/exists")
                return True
            else:
                self.log('ERROR', f"Failed to create user: {response.status_code}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Error creating user: {e}")
            return False
    
    def get_user_uuid(self, realm_name: str, username: str) -> Optional[str]:
        """Get the UUID of a user by username."""
        try:
            url = f"{self.admin_base_url}/realms/{realm_name}/users?username={username}"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                users = response.json()
                if users:
                    return users[0]['id']
            
            return None
            
        except Exception as e:
            self.log('ERROR', f"Error getting user UUID: {e}")
            return None
    
    def assign_client_role_to_user(self, realm_name: str, username: str, client_id: str, role_name: str) -> bool:
        """Assign a client role to a user."""
        try:
            self.log('INFO', f"Assigning role '{role_name}' to user '{username}'")
            
            # Get user UUID
            user_uuid = self.get_user_uuid(realm_name, username)
            if not user_uuid:
                self.log('ERROR', f"User '{username}' not found")
                return False
            
            # Get client UUID
            client_uuid = self.get_client_uuid(realm_name, client_id)
            if not client_uuid:
                self.log('ERROR', f"Client '{client_id}' not found")
                return False
            
            # Get role representation
            url = f"{self.admin_base_url}/realms/{realm_name}/clients/{client_uuid}/roles/{role_name}"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                self.log('ERROR', f"Role '{role_name}' not found")
                return False
            
            role_representation = response.json()
            
            # Assign role to user
            url = f"{self.admin_base_url}/realms/{realm_name}/users/{user_uuid}/role-mappings/clients/{client_uuid}"
            response = requests.post(url, headers=headers, json=[role_representation], timeout=10)
            if response.status_code in [200, 204, 409]:  # 409 means already assigned
                self.log('SUCCESS', f"Role '{role_name}' assigned to user '{username}'")
                return True
            else:
                self.log('ERROR', f"Failed to assign role: {response.status_code}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Error assigning role: {e}")
            return False
    
    def copy_authentication_flow(self, realm_name: str, source_flow: str, new_flow_name: str) -> bool:
        """Copy an authentication flow."""
        try:
            self.log('INFO', f"Copying authentication flow '{source_flow}' to '{new_flow_name}'")
            
            # Get source flow
            url = f"{self.admin_base_url}/realms/{realm_name}/authentication/flows"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                self.log('ERROR', f"Failed to get flows: {response.status_code}")
                return False
            
            flows = response.json()
            source_flow_data = None
            for flow in flows:
                if flow['alias'] == source_flow:
                    source_flow_data = flow
                    break
            
            if not source_flow_data:
                self.log('ERROR', f"Source flow '{source_flow}' not found")
                return False
            
            # Create new flow
            new_flow_data = source_flow_data.copy()
            new_flow_data['alias'] = new_flow_name
            new_flow_data['id'] = None
            
            response = requests.post(url, headers=headers, json=new_flow_data, timeout=10)
            if response.status_code in [201, 409]:  # 409 means flow already exists
                self.log('SUCCESS', f"Authentication flow '{new_flow_name}' created")
                return True
            else:
                self.log('ERROR', f"Failed to create flow: {response.status_code}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Error copying authentication flow: {e}")
            return False
    
    def add_authenticator_to_flow(self, realm_name: str, flow_name: str, provider_id: str) -> bool:
        """Add an authenticator to an authentication flow."""
        try:
            self.log('INFO', f"Adding authenticator '{provider_id}' to flow '{flow_name}'")
            
            # Get flow ID
            url = f"{self.admin_base_url}/realms/{realm_name}/authentication/flows"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                self.log('ERROR', f"Failed to get flows: {response.status_code}")
                return False
            
            flows = response.json()
            flow_id = None
            for flow in flows:
                if flow['alias'] == flow_name:
                    flow_id = flow['id']
                    break
            
            if not flow_id:
                self.log('ERROR', f"Flow '{flow_name}' not found")
                return False
            
            # Add authenticator
            url = f"{self.admin_base_url}/realms/{realm_name}/authentication/flows/{flow_id}/executions/execution"
            data = {
                'provider': provider_id,
                'type': 'basic-flow'
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=10)
            if response.status_code in [201, 409]:  # 409 means already exists
                self.log('SUCCESS', f"Authenticator '{provider_id}' added to flow")
                return True
            else:
                self.log('ERROR', f"Failed to add authenticator: {response.status_code}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Error adding authenticator: {e}")
            return False
    
    def update_authenticator_requirement(self, realm_name: str, flow_name: str, provider_id: str, requirement: str) -> bool:
        """Update authenticator requirement in a flow."""
        try:
            self.log('INFO', f"Updating authenticator requirement for '{provider_id}' in flow '{flow_name}'")
            
            # Get flow ID
            url = f"{self.admin_base_url}/realms/{realm_name}/authentication/flows"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                self.log('ERROR', f"Failed to get flows: {response.status_code}")
                return False
            
            flows = response.json()
            flow_id = None
            for flow in flows:
                if flow['alias'] == flow_name:
                    flow_id = flow['id']
                    break
            
            if not flow_id:
                self.log('ERROR', f"Flow '{flow_name}' not found")
                return False
            
            # Get executions
            url = f"{self.admin_base_url}/realms/{realm_name}/authentication/flows/{flow_id}/executions"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                self.log('ERROR', f"Failed to get executions: {response.status_code}")
                return False
            
            executions = response.json()
            execution_id = None
            for execution in executions:
                if execution.get('providerId') == provider_id:
                    execution_id = execution['id']
                    break
            
            if not execution_id:
                self.log('ERROR', f"Authenticator '{provider_id}' not found in flow")
                return False
            
            # Update requirement
            url = f"{self.admin_base_url}/realms/{realm_name}/authentication/executions/{execution_id}"
            data = {'requirement': requirement}
            
            response = requests.put(url, headers=headers, json=data, timeout=10)
            if response.status_code == 204:
                self.log('SUCCESS', f"Authenticator requirement updated to '{requirement}'")
                return True
            else:
                self.log('ERROR', f"Failed to update requirement: {response.status_code}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Error updating authenticator requirement: {e}")
            return False
    
    def set_default_client_authentication_flow(self, realm_name: str, flow_name: str) -> bool:
        """Set the default client authentication flow for a realm."""
        try:
            self.log('INFO', f"Setting default client authentication flow to '{flow_name}'")
            
            # Get realm config
            url = f"{self.admin_base_url}/realms/{realm_name}"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                self.log('ERROR', f"Failed to get realm config: {response.status_code}")
                return False
            
            realm_config = response.json()
            
            # Update default flow
            realm_config['attributes'] = realm_config.get('attributes', {})
            realm_config['attributes']['clientAuthenticationFlow'] = flow_name
            
            response = requests.put(url, headers=headers, json=realm_config, timeout=10)
            if response.status_code == 204:
                self.log('SUCCESS', f"Default client authentication flow set to '{flow_name}'")
                return True
            else:
                self.log('ERROR', f"Failed to set default flow: {response.status_code}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Error setting default flow: {e}")
            return False
    
    def setup_authentication_flows(self, realm_name: str, flows_config: List[Dict[str, Any]]) -> bool:
        """Setup authentication flows for a realm."""
        try:
            self.log('INFO', f"Setting up authentication flows for realm '{realm_name}'")
            
            for flow_config in flows_config:
                flow_name = flow_config['name']
                source_flow = flow_config.get('copyFrom', 'browser')
                
                # Copy flow
                if not self.copy_authentication_flow(realm_name, source_flow, flow_name):
                    return False
                
                # Add authenticators
                for authenticator in flow_config.get('authenticators', []):
                    provider_id = authenticator['providerId']
                    requirement = authenticator.get('requirement', 'REQUIRED')
                    
                    if not self.add_authenticator_to_flow(realm_name, flow_name, provider_id):
                        return False
                    
                    if not self.update_authenticator_requirement(realm_name, flow_name, provider_id, requirement):
                        return False
                
                # Set as default if specified
                if flow_config.get('setAsDefault', False):
                    if not self.set_default_client_authentication_flow(realm_name, flow_name):
                        return False
            
            self.log('SUCCESS', "Authentication flows setup completed")
            return True
            
        except Exception as e:
            self.log('ERROR', f"Error setting up authentication flows: {e}")
            return False
    
    def get_client_secret(self, realm_name: str, client_id: str) -> Optional[str]:
        """Get the client secret for a client."""
        try:
            # Get client UUID
            client_uuid = self.get_client_uuid(realm_name, client_id)
            if not client_uuid:
                return None
            
            # Get client secret
            url = f"{self.admin_base_url}/realms/{realm_name}/clients/{client_uuid}/client-secret"
            headers = {
                'Authorization': f'Bearer {self.admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                secret_data = response.json()
                return secret_data.get('value')
            
            return None
            
        except Exception as e:
            self.log('ERROR', f"Error getting client secret: {e}")
            return None
    
    def test_token_exchange(self, realm_name: str, config: Dict[str, Any]) -> bool:
        """Test token exchange functionality."""
        try:
            self.log('INFO', "Testing token exchange functionality...")
            
            # Get client secret
            client_id = config['clients'][0]['clientId']  # Use first client for testing
            client_secret = self.get_client_secret(realm_name, client_id)
            if not client_secret:
                self.log('ERROR', "Could not get client secret for testing")
                return False
            
            # Test token exchange
            token_url = f"{self.keycloak_url}/realms/{realm_name}/protocol/openid-connect/token"
            data = {
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret
            }
            
            response = requests.post(token_url, data=data, timeout=10)
            if response.status_code == 200:
                token_data = response.json()
                if 'access_token' in token_data:
                    self.log('SUCCESS', "Token exchange test passed")
                    return True
                else:
                    self.log('ERROR', "Token exchange response missing access_token")
                    return False
            else:
                self.log('ERROR', f"Token exchange test failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Error testing token exchange: {e}")
            return False
    
    def setup_from_config(self, config: Dict[str, Any]) -> bool:
        """Setup Keycloak from configuration file."""
        try:
            realm_name = config['realm']['realm']
            self.log('INFO', f"Setting up Keycloak for realm: {realm_name}")
            
            # Step 1: Create realm
            if not self.create_realm(config['realm']):
                return False
            
            # Step 2: Update realm attributes if specified
            if 'realmAttributes' in config:
                if not self.update_realm_attributes(realm_name, config['realmAttributes']):
                    return False
            
            # Step 3: Create client scopes
            for scope_config in config.get('clientScopes', []):
                if not self.create_client_scope(realm_name, scope_config):
                    return False
                
                # Add mappers if specified
                for mapper_config in scope_config.get('mappers', []):
                    scope_id = self.get_client_scope_id(realm_name, scope_config['name'])
                    if scope_id:
                        if not self.add_scope_mapper(realm_name, scope_id, mapper_config):
                            return False
            
            # Step 4: Create clients
            for client_config in config.get('clients', []):
                if not self.create_client(realm_name, client_config):
                    return False
                
                # Update token exchange settings if specified
                if client_config.get('tokenExchange'):
                    client_uuid = self.get_client_uuid(realm_name, client_config['clientId'])
                    if client_uuid:
                        if not self.update_client_token_exchange(realm_name, client_uuid, client_config):
                            return False
                
                # Create client roles if specified
                for role_config in client_config.get('roles', []):
                    if not self.create_client_role(realm_name, client_uuid, role_config):
                        return False
                
                # Assign client scopes if specified
                for scope_name in client_config.get('assignedScopes', []):
                    assignment_type = 'default'  # Default assignment type
                    if not self.assign_client_scope(realm_name, client_config['clientId'], scope_name, assignment_type):
                        return False
            
            # Step 5: Create users
            for user_config in config.get('users', []):
                if not self.create_user(realm_name, user_config):
                    return False
                
                # Assign client roles if specified
                for role_assignment in user_config.get('clientRoles', []):
                    client_id = role_assignment['clientId']
                    role_name = role_assignment['roleName']
                    if not self.assign_client_role_to_user(realm_name, user_config['username'], client_id, role_name):
                        return False
            
            # Step 6: Setup authentication flows
            if 'authenticationFlows' in config:
                if not self.setup_authentication_flows(realm_name, config['authenticationFlows']):
                    return False
            
            # Step 7: Test token exchange
            if not self.test_token_exchange(realm_name, config):
                return False
            
            self.log('SUCCESS', f"Keycloak setup completed for realm: {realm_name}")
            return True
            
        except Exception as e:
            self.log('ERROR', f"Error in setup_from_config: {e}")
            return False
    
    def print_summary(self, config: Dict[str, Any]) -> None:
        """Print a summary of the configuration."""
        realm_name = config['realm']['realm']
        
        print(f"\n{Colors.CYAN}=== Keycloak Setup Summary ==={Colors.NC}")
        print(f"{Colors.WHITE}Realm:{Colors.NC} {realm_name}")
        print(f"{Colors.WHITE}Keycloak URL:{Colors.NC} {self.keycloak_url}")
        
        # Client summary
        if 'clients' in config:
            print(f"\n{Colors.WHITE}Clients:{Colors.NC}")
            for client in config['clients']:
                client_id = client['clientId']
                client_type = client.get('type', 'unknown')
                print(f"  - {client_id} ({client_type})")
                
                # Get client secret if confidential
                if client_type == 'confidential':
                    secret = self.get_client_secret(realm_name, client_id)
                    if secret:
                        print(f"    Secret: {secret}")
        
        # User summary
        if 'users' in config:
            print(f"\n{Colors.WHITE}Users:{Colors.NC}")
            for user in config['users']:
                username = user['username']
                print(f"  - {username}")
                
                # Show assigned roles
                if 'clientRoles' in user:
                    for role_assignment in user['clientRoles']:
                        print(f"    Role: {role_assignment['roleName']} (Client: {role_assignment['clientId']})")
        
        # Authentication flows summary
        if 'authenticationFlows' in config:
            print(f"\n{Colors.WHITE}Authentication Flows:{Colors.NC}")
            for flow in config['authenticationFlows']:
                flow_name = flow['name']
                print(f"  - {flow_name}")
                if flow.get('setAsDefault', False):
                    print(f"    (Default client authentication flow)")
        
        print(f"\n{Colors.GREEN}Setup completed successfully!{Colors.NC}")
    
    def print_test_commands(self, config: Dict[str, Any]) -> None:
        """Print test commands for verification."""
        realm_name = config['realm']['realm']
        client_id = config['clients'][0]['clientId'] if config.get('clients') else None
        
        print(f"\n{Colors.CYAN}=== Test Commands ==={Colors.NC}")
        print(f"{Colors.WHITE}Test realm access:{Colors.NC}")
        print(f"curl {self.keycloak_url}/realms/{realm_name}")
        
        if client_id:
            print(f"\n{Colors.WHITE}Test OAuth metadata:{Colors.NC}")
            print(f"curl {self.keycloak_url}/realms/{realm_name}/.well-known/oauth-authorization-server")
            
            print(f"\n{Colors.WHITE}Test OpenID Connect metadata:{Colors.NC}")
            print(f"curl {self.keycloak_url}/realms/{realm_name}/.well-known/openid_configuration")
        
        print(f"\n{Colors.WHITE}Test token acquisition:{Colors.NC}")
        if client_id:
            print(f"curl -X POST {self.keycloak_url}/realms/{realm_name}/protocol/openid-connect/token \\")
            print(f"  -d 'grant_type=client_credentials' \\")
            print(f"  -d 'client_id={client_id}' \\")
            print(f"  -d 'client_secret=YOUR_CLIENT_SECRET'")

def load_config(config_file: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        log(f"Configuration loaded from {config_file}", "SUCCESS")
        return config
    except Exception as e:
        log(f"Failed to load configuration: {e}", "ERROR")
        sys.exit(1)

def verify_setup(keycloak_url: str, realm_name: str) -> bool:
    """Verify that Keycloak setup was successful."""
    log("Verifying Keycloak setup...")
    
    # Test realm exists
    try:
        response = requests.get(f"{keycloak_url}/realms/{realm_name}")
        if response.status_code == 200:
            log(f"Realm '{realm_name}' exists", "SUCCESS")
        else:
            log(f"Realm '{realm_name}' not found", "ERROR")
            return False
    except requests.exceptions.RequestException as e:
        log(f"Failed to verify realm: {e}", "ERROR")
        return False
    
    # Test OAuth authorization server metadata
    try:
        response = requests.get(f"{keycloak_url}/realms/{realm_name}/.well-known/oauth-authorization-server")
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
    parser = argparse.ArgumentParser(description="Boot and configure Keycloak")
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE, help="Path to config file")
    parser.add_argument("--url", default=DEFAULT_KEYCLOAK_URL, help="Keycloak URL")
    parser.add_argument("--summary", action="store_true", help="Show detailed summary")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    log("=== Boot Keycloak: Complete Setup and Configuration ===", "INFO")
    
    try:
        # Step 1: Load configuration
        config = load_config(args.config)
        realm_name = config['realm']['realm']
        
        # Step 2: Manage Docker Compose
        if not manage_docker_compose(args.verbose):
            log("Failed to manage Docker Compose", "ERROR")
            sys.exit(1)
        
        # Step 3: Wait for Keycloak to be ready
        if not wait_for_keycloak(args.url):
            log("Keycloak failed to start", "ERROR")
            sys.exit(1)
        
        # Step 4: Initialize Keycloak setup
        keycloak_setup = KeycloakSetup(args.url, DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD)
        
        # Step 5: Get admin token
        if not keycloak_setup.get_admin_token():
            log("Failed to get admin token", "ERROR")
            sys.exit(1)
        
        # Step 6: Detect admin API
        if not keycloak_setup.detect_admin_base_url():
            log("Failed to detect admin API", "ERROR")
            sys.exit(1)
        
        # Step 7: Setup Keycloak configuration
        if not keycloak_setup.setup_from_config(config):
            log("Failed to setup Keycloak configuration", "ERROR")
            sys.exit(1)
        
        # Step 8: Verify setup
        if not verify_setup(args.url, realm_name):
            log("Keycloak setup verification failed", "ERROR")
            sys.exit(1)
        
        # Step 9: Print summary and test commands
        if args.summary:
            keycloak_setup.print_summary(config)
        
        keycloak_setup.print_test_commands(config)
        
        log("=== Boot Keycloak completed successfully! ===", "SUCCESS")
        log("Keycloak is ready for MCP integration")
        log(f"Keycloak URL: {args.url}")
        log(f"Realm: {realm_name}")
        
    except Exception as e:
        log(f"Unexpected error: {e}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()
