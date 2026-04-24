# AchaeanFleet

Container infrastructure for the HomericIntelligence agent mesh.

## What this repo is

AchaeanFleet builds OCI-compliant Docker images for each AI agent type supported by the mesh. It is **infrastructure only** — no agent logic, no ProjectAgamemnon modifications.

## What this repo is NOT

- Do not add agent provisioning logic here → that's Myrmidons
- Do not modify ProjectAgamemnon source → it is mounted read-only via volume
- Do not add authentication, routing, or orchestration → ProjectAgamemnon handles that

## Structure

```
bases/          3 base Dockerfiles (node, python, minimal)
vessels/        9 agent vessel Dockerfiles (FROM a base + AI tool)
compose/        Docker Compose files (claude-only and full mesh)
nomad/          Nomad job specs (Phase 6)
dagger/         Dagger pipeline for CI/CD (Phase 5)
.github/        GitHub Actions CI
```

## Building images locally

```bash
# Build a base image
docker build -f bases/Dockerfile.node -t achaean-base-node:latest .

# Build a vessel (must build base first)
docker build -f vessels/claude/Dockerfile \
  --build-arg BASE_IMAGE=achaean-base-node:latest \
  -t achaean-claude:latest .

# Build all images (Phase 5+)
npx ts-node dagger/pipeline.ts build
```

## Running the mesh

```bash
# Set up environment
cd compose
cp .env.example .env
# Edit .env: add ANTHROPIC_API_KEY and verify AGAMEMNON_URL

# Claude-only (Phase 3 target)
docker compose -f docker-compose.claude-only.yml up -d

# Full heterogeneous mesh (Phase 4 target)
docker compose -f docker-compose.mesh.yml up -d
```

## Agamemnon agent sidecar integration

The base images are designed to work with the Agamemnon agent sidecar. The binary is mounted at runtime:

```yaml
volumes:
  - /home/mvillmow/ProjectAgamemnon/agent-sidecar/agent-sidecar:/app/agent-sidecar:ro
```

**Never copy the Agamemnon agent sidecar into the image at build time** — this would lock the image to a specific ProjectAgamemnon version.

## Read-only root filesystem

All compose services use `read_only: true` for security hardening. Write access is explicitly granted to specific paths via tmpfs mounts and named volumes:

**tmpfs mounts (ephemeral, cleared on container restart):**
- `/tmp` — temp files and tmux sockets (`/tmp/tmux-*`)
- `/run` — runtime PID files and socket files
- `/home/agent/.cache` — tool caches (npm, pip, Claude Code, etc.)
- `/home/agent/.config` — runtime configuration writes
- `/home/agent/.local` — Python user-site packages and local state

**Named/bind volumes (persistent):**
- `/workspace` — agent work directory, mounted from `${WORKSPACE_ROOT}` (writable for agents to read/write project files)
- `/certs` — TLS certificates, mounted read-only (`:ro`)

**Intentionally read-only:**
- `/app/agent-sidecar` — ProjectAgamemnon sidecar binary, mounted from host at build time with `:ro` flag. Never write here; the sidecar is managed by ProjectAgamemnon lifecycle.

## Port mapping convention

```
8080      ProjectAgamemnon coordinator (existing, not in this repo)
23001     hi-aindrea (claude)
23002     hi-eris (claude)
23003     hi-baird (claude)
23004     hi-vegai (claude)
23005     hi-pallas (claude)
23010     hi-codex-1
23020     hi-aider-1
23030     hi-goose-1
23040     hi-cline-1
23050     hi-opencode-1
23060     hi-codebuff-1
23070     hi-ampcode-1
23080     hi-worker-1
```

## Network

All containers join the `homeric-mesh` bridge network. Containers resolve each other by service name via Docker's internal DNS. ProjectAgamemnon on the host connects via `172.20.0.1` (the Docker bridge gateway).

## Nomad

See [`nomad/PATTERNS.md`](nomad/PATTERNS.md) for the full HCL authoring guide.

**Key rule:** Use `template` stanzas with Consul Template syntax for Nomad runtime values
(`NOMAD_ALLOC_INDEX`, `NOMAD_ALLOC_ID`, etc.). Never use `${VAR}` in a bare `env` stanza
for alloc-scoped values — Nomad does not interpolate them at runtime.

## Adding a new agent type

1. Choose a base image (`node`, `python`, or `minimal`)
2. Create `vessels/<agentname>/Dockerfile` with `ARG BASE_IMAGE` + install step
3. Add an entry to `compose/docker-compose.mesh.yml`
4. Add to the matrix in `.github/workflows/ci.yml`
5. Add vessel entry in `dagger/pipeline.ts`
