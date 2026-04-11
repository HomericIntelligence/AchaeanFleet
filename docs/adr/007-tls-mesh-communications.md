# ADR-007: TLS for Homeric-Mesh Inter-Service Communication

**Status:** Accepted  
**Date:** 2026-04-10  
**Issue:** [#26 — Security: Agent containers use NATS and Agamemnon over unencrypted HTTP](https://github.com/HomericIntelligence/AchaeanFleet/issues/26)  
**OWASP:** A02:2021 — Cryptographic Failures

---

## Context

All inter-service communication in the homeric-mesh used plaintext protocols:

- `AGAMEMNON_URL=http://172.20.0.1:8080` — ProjectAgamemnon coordinator
- `nats://localhost:4222` — Hermes/Keystone NATS (planned)
- HTTP health checks inside all containers

While these services run on a private Docker bridge network (`172.20.0.0/16`), any
container with access to the bridge could sniff traffic including:

- `ANTHROPIC_API_KEY` values transmitted in `Authorization: Bearer` headers
- Agent task payloads and configurations
- Webhook secrets and session tokens

This is **OWASP A02:2021 — Cryptographic Failures** (cleartext transmission of sensitive data).

---

## Decision

**Use Caddy as a TLS-terminating reverse proxy in front of ProjectAgamemnon,
with a self-signed CA for the Docker-bridge deployment case.**

Key decisions:

### 1. Caddy over Traefik/nginx

Caddy was chosen because:
- Zero-config TLS: `tls cert key` in the Caddyfile is sufficient
- Self-signed CA workflow is first-class (no ACME required)
- Built-in health endpoint on `:2019` for Docker health checks
- The operational burden of certificate rotation is minimal

### 2. Cert mount pattern mirrors sidecar mount

Certificates are mounted read-only at `/certs` at runtime, never baked into images.
This mirrors the existing pattern for the Agamemnon sidecar binary:

```yaml
volumes:
  - ${TLS_CERT_DIR:-../tls/certs}:/certs:ro
```

This avoids locking images to a specific cert version and allows rotation without
a rebuild.

### 3. Atomic scheme upgrade

`AGAMEMNON_URL` was changed from `http://` to `https://` simultaneously across all
compose files, Nomad specs, and pod specs. Partial upgrades produce
`SSL_ERROR_RX_RECORD_TOO_LONG` (TLS handshake against a plain-HTTP listener).

### 4. Caddy's reverse proxy hop stays on the bridge

Caddy terminates TLS from containers, then proxies to Agamemnon on
`http://172.20.0.1:8080` (the Docker bridge gateway). This plain-HTTP hop is
confined to the host loopback/bridge interface and is not exposed to other
containers on the mesh network — so it does not reintroduce the original
vulnerability.

### 5. NATS: tls:// from day one

NATS is not yet deployed but is planned for Hermes/Keystone integration.
`tls/nats/nats-tls.conf` is added as a template that uses the same CA.
When NATS is wired in, `NATS_URL=tls://nats:4222` is already in `.env.example`.

---

## Consequences

### Positive

- API keys and agent task data are encrypted in transit on the mesh network
- The cert mount pattern is consistent with the sidecar binary mount pattern
- No changes to base images or vessel Dockerfiles — `ca-certificates` was already installed
- Caddy's self-signed CA workflow requires only `openssl` (present on all base images)
- Overlay compose (`docker-compose.caddy.yml`) is opt-in — existing `docker compose up`
  still works without TLS for local development if Caddy is not started

### Negative / Trade-offs

- One additional container (`caddy`) is required in all deployments
- Self-signed certs require distributing `ca.crt` to all containers and hosts
- Certificate rotation requires stopping Caddy and restarting (or sending `SIGHUP`)
- Nomad deployments need `tls/certs/` distributed to every client host at
  `var.tls_cert_dir` (default: `/etc/achaean/certs`)

---

## Alternatives Considered

### Tailscale / WireGuard (network-layer encryption)

If all homeric-mesh hosts are Tailscale-connected, WireGuard provides network-layer
encryption that makes in-mesh TLS redundant. This is an acceptable alternative for
non-Docker-bridge deployments (e.g., multi-host Tailscale meshes).

**Why not chosen as default:** The Docker-bridge case (single-host, local development)
is the primary deployment target for Phase 3/4. Tailscale is not available inside
Docker containers without a sidecar, making it unsuitable as a universal solution.

### Mutual TLS (mTLS) / Zero-trust

Full mTLS (each agent presents a client cert to Caddy) was considered as a Phase 5/6
hardening step. Not implemented now because:
- Agent processes (Claude Code, Aider, etc.) don't currently have a mechanism to
  present client certs
- Server-side TLS (Caddy validates the connection; agents validate Caddy's cert)
  already closes the primary threat: passive credential sniffing on the bridge

mTLS remains the Phase 6 hardening target. See `tls/nats/nats-tls.conf` for the
`verify: false` flag that is the mTLS toggle for NATS.

### Consul Connect (service mesh)

Nomad's Consul Connect sidecar proxy provides automatic mTLS between services with
certificate rotation via Vault. This is the Phase 6 target for Nomad deployments.
Not implemented now due to the operational complexity of deploying Consul + Vault
alongside the mesh.

---

## Related

- [ADR-006](https://github.com/HomericIntelligence/Odysseus/blob/main/docs/adr/006-decouple-from-ai-maestro.md) — ai-maestro decoupling (renamed `AGAMEMNON_URL`)
- [`tls/README.md`](../../tls/README.md) — operational guide (cert generation, rotation, verification)
- [SECURITY.md](../../SECURITY.md) — security policy and reporting
