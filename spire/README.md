# SPIRE Docker Compose Demo

This folder contains a minimal Docker Compose setup for running SPIRE Server and Agent, suitable for local development and testing with an MCP client.

## Overview
- **Ephemeral setup**: All data is stored inside the containers and will be lost if the containers are removed or restarted.
- **SPIRE Server and Agent run in separate containers**.
- **SPIRE Agent exposes the Workload API over TCP** (unauthenticated, for demo/dev only) so you can fetch JWT SVIDs from your host.
- **Default trust domain**: `example.org`

## Ports and Endpoints

| Service         | Host Port | Container Port | Purpose/How to Use                        |
|-----------------|-----------|---------------|-------------------------------------------|
| SPIRE Server    | 18081     | 8081          | Management API (token generation, entries) |
| SPIRE Agent API | 18082     | 18082         | Workload API (for MCP client JWT SVID)     |

- **SPIRE Server API**: `localhost:18081`
- **SPIRE Agent Workload API (TCP)**: `localhost:18082`

## Usage

1. **Start the stack:**
   ```bash
   docker compose up -d
   ```
2. **Generate a join token:**
   ```bash
   docker compose exec spire-server /opt/spire/bin/spire-server token generate -spiffeID spiffe://example.org/agent
   ```
   Save the token for use with the agent.
3. **Register a workload (example):**
   ```bash
   docker compose exec spire-server /opt/spire/bin/spire-server entry create \
     -parentID spiffe://example.org/agent \
     -spiffeID spiffe://example.org/workload \
     -selector unix:uid:0
   ```
4. **Fetch a JWT SVID from your MCP client:**
   - Connect to `localhost:18082` using the [SPIFFE Workload API](https://github.com/spiffe/go-spiffe/blob/main/v2/proto/spiffe/workload/workload.proto).
   - Request a JWT SVID for the registered workload.

## How to Change the Trust Domain

1. **Edit the config files:**
   - `server_container.conf`: Change the `trust_domain` value.
   - `agent_container.conf`: Change the `trust_domain` and update `trust_bundle_path` if needed.
2. **Update registration commands:**
   - Use the new trust domain in all `spiffe://<trust-domain>/...` IDs.
3. **Restart the stack:**
   ```bash
   docker compose down -v
   docker compose up -d
   ```

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