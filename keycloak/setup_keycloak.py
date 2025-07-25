#!/usr/bin/env python3

"""
Keycloak Token Exchange Setup Script

This script automates the complete setup for Standard Token Exchange in Keycloak 26.2.5
using configuration from a JSON file.

Usage:
    python setup_keycloak.py --config config.json --url http://localhost:8080
    
Requirements:
    pip install requests
"""

import argparse
import json
import sys
import time
from typing import Dict, List, Optional, Any
import requests
from urllib.parse import urljoin


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


class KeycloakSetup:
    """Keycloak setup automation class."""
    
    def __init__(self, keycloak_url: str, admin_username: str = "admin", admin_password: str = "admin"):
        self.keycloak_url = keycloak_url.rstrip('/')
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.admin_token = None
        self.session = requests.Session()
        self.debug = False
        self.admin_base_url = None  # Will be detected during setup
        
    def log(self, level: str, message: str):
        """Log messages with color coding."""
        colors = {
            'INFO': Colors.BLUE,
            'SUCCESS': Colors.GREEN,
            'WARNING': Colors.YELLOW,
            'ERROR': Colors.RED,
            'DEBUG': Colors.PURPLE
        }
        color = colors.get(level, Colors.WHITE)
        
        # Only print DEBUG messages if debug is enabled
        if level == 'DEBUG' and not self.debug:
            return
            
        print(f"{color}[{level}]{Colors.NC} {message}")
        
    def get_admin_token(self) -> bool:
        """Get admin access token."""
        self.log('INFO', 'Getting admin access token...')
        
        # Try multiple token endpoint paths
        token_paths = [
            "/realms/master/protocol/openid-connect/token",
            "/auth/realms/master/protocol/openid-connect/token"
        ]
        
        for token_path in token_paths:
            try:
                token_url = f"{self.keycloak_url}{token_path}"
                if self.debug:
                    self.log('DEBUG', f'Trying token endpoint: {token_url}')
                    
                response = self.session.post(
                    token_url,
                    data={
                        "grant_type": "password",
                        "client_id": "admin-cli",
                        "username": self.admin_username,
                        "password": self.admin_password
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    self.admin_token = token_data.get('access_token')
                    
                    if not self.admin_token:
                        continue
                        
                    self.session.headers.update({'Authorization': f'Bearer {self.admin_token}'})
                    self.log('SUCCESS', 'Admin token obtained')
                    if self.debug:
                        self.log('DEBUG', f'Working token endpoint: {token_url}')
                    return True
                elif self.debug:
                    self.log('DEBUG', f'Token endpoint failed with status: {response.status_code}')
                    
            except requests.exceptions.RequestException as e:
                if self.debug:
                    self.log('DEBUG', f'Token endpoint error: {e}')
                continue
        
        self.log('ERROR', 'Failed to get admin token from any endpoint')
        return False
        
    def detect_admin_base_url(self) -> bool:
        """Detect the correct admin API base URL."""
        admin_paths = ["/admin", "/auth/admin"]
        
        for admin_path in admin_paths:
            try:
                test_url = f"{self.keycloak_url}{admin_path}/realms"
                if self.debug:
                    self.log('DEBUG', f'Testing admin API at: {test_url}')
                    
                response = self.session.get(test_url)
                if response.status_code == 200:
                    self.admin_base_url = f"{self.keycloak_url}{admin_path}"
                    if self.debug:
                        self.log('DEBUG', f'Admin API base URL: {self.admin_base_url}')
                    return True
                elif self.debug:
                    self.log('DEBUG', f'Admin API test failed with status: {response.status_code}')
                    
            except requests.exceptions.RequestException as e:
                if self.debug:
                    self.log('DEBUG', f'Admin API test error: {e}')
                continue
        
        self.log('ERROR', 'Could not detect admin API base URL')
        return False
            
    def create_realm(self, realm_config: Dict[str, Any]) -> bool:
        """Create a realm."""
        realm_name = realm_config['name']
        self.log('INFO', f'Creating realm: {realm_name}...')
        
        if not self.admin_base_url:
            if not self.detect_admin_base_url():
                return False
        
        try:
            # Check if realm exists
            response = self.session.get(f"{self.admin_base_url}/realms/{realm_name}")
            if response.status_code == 200:
                self.log('WARNING', f'Realm {realm_name} already exists, updating attributes...')
                return self.update_realm_attributes(realm_name, realm_config)
                
            # Create realm - use proper Keycloak realm structure
            realm_data = {
                "realm": realm_config['name'],
                "displayName": realm_config.get('displayName', realm_config['name']),
                "enabled": realm_config.get('enabled', True)
            }
            
            # Add optional settings only if they're reasonable values
            if 'accessTokenLifespan' in realm_config:
                realm_data["accessTokenLifespan"] = realm_config['accessTokenLifespan']
            if 'accessTokenLifespanForImplicitFlow' in realm_config:
                realm_data["accessTokenLifespanForImplicitFlow"] = realm_config['accessTokenLifespanForImplicitFlow']
            if 'ssoSessionIdleTimeout' in realm_config:
                realm_data["ssoSessionIdleTimeout"] = realm_config['ssoSessionIdleTimeout']
            if 'ssoSessionMaxLifespan' in realm_config:
                realm_data["ssoSessionMaxLifespan"] = realm_config['ssoSessionMaxLifespan']
            if 'offlineSessionIdleTimeout' in realm_config:
                realm_data["offlineSessionIdleTimeout"] = realm_config['offlineSessionIdleTimeout']
            
            # Add realm attributes if specified
            if 'attributes' in realm_config:
                realm_data["attributes"] = {}
                for key, value in realm_config['attributes'].items():
                    realm_data["attributes"][key] = str(value)  # Keycloak expects string values
            
            if self.debug:
                self.log('DEBUG', f'Realm data: {json.dumps(realm_data, indent=2)}')
            
            response = self.session.post(
                f"{self.admin_base_url}/realms",
                json=realm_data
            )
            
            if response.status_code != 201:
                self.log('ERROR', f'Failed to create realm. Status: {response.status_code}')
                self.log('ERROR', f'Response: {response.text}')
                return False
            
            self.log('SUCCESS', f'Realm {realm_name} created')
            
            # Log SPIFFE attributes if they were set
            if 'attributes' in realm_config:
                self.log('INFO', 'Realm attributes configured:')
                for key, value in realm_config['attributes'].items():
                    self.log('INFO', f'  {key}: {value}')
            
            return True
            
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to create realm {realm_name}: {e}')
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    self.log('ERROR', f'Error details: {error_detail}')
                except:
                    self.log('ERROR', f'Error response: {e.response.text}')
            return False
            
    def update_realm_attributes(self, realm_name: str, realm_config: Dict[str, Any]) -> bool:
        """Update realm attributes for an existing realm."""
        if 'attributes' not in realm_config:
            self.log('INFO', 'No attributes to update')
            return True
            
        self.log('INFO', f'Updating attributes for realm: {realm_name}...')
        
        try:
            # Get current realm configuration
            response = self.session.get(f"{self.admin_base_url}/realms/{realm_name}")
            response.raise_for_status()
            current_realm = response.json()
            
            # Get current attributes or initialize empty dict
            current_attributes = current_realm.get('attributes', {})
            
            # Add/update new attributes
            for key, value in realm_config['attributes'].items():
                current_attributes[key] = str(value)  # Keycloak expects string values
                
            # Update the current realm configuration with new attributes
            current_realm["attributes"] = current_attributes
            
            if self.debug:
                self.log('DEBUG', f'Updating realm with attributes: {json.dumps({"attributes": current_attributes}, indent=2)}')
            
            # Update the realm with complete configuration
            response = self.session.put(
                f"{self.admin_base_url}/realms/{realm_name}",
                json=current_realm
            )
            
            if response.status_code not in (200, 204):
                self.log('ERROR', f'Failed to update realm attributes. Status: {response.status_code}')
                self.log('ERROR', f'Response: {response.text}')
                return False
            
            self.log('SUCCESS', f'Realm {realm_name} attributes updated')
            
            # Log updated attributes
            self.log('INFO', 'Updated realm attributes:')
            for key, value in realm_config['attributes'].items():
                self.log('INFO', f'  {key}: {value}')
            
            return True
            
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to update realm attributes for {realm_name}: {e}')
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    self.log('ERROR', f'Error details: {error_detail}')
                except:
                    self.log('ERROR', f'Error response: {e.response.text}')
            return False
            
    def create_client_scope(self, realm_name: str, scope_config: Dict[str, Any]) -> bool:
        """Create a client scope."""
        scope_name = scope_config['name']
        self.log('INFO', f'Creating client scope: {scope_name}...')
        
        try:
            # Check if scope exists
            response = self.session.get(f"{self.admin_base_url}/realms/{realm_name}/client-scopes")
            response.raise_for_status()
            
            existing_scopes = response.json()
            if any(scope['name'] == scope_name for scope in existing_scopes):
                self.log('WARNING', f'Client scope {scope_name} already exists, skipping creation')
                return True
                
            # Create scope
            response = self.session.post(
                f"{self.admin_base_url}/realms/{realm_name}/client-scopes",
                json=scope_config
            )
            response.raise_for_status()
            
            self.log('SUCCESS', f'Client scope {scope_name} created')
            
            # Add mappers if specified
            if 'mappers' in scope_config and scope_config['mappers']:
                scope_id = self.get_client_scope_id(realm_name, scope_name)
                if scope_id:
                    for mapper in scope_config['mappers']:
                        self.add_scope_mapper(realm_name, scope_id, mapper)

            # Add role scope mappings if 'roles' is specified
            if 'roles' in scope_config and scope_config['roles']:
                scope_id = self.get_client_scope_id(realm_name, scope_name)
                if scope_id:
                    for role_assoc in scope_config['roles']:
                        client = role_assoc['client']
                        role = role_assoc['role']
                        # Get client UUID
                        client_uuid = self.get_client_uuid(realm_name, client)
                        if not client_uuid:
                            self.log('ERROR', f'Client {client} not found for scope mapping')
                            continue
                        # Get role details
                        try:
                            response = self.session.get(
                                f"{self.admin_base_url}/realms/{realm_name}/clients/{client_uuid}/roles/{role}"
                            )
                            response.raise_for_status()
                            role_data = response.json()
                        except requests.exceptions.RequestException as e:
                            self.log('ERROR', f'Failed to get role {role} for client {client}: {e}')
                            continue
                        # Add scope mapping
                        try:
                            response = self.session.post(
                                f"{self.admin_base_url}/realms/{realm_name}/client-scopes/{scope_id}/scope-mappings/clients/{client_uuid}",
                                json=[role_data]
                            )
                            if response.status_code not in (204, 201):
                                self.log('ERROR', f'Failed to add scope mapping for role {role} to scope {scope_name}: {response.text}')
                            else:
                                self.log('SUCCESS', f'Added scope mapping: {role} to client scope {scope_name}')
                        except requests.exceptions.RequestException as e:
                            self.log('ERROR', f'Failed to add scope mapping for role {role} to scope {scope_name}: {e}')
                        
            return True
            
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to create client scope {scope_name}: {e}')
            return False
            
    def get_client_scope_id(self, realm_name: str, scope_name: str) -> Optional[str]:
        """Get client scope UUID by name."""
        try:
            response = self.session.get(f"{self.admin_base_url}/realms/{realm_name}/client-scopes")
            response.raise_for_status()
            
            scopes = response.json()
            for scope in scopes:
                if scope['name'] == scope_name:
                    return scope['id']
                    
            return None
            
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to get client scope ID for {scope_name}: {e}')
            return None
            
    def add_scope_mapper(self, realm_name: str, scope_id: str, mapper_config: Dict[str, Any]) -> bool:
        """Add a mapper to a client scope."""
        mapper_name = mapper_config['name']
        self.log('INFO', f'Adding mapper {mapper_name} to scope...')
        
        try:
            # Check if mapper exists
            response = self.session.get(
                f"{self.admin_base_url}/realms/{realm_name}/client-scopes/{scope_id}/protocol-mappers/models"
            )
            response.raise_for_status()
            
            existing_mappers = response.json()
            if any(mapper['name'] == mapper_name for mapper in existing_mappers):
                self.log('WARNING', f'Mapper {mapper_name} already exists, skipping creation')
                return True
                
            # Create mapper
            mapper_data = {
                "name": mapper_name,
                "protocol": "openid-connect",
                "protocolMapper": mapper_config['type'],
                "config": mapper_config['config']
            }
            
            response = self.session.post(
                f"{self.admin_base_url}/realms/{realm_name}/client-scopes/{scope_id}/protocol-mappers/models",
                json=mapper_data
            )
            response.raise_for_status()
            
            self.log('SUCCESS', f'Mapper {mapper_name} added')
            return True
            
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to add mapper {mapper_name}: {e}')
            return False
            
    def create_client(self, realm_name: str, client_config: Dict[str, Any]) -> bool:
        """Create a client."""
        client_id = client_config['clientId']
        self.log('INFO', f'Creating client: {client_id}...')
        
        try:
            # Check if client exists
            response = self.session.get(
                f"{self.admin_base_url}/realms/{realm_name}/clients",
                params={"clientId": client_id}
            )
            response.raise_for_status()
            
            existing_clients = response.json()
            if existing_clients:
                self.log('WARNING', f'Client {client_id} already exists, updating token exchange settings...')
                # Update existing client with token exchange settings
                client_uuid = existing_clients[0]['id']
                return self.update_client_token_exchange(realm_name, client_uuid, client_config)
                
            # Prepare client configuration
            client_data = {
                "clientId": client_id,
                "name": client_config.get('name', client_id),
                "enabled": client_config.get('enabled', True),
                "protocol": "openid-connect"
            }
            
            # Configure based on client type
            if client_config['type'] == 'public':
                client_data.update({
                    "publicClient": True,
                    "standardFlowEnabled": client_config.get('standardFlowEnabled', True),
                    "directAccessGrantsEnabled": client_config.get('directAccessGrantsEnabled', True),
                    "redirectUris": client_config.get('redirectUris', []),
                    "webOrigins": client_config.get('webOrigins', [])
                })
            else:  # confidential
                client_data.update({
                    "publicClient": False,
                    "serviceAccountsEnabled": client_config.get('serviceAccountsEnabled', True),
                    "standardFlowEnabled": client_config.get('standardFlowEnabled', False),
                    "directAccessGrantsEnabled": client_config.get('directAccessGrantsEnabled', False)
                })
                
            # Set fullScopeAllowed from config (defaults to true if not specified)
            if 'fullScopeAllowed' in client_config:
                client_data["fullScopeAllowed"] = client_config['fullScopeAllowed']
            
            # Add client secret if provided
            if client_config.get('clientSecret'):
                client_data["secret"] = client_config['clientSecret']
            
            # Set client authenticator type (defaults to "client-secret" if not specified)
            client_data["clientAuthenticatorType"] = client_config.get('clientAuthenticatorType', 'client-secret')
            
            # Initialize attributes if not already present
            if "attributes" not in client_data:
                client_data["attributes"] = {}
            
            # Add custom attributes from config
            if 'attributes' in client_config:
                for key, value in client_config['attributes'].items():
                    client_data["attributes"][key] = str(value)  # Keycloak expects string values
                    
            # Add token exchange settings for confidential clients
            if client_config.get('tokenExchange', {}).get('enabled', False):
                client_data["attributes"]["token.exchange.standard.enabled"] = "true"
                
                refresh_setting = client_config.get('tokenExchange', {}).get('allowRefreshToken')
                if refresh_setting:
                    client_data["attributes"]["token.exchange.refresh.enabled"] = refresh_setting
                    
            if self.debug:
                self.log('DEBUG', f'Client data: {json.dumps(client_data, indent=2)}')
                        
            # Create client
            response = self.session.post(
                f"{self.admin_base_url}/realms/{realm_name}/clients",
                json=client_data
            )
            response.raise_for_status()
            
            self.log('SUCCESS', f'Client {client_id} created')
            
            # Create client roles if specified
            if 'roles' in client_config:
                for role in client_config['roles']:
                    self.create_client_role(realm_name, client_id, role)
                    
            return True
            
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to create client {client_id}: {e}')
            return False
            
    def update_client_token_exchange(self, realm_name: str, client_uuid: str, client_config: Dict[str, Any]) -> bool:
        """Update client with token exchange settings."""
        client_id = client_config['clientId']
        self.log('INFO', f'Updating token exchange settings for client {client_id}...')
        
        try:
            # Get current client configuration
            response = self.session.get(f"{self.admin_base_url}/realms/{realm_name}/clients/{client_uuid}")
            response.raise_for_status()
            current_client = response.json()
            
            # Initialize attributes if not already present
            if "attributes" not in current_client:
                current_client["attributes"] = {}
                
            # Add custom attributes from config
            if 'attributes' in client_config:
                for key, value in client_config['attributes'].items():
                    current_client["attributes"][key] = str(value)  # Keycloak expects string values
            
            # Update attributes for token exchange
            if client_config.get('tokenExchange', {}).get('enabled', False):
                current_client["attributes"]["token.exchange.standard.enabled"] = "true"
                
                refresh_setting = client_config.get('tokenExchange', {}).get('allowRefreshToken')
                if refresh_setting:
                    current_client["attributes"]["token.exchange.refresh.enabled"] = refresh_setting
                    
                if self.debug:
                    self.log('DEBUG', f'Updated client attributes: {current_client.get("attributes", {})}')
                    
                # Update the client
                response = self.session.put(
                    f"{self.admin_base_url}/realms/{realm_name}/clients/{client_uuid}",
                    json=current_client
                )
                response.raise_for_status()
                
                self.log('SUCCESS', f'Token exchange enabled for client {client_id}')
            
            return True
            
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to update token exchange for client {client_id}: {e}')
            return False
            
    def get_client_uuid(self, realm_name: str, client_id: str) -> Optional[str]:
        """Get client UUID by client ID."""
        try:
            response = self.session.get(
                f"{self.admin_base_url}/realms/{realm_name}/clients",
                params={"clientId": client_id}
            )
            response.raise_for_status()
            
            clients = response.json()
            if clients:
                return clients[0]['id']
                
            return None
            
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to get client UUID for {client_id}: {e}')
            return None
            
    def create_client_role(self, realm_name: str, client_id: str, role_config: Dict[str, Any]) -> bool:
        """Create a client role."""
        role_name = role_config['name']
        self.log('INFO', f'Creating role {role_name} in client {client_id}...')
        
        try:
            client_uuid = self.get_client_uuid(realm_name, client_id)
            if not client_uuid:
                self.log('ERROR', f'Client {client_id} not found')
                return False
                
            # Check if role exists
            response = self.session.get(
                f"{self.admin_base_url}/realms/{realm_name}/clients/{client_uuid}/roles/{role_name}"
            )
            if response.status_code == 200:
                self.log('WARNING', f'Role {role_name} already exists in client {client_id}, skipping creation')
                return True
                
            # Create role
            role_data = {
                "name": role_name,
                "description": role_config.get('description', '')
            }
            
            response = self.session.post(
                f"{self.admin_base_url}/realms/{realm_name}/clients/{client_uuid}/roles",
                json=role_data
            )
            response.raise_for_status()
            
            self.log('SUCCESS', f'Role {role_name} created in client {client_id}')
            return True
            
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to create role {role_name} in client {client_id}: {e}')
            return False
            
    def assign_client_scope(self, realm_name: str, client_id: str, scope_name: str, assignment_type: str = 'default') -> bool:
        """Assign a client scope to a client."""
        self.log('INFO', f'Assigning scope {scope_name} to client {client_id} as {assignment_type}...')
        
        try:
            client_uuid = self.get_client_uuid(realm_name, client_id)
            scope_uuid = self.get_client_scope_id(realm_name, scope_name)
            
            if not client_uuid:
                self.log('ERROR', f'Client {client_id} not found')
                return False
                
            if not scope_uuid:
                self.log('ERROR', f'Client scope {scope_name} not found')
                return False
                
            # Check if scope is already assigned
            response = self.session.get(
                f"{self.admin_base_url}/realms/{realm_name}/clients/{client_uuid}/{assignment_type}-client-scopes"
            )
            response.raise_for_status()
            
            assigned_scopes = response.json()
            if any(scope['name'] == scope_name for scope in assigned_scopes):
                self.log('WARNING', f'Scope {scope_name} already assigned to client {client_id} as {assignment_type}, skipping')
                return True
                
            # Assign scope
            response = self.session.put(
                f"{self.admin_base_url}/realms/{realm_name}/clients/{client_uuid}/{assignment_type}-client-scopes/{scope_uuid}"
            )
            response.raise_for_status()
            
            self.log('SUCCESS', f'Scope {scope_name} assigned to client {client_id} as {assignment_type}')
            return True
            
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to assign scope {scope_name} to client {client_id}: {e}')
            return False
            
    def create_user(self, realm_name: str, user_config: Dict[str, Any]) -> bool:
        """Create a user."""
        username = user_config['username']
        self.log('INFO', f'Creating user: {username}...')
        
        try:
            # Check if user exists
            response = self.session.get(
                f"{self.admin_base_url}/realms/{realm_name}/users",
                params={"username": username}
            )
            response.raise_for_status()
            
            existing_users = response.json()
            if existing_users:
                self.log('WARNING', f'User {username} already exists, skipping creation')
                return True
                
            # Create user
            user_data = {
                "username": username,
                "email": user_config.get('email'),
                "firstName": user_config.get('firstName'),
                "lastName": user_config.get('lastName'),
                "enabled": user_config.get('enabled', True),
                "emailVerified": user_config.get('emailVerified', True)
            }
            
            if 'password' in user_config:
                user_data["credentials"] = [{
                    "type": "password",
                    "value": user_config['password'],
                    "temporary": user_config.get('temporary', False)
                }]
                
            response = self.session.post(
                f"{self.admin_base_url}/realms/{realm_name}/users",
                json=user_data
            )
            response.raise_for_status()
            
            self.log('SUCCESS', f'User {username} created')
            
            # Assign client roles if specified
            if 'clientRoles' in user_config:
                for client_id, roles in user_config['clientRoles'].items():
                    for role_name in roles:
                        self.assign_client_role_to_user(realm_name, username, client_id, role_name)
                        
            return True
            
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to create user {username}: {e}')
            return False
            
    def get_user_uuid(self, realm_name: str, username: str) -> Optional[str]:
        """Get user UUID by username."""
        try:
            response = self.session.get(
                f"{self.admin_base_url}/realms/{realm_name}/users",
                params={"username": username}
            )
            response.raise_for_status()
            
            users = response.json()
            if users:
                return users[0]['id']
                
            return None
            
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to get user UUID for {username}: {e}')
            return None
            
    def assign_client_role_to_user(self, realm_name: str, username: str, client_id: str, role_name: str) -> bool:
        """Assign a client role to a user."""
        self.log('INFO', f'Assigning role {role_name} from client {client_id} to user {username}...')
        
        try:
            user_uuid = self.get_user_uuid(realm_name, username)
            client_uuid = self.get_client_uuid(realm_name, client_id)
            
            if not user_uuid:
                self.log('ERROR', f'User {username} not found')
                return False
                
            if not client_uuid:
                self.log('ERROR', f'Client {client_id} not found')
                return False
                
            # Get role details
            response = self.session.get(
                f"{self.admin_base_url}/realms/{realm_name}/clients/{client_uuid}/roles/{role_name}"
            )
            response.raise_for_status()
            role_data = response.json()
            
            # Assign role
            response = self.session.post(
                f"{self.admin_base_url}/realms/{realm_name}/users/{user_uuid}/role-mappings/clients/{client_uuid}",
                json=[role_data]
            )
            response.raise_for_status()
            
            self.log('SUCCESS', f'Role {role_name} from client {client_id} assigned to user {username}')
            return True
            
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to assign role {role_name} from client {client_id} to user {username}: {e}')
            return False
            
    def copy_authentication_flow(self, realm_name: str, source_flow: str, new_flow_name: str) -> bool:
        """Copy an existing authentication flow."""
        self.log('INFO', f'Copying authentication flow from {source_flow} to {new_flow_name}...')
        
        try:
            copy_url = f"{self.admin_base_url}/realms/{realm_name}/authentication/flows/{source_flow}/copy"
            copy_data = {"newName": new_flow_name}
            
            response = self.session.post(copy_url, json=copy_data)
            
            if response.status_code == 201:
                self.log('SUCCESS', f'Authentication flow {new_flow_name} created from {source_flow}')
                return True
            elif response.status_code == 409:
                self.log('WARNING', f'Authentication flow {new_flow_name} already exists, skipping creation')
                return True
            else:
                self.log('ERROR', f'Failed to copy authentication flow. Status: {response.status_code}')
                self.log('ERROR', f'Response: {response.text}')
                return False
                
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to copy authentication flow {new_flow_name}: {e}')
            return False
            
    def add_authenticator_to_flow(self, realm_name: str, flow_name: str, provider_id: str) -> bool:
        """Add an authenticator to an authentication flow."""
        self.log('INFO', f'Adding authenticator {provider_id} to flow {flow_name}...')
        
        try:
            add_exec_url = f"{self.admin_base_url}/realms/{realm_name}/authentication/flows/{flow_name}/executions/execution"
            exec_data = {"provider": provider_id}
            
            response = self.session.post(add_exec_url, json=exec_data)
            
            if response.status_code == 201:
                self.log('SUCCESS', f'Authenticator {provider_id} added to flow {flow_name}')
                return True
            else:
                self.log('ERROR', f'Failed to add authenticator. Status: {response.status_code}')
                self.log('ERROR', f'Response: {response.text}')
                return False
                
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to add authenticator {provider_id} to flow {flow_name}: {e}')
            return False
            
    def update_authenticator_requirement(self, realm_name: str, flow_name: str, provider_id: str, requirement: str) -> bool:
        """Update the requirement level of an authenticator in a flow."""
        self.log('INFO', f'Setting authenticator {provider_id} requirement to {requirement} in flow {flow_name}...')
        
        try:
            # Get executions
            get_exec_url = f"{self.admin_base_url}/realms/{realm_name}/authentication/flows/{flow_name}/executions"
            response = self.session.get(get_exec_url)
            response.raise_for_status()
            
            executions = response.json()
            
            # Find the specific authenticator execution
            target_execution = next((ex for ex in executions if ex.get("providerId") == provider_id), None)
            
            if not target_execution:
                self.log('ERROR', f'Authenticator {provider_id} not found in flow {flow_name}')
                return False
                
            # Update requirement
            update_data = {
                "id": target_execution["id"],
                "requirement": requirement
            }
            
            response = self.session.put(get_exec_url, json=update_data)
            
            if response.status_code == 204:
                self.log('SUCCESS', f'Authenticator {provider_id} requirement set to {requirement}')
                return True
            else:
                self.log('ERROR', f'Failed to update authenticator requirement. Status: {response.status_code}')
                self.log('ERROR', f'Response: {response.text}')
                return False
                
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to update authenticator requirement: {e}')
            return False
            
    def set_default_client_authentication_flow(self, realm_name: str, flow_name: str) -> bool:
        """Set a flow as the default client authentication flow for the realm."""
        self.log('INFO', f'Setting {flow_name} as default client authentication flow...')
        
        try:
            # Get current realm configuration
            realm_url = f"{self.admin_base_url}/realms/{realm_name}"
            response = self.session.get(realm_url)
            response.raise_for_status()
            
            realm_config = response.json()
            realm_config["clientAuthenticationFlow"] = flow_name
            
            # Update realm configuration
            response = self.session.put(realm_url, json=realm_config)
            
            if response.status_code == 204:
                self.log('SUCCESS', f'Default client authentication flow set to {flow_name}')
                return True
            else:
                self.log('ERROR', f'Failed to update realm configuration. Status: {response.status_code}')
                self.log('ERROR', f'Response: {response.text}')
                return False
                
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to set default client authentication flow: {e}')
            return False
            
    def setup_authentication_flows(self, realm_name: str, flows_config: List[Dict[str, Any]]) -> bool:
        """Set up authentication flows from configuration."""
        self.log('INFO', 'Setting up authentication flows...')
        
        for flow_config in flows_config:
            flow_name = flow_config['name']
            
            # Copy from existing flow if specified
            if 'copyFrom' in flow_config:
                if not self.copy_authentication_flow(realm_name, flow_config['copyFrom'], flow_name):
                    return False
                    
            # Add authenticators
            for authenticator in flow_config.get('authenticators', []):
                provider_id = authenticator['providerId']
                requirement = authenticator.get('requirement', 'REQUIRED')
                
                # Add authenticator to flow
                if not self.add_authenticator_to_flow(realm_name, flow_name, provider_id):
                    return False
                    
                # Update requirement if not default
                if requirement != 'REQUIRED':
                    if not self.update_authenticator_requirement(realm_name, flow_name, provider_id, requirement):
                        return False
                        
            # Set as default flows if specified
            defaults = flow_config.get('setAsDefault', {})
            if defaults.get('clientAuthentication', False):
                if not self.set_default_client_authentication_flow(realm_name, flow_name):
                    return False
                    
        self.log('SUCCESS', 'Authentication flows setup completed')
        return True
            
    def get_client_secret(self, realm_name: str, client_id: str) -> Optional[str]:
        """Get client secret."""
        try:
            client_uuid = self.get_client_uuid(realm_name, client_id)
            if not client_uuid:
                return None
                
            response = self.session.get(
                f"{self.admin_base_url}/realms/{realm_name}/clients/{client_uuid}/client-secret"
            )
            response.raise_for_status()
            
            secret_data = response.json()
            return secret_data.get('value')
            
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Failed to get client secret for {client_id}: {e}')
            return None
            
    def test_token_exchange(self, realm_name: str, config: Dict[str, Any]) -> bool:
        """Test token exchange functionality."""
        self.log('INFO', 'Testing token exchange functionality...')
        
        try:
            # Get user token
            user_token_response = self.session.post(
                f"{self.keycloak_url}/realms/{realm_name}/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": "user-web-app",
                    "username": "testuser",
                    "password": "password123",
                    "scope": "openid"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            user_token_response.raise_for_status()
            user_token = user_token_response.json()['access_token']
            
            # Get agent-planner client secret
            planner_secret = self.get_client_secret(realm_name, "agent-planner")
            if not planner_secret:
                self.log('ERROR', 'Could not get agent-planner client secret')
                return False
                
            # Test token exchange
            exchange_response = self.session.post(
                f"{self.keycloak_url}/realms/{realm_name}/protocol/openid-connect/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                    "client_id": "agent-planner",
                    "client_secret": planner_secret,
                    "subject_token": user_token,
                    "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
                    "requested_token_type": "urn:ietf:params:oauth:token-type:access_token",
                    "audience": "agent-tax-optimizer"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            exchange_response.raise_for_status()
            
            exchanged_token = exchange_response.json()
            self.log('SUCCESS', 'Token exchange test successful!')
            self.log('INFO', f'Exchanged token type: {exchanged_token.get("token_type")}')
            self.log('INFO', f'Expires in: {exchanged_token.get("expires_in")} seconds')
            
            return True
            
        except requests.exceptions.RequestException as e:
            self.log('ERROR', f'Token exchange test failed: {e}')
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    self.log('ERROR', f'Error details: {error_detail}')
                except:
                    self.log('ERROR', f'Error response: {e.response.text}')
            return False
            
    def setup_from_config(self, config: Dict[str, Any]) -> bool:
        """Set up Keycloak from configuration."""
        self.log('INFO', 'Starting Keycloak setup from configuration...')
        
        # Detect admin base URL first
        if not self.detect_admin_base_url():
            return False
        
        realm_name = config['realm']['name']
        
        # Step 1: Create realm
        if not self.create_realm(config['realm']):
            return False
            
        # Step 2: Create client scopes (without role mappings)
        self.log('INFO', 'Creating client scopes...')
        for scope in config.get('clientScopes', []):
            # Remove roles before creating the scope
            scope_copy = dict(scope)
            scope_copy.pop('roles', None)
            if not self.create_client_scope(realm_name, scope_copy):
                return False
                
        # Step 3: Create clients
        self.log('INFO', 'Creating clients...')
        for client in config.get('clients', []):
            if not self.create_client(realm_name, client):
                return False
                
        # Step 4: Assign client scopes to clients
        self.log('INFO', 'Assigning client scopes to clients...')
        for client in config.get('clients', []):
            client_id = client['clientId']
            
            # Assign default scopes
            for scope_name in client.get('assignedScopes', {}).get('default', []):
                if not self.assign_client_scope(realm_name, client_id, scope_name, 'default'):
                    self.log('WARNING', f'Failed to assign default scope {scope_name} to client {client_id}')
                    
            # Assign optional scopes  
            for scope_name in client.get('assignedScopes', {}).get('optional', []):
                if not self.assign_client_scope(realm_name, client_id, scope_name, 'optional'):
                    self.log('WARNING', f'Failed to assign optional scope {scope_name} to client {client_id}')
                    
        # Step 5: Add role scope mappings (second pass)
        self.log('INFO', 'Adding role scope mappings to client scopes...')
        for scope in config.get('clientScopes', []):
            if 'roles' in scope and scope['roles']:
                scope_id = self.get_client_scope_id(realm_name, scope['name'])
                if scope_id:
                    for role_assoc in scope['roles']:
                        client = role_assoc['client']
                        role = role_assoc['role']
                        # Get client UUID
                        client_uuid = self.get_client_uuid(realm_name, client)
                        if not client_uuid:
                            self.log('ERROR', f'Client {client} not found for scope mapping')
                            continue
                        # Get role details
                        try:
                            response = self.session.get(
                                f"{self.admin_base_url}/realms/{realm_name}/clients/{client_uuid}/roles/{role}"
                            )
                            response.raise_for_status()
                            role_data = response.json()
                        except requests.exceptions.RequestException as e:
                            self.log('ERROR', f'Failed to get role {role} for client {client}: {e}')
                            continue
                        # Add scope mapping
                        try:
                            response = self.session.post(
                                f"{self.admin_base_url}/realms/{realm_name}/client-scopes/{scope_id}/scope-mappings/clients/{client_uuid}",
                                json=[role_data]
                            )
                            if response.status_code not in (204, 201):
                                self.log('ERROR', f'Failed to add scope mapping for role {role} to scope {scope['name']}: {response.text}')
                            else:
                                self.log('SUCCESS', f'Added scope mapping: {role} to client scope {scope['name']}')
                        except requests.exceptions.RequestException as e:
                            self.log('ERROR', f'Failed to add scope mapping for role {role} to scope {scope['name']}: {e}')
        
        # Step 6: Create users
        self.log('INFO', 'Creating users...')
        for user in config.get('users', []):
            if not self.create_user(realm_name, user):
                return False
                
        # Step 7: Set up authentication flows
        self.log('INFO', 'Setting up authentication flows...')
        if 'authenticationFlows' in config:
            if not self.setup_authentication_flows(realm_name, config['authenticationFlows']):
                return False
                
        self.log('SUCCESS', 'Keycloak setup completed successfully!')
        return True
        
    def print_summary(self, config: Dict[str, Any]) -> None:
        """Print setup summary."""
        realm_name = config['realm']['name']
        
        print(f"\n{Colors.CYAN}=== KEYCLOAK SETUP SUMMARY ==={Colors.NC}")
        print(f"Keycloak URL: {self.keycloak_url}")
        print(f"Realm: {realm_name}")
        
        # Print realm attributes if they exist
        if 'attributes' in config['realm']:
            print(f"\n{Colors.WHITE}Realm Attributes:{Colors.NC}")
            for key, value in config['realm']['attributes'].items():
                print(f"  • {key}: {value}")
        
        print(f"\n{Colors.WHITE}Clients:{Colors.NC}")
        for client in config.get('clients', []):
            client_id = client['clientId']
            client_type = client['type']
            token_exchange = client.get('tokenExchange', {}).get('enabled', False)
            
            print(f"  • {client_id} ({client_type})")
            if token_exchange:
                print(f"    - Token exchange: ✅ enabled")
            if client['type'] == 'confidential':
                secret = self.get_client_secret(realm_name, client_id)
                if secret:
                    print(f"    - Client secret: {secret}")
            if 'attributes' in client:
                print(f"    - Custom attributes:")
                for key, value in client['attributes'].items():
                    print(f"      • {key}: {value}")
                    
        print(f"\n{Colors.WHITE}Client Scopes:{Colors.NC}")
        for scope in config.get('clientScopes', []):
            print(f"  • {scope['name']}: {scope['description']}")
            
        print(f"\n{Colors.WHITE}Users:{Colors.NC}")
        for user in config.get('users', []):
            print(f"  • {user['username']} ({user['email']})")
            if 'clientRoles' in user:
                for client_id, roles in user['clientRoles'].items():
                    print(f"    - {client_id}: {', '.join(roles)}")
                    
        print(f"\n{Colors.WHITE}Authentication Flows:{Colors.NC}")
        for flow in config.get('authenticationFlows', []):
            print(f"  • {flow['name']}")
            if 'copyFrom' in flow:
                print(f"    - Copied from: {flow['copyFrom']}")
            if 'authenticators' in flow:
                for auth in flow['authenticators']:
                    print(f"    - Authenticator: {auth['providerId']} ({auth.get('requirement', 'REQUIRED')})")
            if flow.get('setAsDefault', {}).get('clientAuthentication'):
                print(f"    - Set as default client authentication flow: ✅")
                    
        print(f"\n{Colors.WHITE}Token Exchange Rules:{Colors.NC}")
        for rule in config.get('tokenExchangeRules', []):
            print(f"  • {rule['description']}")
            print(f"    - Requester: {rule['requesterClient']}")
            print(f"    - Targets: {', '.join(rule['targetClients'])}")
            print(f"    - Scopes: {', '.join(rule['allowedScopes'])}")
            
        print(f"\n{Colors.GREEN}🎉 Setup complete! You can now test token exchange.{Colors.NC}")
        
    def print_test_commands(self, config: Dict[str, Any]) -> None:
        """Print test commands."""
        realm_name = config['realm']['name']
        planner_secret = self.get_client_secret(realm_name, "agent-planner")
        
        print(f"\n{Colors.CYAN}=== TEST COMMANDS ==={Colors.NC}")
        
        print(f"\n{Colors.WHITE}1. Get user token:{Colors.NC}")
        print(f"""curl -X POST \\
  {self.keycloak_url}/realms/{realm_name}/protocol/openid-connect/token \\
  -H 'Content-Type: application/x-www-form-urlencoded' \\
  -d 'grant_type=password' \\
  -d 'client_id=user-web-app' \\
  -d 'username=testuser' \\
  -d 'password=password123' \\
  -d 'scope=openid'""")
        
        print(f"\n{Colors.WHITE}2. Exchange token (basic):{Colors.NC}")
        print(f"""curl -X POST \\
  {self.keycloak_url}/realms/{realm_name}/protocol/openid-connect/token \\
  -H 'Content-Type: application/x-www-form-urlencoded' \\
  -d 'grant_type=urn:ietf:params:oauth:grant-type:token-exchange' \\
  -d 'client_id=agent-planner' \\
  -d 'client_secret={planner_secret}' \\
  -d 'subject_token=USER_ACCESS_TOKEN' \\
  -d 'subject_token_type=urn:ietf:params:oauth:token-type:access_token' \\
  -d 'requested_token_type=urn:ietf:params:oauth:token-type:access_token' \\
  -d 'audience=agent-tax-optimizer'""")
        
        print(f"\n{Colors.WHITE}3. Exchange token (with scope):{Colors.NC}")
        print(f"""curl -X POST \\
  {self.keycloak_url}/realms/{realm_name}/protocol/openid-connect/token \\
  -H 'Content-Type: application/x-www-form-urlencoded' \\
  -d 'grant_type=urn:ietf:params:oauth:grant-type:token-exchange' \\
  -d 'client_id=agent-planner' \\
  -d 'client_secret={planner_secret}' \\
  -d 'subject_token=USER_ACCESS_TOKEN' \\
  -d 'subject_token_type=urn:ietf:params:oauth:token-type:access_token' \\
  -d 'requested_token_type=urn:ietf:params:oauth:token-type:access_token' \\
  -d 'audience=agent-tax-optimizer' \\
  -d 'scope=tax:process'""")


def load_config(config_file: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"{Colors.RED}[ERROR]{Colors.NC} Configuration file {config_file} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"{Colors.RED}[ERROR]{Colors.NC} Invalid JSON in configuration file: {e}")
        sys.exit(1)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Keycloak Token Exchange Setup Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup_keycloak.py --config config.json --url http://localhost:8081
  python setup_keycloak.py --config config.json --url http://localhost:8081 --test
  python setup_keycloak.py --config config.json --url http://localhost:8081 --admin-user admin --admin-pass mypassword
        """
    )
    
    parser.add_argument('--config', '-c', required=True, help='Path to configuration JSON file')
    parser.add_argument('--url', '-u', default='http://localhost:8080', help='Keycloak URL (default: http://localhost:8080)')
    parser.add_argument('--admin-user', default='admin', help='Admin username (default: admin)')
    parser.add_argument('--admin-pass', default='admin', help='Admin password (default: admin)')
    parser.add_argument('--test', action='store_true', help='Run token exchange test after setup')
    parser.add_argument('--summary', action='store_true', help='Print setup summary')
    parser.add_argument('--test-commands', action='store_true', help='Print test commands')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Initialize Keycloak setup
    setup = KeycloakSetup(args.url, args.admin_user, args.admin_pass)
    
    # Enable debug logging if requested
    if args.debug:
        setup.debug = True
    
    # Get admin token
    if not setup.get_admin_token():
        print(f"{Colors.RED}[ERROR]{Colors.NC} Failed to authenticate with Keycloak")
        print(f"Check that Keycloak is running at {args.url} and credentials are correct")
        sys.exit(1)
        
    # Run setup
    if not setup.setup_from_config(config):
        print(f"{Colors.RED}[ERROR]{Colors.NC} Setup failed")
        sys.exit(1)
        
    # Print summary
    if args.summary or args.verbose:
        setup.print_summary(config)
        
    # Print test commands
    if args.test_commands or args.verbose:
        setup.print_test_commands(config)
        
    # Run test
    if args.test:
        print(f"\n{Colors.CYAN}=== RUNNING TOKEN EXCHANGE TEST ==={Colors.NC}")
        if setup.test_token_exchange(config['realm']['name'], config):
            print(f"{Colors.GREEN}✅ Token exchange test passed!{Colors.NC}")
        else:
            print(f"{Colors.RED}❌ Token exchange test failed!{Colors.NC}")
            sys.exit(1)


if __name__ == '__main__':
    main()