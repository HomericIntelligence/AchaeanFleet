# TLS Infrastructure for homeric-mesh

This directory contains the TLS/mTLS configuration for AchaeanFleet. It addresses
[OWASP A02:2021 — Cryptographic Failures](https://owasp.org/Top10/A02_2021-Cryptographic_Failures/)
by encrypting all inter-service communication on the Docker bridge network.

## Architecture

```
Agent Containers (9 vessels)
        │
        │  https://caddy:8443  (TLS, validated by /certs/ca.crt)
        ▼
   ┌─────────┐
   │  Caddy  │  (TLS termination)
   │  :8443  │
   └────┬────┘
        │  http://172.20.0.1:8080  (plain HTTP, host-only loopback)
        ▼
ProjectAgamemnon Coordinator (host process, port 8080)
```

Caddy terminates TLS for inbound agent connections. It forwards to ProjectAgamemnon
on the Docker bridge gateway over plain HTTP — this hop stays on the loopback/bridge
interface and never crosses an untrusted network boundary.

## Certificate Hierarchy

```
ca.crt / ca.key          ← Root CA (HomericIntelligence Mesh CA)
   ├── caddy.crt / caddy.key   ← Caddy server cert (SANs: caddy, 172.20.0.1, localhost)
   └── nats.crt  / nats.key    ← NATS server cert  (SANs: nats, localhost)
```

## Generating Certificates

```bash
# From repo root — creates tls/certs/
bash tls/generate-certs.sh

# Custom validity (default: 825 days)
bash tls/generate-certs.sh --days 3650
```

**Important:** `tls/certs/` is excluded from version control via `.gitignore`.
Never commit private keys.

## Directory Layout

```
tls/
├── generate-certs.sh     ← Certificate generation script (openssl)
├── certs/                ← Generated certs (git-ignored, create with generate-certs.sh)
│   ├── ca.crt
│   ├── ca.key            ← PRIVATE — never commit
│   ├── caddy.crt
│   ├── caddy.key         ← PRIVATE — never commit
│   ├── nats.crt
│   └── nats.key          ← PRIVATE — never commit
├── caddy/
│   └── Caddyfile         ← Caddy reverse-proxy + TLS config
└── nats/
    └── nats-tls.conf     ← NATS server TLS config (forward-looking template)
```

## Using with Docker Compose

Overlay `docker-compose.caddy.yml` on top of any fleet compose file:

```bash
# Generate certs first
bash tls/generate-certs.sh

# Claude-only + Caddy TLS
cd compose
cp .env.example .env
# Edit .env: add ANTHROPIC_API_KEY
docker compose -f docker-compose.caddy.yml -f docker-compose.claude-only.yml up -d

# Full mesh + Caddy TLS
docker compose -f docker-compose.caddy.yml -f docker-compose.mesh.yml up -d
```

Agent containers connect to `https://caddy:8443` (set via `AGAMEMNON_URL`).
The CA cert is mounted at `/certs/ca.crt` for validation.

## Rotating Certificates

```bash
# Stop Caddy, regenerate, restart
docker compose stop caddy
bash tls/generate-certs.sh
docker compose start caddy
```

Caddy reloads its config on `SIGHUP` — a restart is the simplest rotation path
for a self-signed CA. For production, consider Caddy's built-in ACME support with
an internal ACME CA (Step CA / Smallstep).

## Verifying TLS

```bash
# Verify cert chain
openssl verify -CAfile tls/certs/ca.crt tls/certs/caddy.crt

# Test TLS handshake from host
curl --cacert tls/certs/ca.crt https://172.20.0.1:8443/health

# Test from inside a container
docker exec hi-aindrea curl --cacert /certs/ca.crt https://caddy:8443/health

# Confirm plaintext is rejected (should fail or return no response)
curl http://172.20.0.1:8443/health  # Not a valid plain-HTTP port for Caddy
```

## NATS TLS (Forward-Looking)

When Hermes/Keystone are wired into the mesh, NATS must use TLS from day one.
See `tls/nats/nats-tls.conf` for the server config template.

Agents connect with:
```
NATS_URL=tls://nats:4222
```

Validate with:
```bash
nats pub -s "tls://localhost:4222" \
  --tlscacert tls/certs/ca.crt \
  test.subject "hello"
```

## CI distribution to Nomad client hosts

Certs generated locally with `bash tls/generate-certs.sh` are for development. In CI,
`.github/workflows/certs.yml` regenerates and distributes them on every push to `main`
via `scripts/distribute-certs.sh`.

Required GitHub Actions secrets:

| Secret | Format | Purpose |
|---|---|---|
| `NOMAD_SSH_DEPLOY_KEY` | base64 of an ed25519 private key | Authenticates to each Nomad client host as the `nomad` user |
| `NOMAD_CLIENT_KNOWN_HOSTS` | base64 of an ssh `known_hosts` file | Pre-enrolls host fingerprints; avoids `StrictHostKeyChecking=no` |
| `NOMAD_CLIENT_HOSTS` | space-separated hostnames or IPs | Targets for cert distribution |

Generate the deploy key and encode secrets:

```bash
# Generate a new deploy key
ssh-keygen -t ed25519 -a 64 -f ~/.ssh/nomad_deploy -N ""

# Base64-encode for GitHub secrets
base64 -w0 ~/.ssh/nomad_deploy        # → NOMAD_SSH_DEPLOY_KEY
ssh-keyscan -t ed25519 host1 host2 ... | base64 -w0  # → NOMAD_CLIENT_KNOWN_HOSTS
```

Set via GitHub CLI:

```bash
gh secret set NOMAD_SSH_DEPLOY_KEY     --body "$(base64 -w0 ~/.ssh/nomad_deploy)"
gh secret set NOMAD_CLIENT_KNOWN_HOSTS --body "$(ssh-keyscan -t ed25519 host1 host2 | base64 -w0)"
gh secret set NOMAD_CLIENT_HOSTS       --body "host1 host2 host3"
```

Once secrets are provisioned, manually trigger a test run:

```bash
gh workflow run certs.yml
```

## Tailscale Alternative

If the homeric-mesh runs entirely on Tailscale-connected hosts, WireGuard provides
network-layer encryption and this TLS layer may be redundant. See
[ADR-007](../docs/adr/007-tls-mesh-communications.md) for the trade-off analysis.
For Docker-bridge deployments, in-mesh TLS via Caddy is required.
