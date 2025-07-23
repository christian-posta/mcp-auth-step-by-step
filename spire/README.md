# SPIRE Docker Compose Demo

This folder contains a minimal Docker Compose setup for running SPIRE Server and Agent, suitable for local development and testing with an MCP client.

## Overview
- **Ephemeral setup**: All data is stored inside the containers and will be lost if the containers are removed or restarted.
- **SPIRE Server and Agent run in separate containers**.
- **SPIRE Agent exposes the Workload API over TCP** (unauthenticated, for demo/dev only) 
- **Default trust domain**: `example.org`

## Ports and Endpoints

| Service         | Host Port | Container Port | Purpose/How to Use                        |
|-----------------|-----------|---------------|-------------------------------------------|
| SPIRE Server    | 18081     | 8081          | Management API (token generation, entries) |
| SPIRE Agent API |           |               | Workload API (UDS, no exposed TCP)     |

- **SPIRE Server API**: `localhost:18081`
- **SPIRE Agent Workload API (TCP)**: `localhost:18082`

## Usage

1. **Start the stack:**
   ```bash
   ./start-spire.sh
   ```
2. **Fetch a JWT SVID from your MCP client:**
   ```bash
   ./get-svid.sh
   ```

Inspect the token and verify it looks right. 

3. **Verify OIDC Discovery**
   ```bash
   curl http://localhost:18443/.well-known/openid-configuration   
   ```

4. **Verify JWKS**
   ```bash
   curl http://localhost:18443/keys
   ```   

   Note, the SPIRE issuer for JWTs is:
   ```text
   http://spire-server:8443
   ```

   JWKS URL for keycloak:
   ```
   http://spire-oidc-discovery:8443/keys
   ```

## How to Change the Trust Domain

1. **Edit the config files:**
   - `server_container.conf`: Change the `trust_domain` value.
   - `agent_container.conf`: Change the `trust_domain` and update `trust_bundle_path` if needed.
2. **Update registration commands:**
   - Use the new trust domain in all `spiffe://<trust-domain>/...` IDs.


## Notes
- This setup is for demo/dev only. The Workload API is exposed over TCP without authentication.
- All data is ephemeral. For persistent storage, add Docker volumes.
- For more advanced scenarios, see the [SPIRE documentation](https://spiffe.io/docs/latest/spire/). 

## Troubleshooting

### Error: unable to load upstream CA key: is a directory
- Ensure `dummy_upstream_ca.key` and `dummy_upstream_ca.crt` in this folder are files, not directories.
- If you accidentally created a directory, delete it and copy the correct file from the supporting SPIRE config.
- The volume mounts in `docker-compose.yml` should look like:
  ```yaml
  - ./dummy_upstream_ca.key:/etc/spire/server/dummy_upstream_ca.key:ro
  - ./dummy_upstream_ca.crt:/etc/spire/server/dummy_upstream_ca.crt:ro
  ```

### Error: admin socket cannot be in the same directory or a subdirectory as that containing the Workload API socket
- In `agent_container.conf`, make sure `admin_socket_path` is **not** in the same directory as `socket_path`.
- Example fix:
  ```hcl
  admin_socket_path = "/run/spire/agent/admin.sock"
  ```
- Restart the containers after making this change. 

### How to generate dummy CA certs and keys if missing
If you do not have the required files (`dummy_upstream_ca.crt`, `dummy_upstream_ca.key`, `dummy_root_ca.crt`), you can generate them with the following commands:

```bash
# Generate dummy_upstream_ca.key and dummy_upstream_ca.crt
openssl req -x509 -newkey rsa:2048 -days 365 -nodes \
  -keyout dummy_upstream_ca.key \
  -out dummy_upstream_ca.crt \
  -subj "/CN=Dummy Upstream CA"

# Copy dummy_upstream_ca.crt as dummy_root_ca.crt for the agent
cp dummy_upstream_ca.crt dummy_root_ca.crt
```

- Place these files in the `spire/` folder.
- Make sure they are files, not directories.
- Restart your containers after generating these files. 


## Notes

We cannot use identity brokering in keycloak because SPIRE does not implement authorization code which is a pre-req in keycloak to do brokering

We can try using client-jwt, but Keycloak expects the isuser and subject to be the same (since it's client issued JWT). With SPIRE this will not be the case. 