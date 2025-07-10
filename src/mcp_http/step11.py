import requests
import json
from urllib.parse import urljoin
import os

# Configuration
MCP_SERVER_URL = "http://localhost:9000"
MCP_ENDPOINT = f"{MCP_SERVER_URL}/mcp"
CREDENTIALS_FILE = "client_credentials.json"
REDIRECT_URI = "http://localhost:9090/callback"

# 1. Attempt to list tools (unauthenticated)
def post_tools_list():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": None
    }
    print(f"\n[1] Sending unauthenticated tools/list request to {MCP_ENDPOINT} ...")
    resp = requests.post(MCP_ENDPOINT, json=payload)
    print(f"Status: {resp.status_code}")
    return resp

# 2. Parse WWW-Authenticate header for resource_metadata
def parse_www_authenticate(resp):
    www_auth = resp.headers.get("WWW-Authenticate")
    print(f"\n[2] WWW-Authenticate header: {www_auth}")
    if not www_auth:
        raise RuntimeError("No WWW-Authenticate header found!")
    # Parse resource_metadata (format: Bearer realm=..., resource_metadata="...")
    import re
    match = re.search(r'resource_metadata="([^"]+)"', www_auth)
    if not match:
        raise RuntimeError("resource_metadata not found in WWW-Authenticate header!")
    resource_metadata_url = match.group(1)
    print(f"Extracted resource_metadata URL: {resource_metadata_url}")
    return resource_metadata_url

# 3. Fetch OAuth protected resource metadata
def fetch_protected_resource_metadata(url):
    print(f"\n[3] Fetching protected resource metadata from {url} ...")
    resp = requests.get(url)
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch protected resource metadata: {resp.text}")
    data = resp.json()
    print("Protected resource metadata:")
    print(json.dumps(data, indent=2))
    return data

# 4. Extract authorization_servers
def extract_authorization_server(resource_metadata):
    auth_servers = resource_metadata.get("authorization_servers")
    if not auth_servers or not isinstance(auth_servers, list):
        raise RuntimeError("authorization_servers field missing or invalid!")
    auth_server = auth_servers[0]
    print(f"\n[4] Using authorization server: {auth_server}")
    return auth_server

# 5. Fetch authorization server metadata (RFC8414)
def fetch_authorization_server_metadata(auth_server_url):
    # Always append /.well-known/oauth-authorization-server to the discovered base URL
    if auth_server_url.endswith("/"):
        auth_server_url = auth_server_url[:-1]
    metadata_url = urljoin(auth_server_url + '/', ".well-known/oauth-authorization-server")
    print(f"\n[5] Fetching authorization server metadata from {metadata_url} ...")
    resp = requests.get(metadata_url)
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch authorization server metadata: {resp.text}")
    data = resp.json()
    print("Authorization server metadata:")
    print(json.dumps(data, indent=2))
    # Print relevant endpoints
    print("\nRelevant endpoints:")
    for key in ["token_endpoint", "authorization_endpoint", "registration_endpoint"]:
        if key in data:
            print(f"  {key}: {data[key]}")
    return data

def print_dcr_request(authz_metadata):
    reg_endpoint = authz_metadata.get("registration_endpoint")
    if not reg_endpoint:
        print("\n[6] No registration_endpoint found in authorization server metadata.")
        return
    print(f"\n[6] Dynamic Client Registration (RFC 7591)")
    print(f"Registration endpoint: {reg_endpoint}")
    dcr_payload = {
        "client_name": "My Anonymous Client",
        "redirect_uris": [REDIRECT_URI],
        "grant_types": ["authorization_code"],
        "scope": "mcp:read mcp:tools mcp:prompts echo-mcp-server-audience",
        "token_endpoint_auth_method": "client_secret_basic"
    }
    print("Registration request payload:")
    print(json.dumps(dcr_payload, indent=2))

def load_client_credentials():
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as f:
            creds = json.load(f)
        print(f"\n[INFO] Loaded client credentials from {CREDENTIALS_FILE}:")
        print(json.dumps(creds, indent=2))
        return creds
    return None

def save_client_credentials(client_id, client_secret):
    creds = {"client_id": client_id, "client_secret": client_secret}
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(creds, f, indent=2)
    print(f"\n[INFO] Saved client credentials to {CREDENTIALS_FILE}")

def perform_dcr_request(authz_metadata):
    reg_endpoint = authz_metadata.get("registration_endpoint")
    if not reg_endpoint:
        print("\n[6] No registration_endpoint found in authorization server metadata.")
        return None
    print(f"\n[6] Dynamic Client Registration (RFC 7591)")
    print(f"Registration endpoint: {reg_endpoint}")
    dcr_payload = {
        "client_name": "My Anonymous Client",
        "redirect_uris": [REDIRECT_URI],
        "grant_types": ["authorization_code"],
        "scope": "mcp:read mcp:tools mcp:prompts echo-mcp-server-audience",
        "token_endpoint_auth_method": "client_secret_basic"
    }
    print("Registration request payload:")
    print(json.dumps(dcr_payload, indent=2))
    try:
        resp = requests.post(reg_endpoint, json=dcr_payload, headers={"Content-Type": "application/json"})
        print(f"\nRegistration response status: {resp.status_code}")
        print("Registration response body:")
        print(resp.text)
        if resp.status_code == 201 or resp.status_code == 200:
            data = resp.json()
            client_id = data.get("client_id")
            client_secret = data.get("client_secret")
            print(f"\n[7] Registered client_id: {client_id}")
            print(f"[7] Registered client_secret: {client_secret}")
            save_client_credentials(client_id, client_secret)
            return data
        else:
            print("\n[7] Registration failed.")
            return None
    except Exception as e:
        print(f"\n[ERROR] Registration request failed: {e}")
        return None

def build_authorization_url(authz_metadata, client_id):
    authz_endpoint = authz_metadata.get("authorization_endpoint")
    if not authz_endpoint:
        print("\n[8] No authorization_endpoint found in authorization server metadata.")
        return None
    # Required parameters
    import secrets
    import urllib.parse
    state = secrets.token_urlsafe(16)
    # The resource parameter is required by MCP spec
    resource = MCP_SERVER_URL
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": "mcp:read mcp:tools mcp:prompts echo-mcp-server-audience",
        "state": state,
        "resource": resource
    }
    url = authz_endpoint + "?" + urllib.parse.urlencode(params)
    print(f"\n[8] Open this URL in your browser to authorize:")
    print(url)
    return state

def prompt_for_redirect_url():
    print("\nAfter authorizing, you will be redirected to your callback URL.")
    print("Copy the full URL from your browser's address bar and paste it here.")
    redirect_url = input("Paste the full redirect URL: ").strip()
    return redirect_url

def extract_code_from_redirect_url(redirect_url, expected_state=None):
    import urllib.parse
    parsed = urllib.parse.urlparse(redirect_url)
    query = urllib.parse.parse_qs(parsed.query)
    code = query.get("code", [None])[0]
    state = query.get("state", [None])[0]
    if not code:
        print("\n[ERROR] No code found in redirect URL.")
        return None
    print(f"\n[9] Authorization code: {code}")
    if expected_state:
        if state != expected_state:
            print(f"[WARNING] State mismatch! Expected: {expected_state}, Got: {state}")
        else:
            print(f"[INFO] State matches: {state}")
    return code

def exchange_code_for_token(authz_metadata, client_id, client_secret, code):
    token_endpoint = authz_metadata.get("token_endpoint")
    if not token_endpoint:
        print("\n[10] No token_endpoint found in authorization server metadata.")
        return None
    print(f"\n[10] Exchanging code for token at: {token_endpoint}")
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "client_secret": client_secret,
        "resource": MCP_SERVER_URL
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    import requests
    resp = requests.post(token_endpoint, data=data, headers=headers)
    print(f"Token endpoint response status: {resp.status_code}")
    print("Token endpoint response body:")
    print(resp.text)
    if resp.status_code == 200:
        token_data = resp.json()
        access_token = token_data.get("access_token")
        if access_token:
            print(f"\n[11] Access token: {access_token[:40]}... (truncated)")
            return access_token
        else:
            print("\n[ERROR] No access_token in response.")
            return None
    else:
        print("\n[ERROR] Failed to obtain access token.")
        return None

def mcp_tools_list_with_token(access_token):
    print(f"\n[12] Calling MCP tools/list with access token...")
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": None
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    resp = requests.post(MCP_ENDPOINT, json=payload, headers=headers)
    print(f"MCP response status: {resp.status_code}")
    print("MCP response body:")
    print(resp.text)
    if resp.status_code == 200:
        try:
            data = resp.json()
            print("\n[13] MCP tools:")
            print(json.dumps(data, indent=2))
        except Exception as e:
            print(f"\n[ERROR] Failed to parse MCP response: {e}")
    else:
        print("\n[ERROR] MCP server returned error.")

def main():
    try:
        creds = load_client_credentials()
        if creds:
            print("\n[INFO] Skipping registration since credentials already exist.")
            client_id = creds["client_id"]
            client_secret = creds["client_secret"]
        else:
            resp = post_tools_list()
            if resp.status_code != 401:
                print("Expected 401 Unauthorized, got:", resp.status_code)
                print("Response:", resp.text)
                return
            resource_metadata_url = parse_www_authenticate(resp)
            resource_metadata = fetch_protected_resource_metadata(resource_metadata_url)
            auth_server_url = extract_authorization_server(resource_metadata)
            authz_metadata = fetch_authorization_server_metadata(auth_server_url)
            reg_data = perform_dcr_request(authz_metadata)
            if not reg_data:
                print("\n[ERROR] Registration failed, cannot continue.")
                return
            client_id = reg_data.get("client_id")
            client_secret = reg_data.get("client_secret")
        # --- OAuth flow ---
        # Discover endpoints
        if not creds:
            # If we just registered, we already have authz_metadata
            pass
        else:
            # If we loaded creds, need to rediscover endpoints
            resp = post_tools_list()
            if resp.status_code != 401:
                print("Expected 401 Unauthorized, got:", resp.status_code)
                print("Response:", resp.text)
                return
            resource_metadata_url = parse_www_authenticate(resp)
            resource_metadata = fetch_protected_resource_metadata(resource_metadata_url)
            auth_server_url = extract_authorization_server(resource_metadata)
            authz_metadata = fetch_authorization_server_metadata(auth_server_url)
        state = build_authorization_url(authz_metadata, client_id)
        if not state:
            print("\n[ERROR] Could not build authorization URL.")
            return
        redirect_url = prompt_for_redirect_url()
        code = extract_code_from_redirect_url(redirect_url, expected_state=state)
        if not code:
            print("\n[ERROR] No code to exchange for token.")
            return
        access_token = exchange_code_for_token(authz_metadata, client_id, client_secret, code)
        if not access_token:
            print("\n[ERROR] Could not obtain access token.")
            return
        mcp_tools_list_with_token(access_token)
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    main() 